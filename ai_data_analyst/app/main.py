from __future__ import annotations

import shutil
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models import AnalysisState
from app.settings import MAX_JOBS, MAX_UPLOAD_BYTES, OUTPUT_DIR, STATIC_DIR, UPLOAD_DIR
from app.workflow import AnalysisWorkflow

app = FastAPI(title="AI Data Analyst", version="0.1.0")


class UploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_UPLOAD_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "上传文件超过 50MB 限制"},
                )
        response = await call_next(request)
        return response


app.add_middleware(UploadSizeMiddleware)

workflow = AnalysisWorkflow()
JOBS: OrderedDict[str, AnalysisState] = OrderedDict()


def _evict_old_jobs() -> None:
    while len(JOBS) >= MAX_JOBS:
        JOBS.popitem(last=False)


def _safe_name(filename: str) -> str:
    name = Path(filename).name.replace(" ", "_")
    # strip path-traversal sequences like "../" or "..\"
    name = Path(name).name
    # only allow safe characters
    name = "".join(c for c in name if c.isalnum() or c in {".", "-", "_"})
    return name or "dataset.csv"


async def _save_upload(file: UploadFile, target: Path) -> None:
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    saved = target.stat().st_size
    if saved > MAX_UPLOAD_BYTES:
        target.unlink()
        raise HTTPException(status_code=413, detail="上传文件超过 50MB 限制")


async def _read_brief(brief_file: UploadFile | None) -> str:
    if brief_file is None:
        return ""
    content = await brief_file.read()
    for encoding in ["utf-8-sig", "utf-8", "gbk"]:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


@app.post("/api/analyze")
async def analyze(
    data_file: UploadFile = File(...),
    analysis_goal: str = Form(""),
    analysis_type: str = Form("general"),
    brief_file: UploadFile | None = File(None),
):
    analysis_type = analysis_type.strip().lower()
    if analysis_type not in {"general", "finance"}:
        raise HTTPException(status_code=400, detail="分析类型仅支持 general 或 finance")

    suffix = Path(data_file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3"}:
        raise HTTPException(status_code=400, detail="数据文件仅支持 CSV、XLSX、XLS、SQLite")

    job_id = uuid.uuid4().hex[:12]
    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    upload_path = job_upload_dir / _safe_name(data_file.filename or f"dataset{suffix}")
    await _save_upload(data_file, upload_path)
    brief_text = await _read_brief(brief_file)
    goal = "\n\n".join(part for part in [analysis_goal.strip(), brief_text.strip()] if part)

    state = AnalysisState(
        job_id=job_id,
        original_filename=data_file.filename or upload_path.name,
        analysis_goal=goal,
        analysis_type=analysis_type,
        upload_path=upload_path,
        output_dir=job_output_dir,
    )
    state = workflow.run(state)
    _evict_old_jobs()
    JOBS[job_id] = state
    return state.public_payload()


@app.get("/api/jobs")
def list_jobs():
    return [
        {
            "job_id": state.job_id,
            "filename": state.original_filename,
            "rows": state.schema.get("rows"),
            "columns": state.schema.get("columns"),
            "errors": state.errors,
            "report_url": f"/api/report/{state.job_id}" if state.report_path else None,
        }
        for state in JOBS.values()
    ]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    state = JOBS.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在或服务已重启")
    return state.public_payload()


@app.get("/api/report/{job_id}")
def get_report(job_id: str):
    state = JOBS.get(job_id)
    if not state or not state.report_path or not state.report_path.exists():
        report_path = OUTPUT_DIR / job_id / "analysis_report.html"
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="报告不存在")
    else:
        report_path = state.report_path
    return FileResponse(report_path, media_type="text/html", filename=f"analysis_report_{job_id}.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
