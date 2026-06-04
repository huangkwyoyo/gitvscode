from __future__ import annotations

import asyncio
import shutil
import threading
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
from app.services.logger import get_logger
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
_JOBS_LOCK = threading.Lock()


def _evict_old_jobs() -> None:
    while len(JOBS) >= MAX_JOBS:
        JOBS.popitem(last=False)


def _cleanup_old_files() -> None:
    """清理超出保留时间的上传和输出文件。"""
    import time
    from app.settings import JOB_RETENTION_HOURS
    cutoff = time.time() - JOB_RETENTION_HOURS * 3600
    for dir_path in [UPLOAD_DIR, OUTPUT_DIR]:
        if not dir_path.exists():
            continue
        for job_dir in dir_path.iterdir():
            if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)


def _safe_name(filename: str) -> str:
    name = Path(filename).name.replace(" ", "_")
    # strip path-traversal sequences like "../" or "..\"
    name = Path(name).name
    # only allow safe characters
    name = "".join(c for c in name if c.isalnum() or c in {".", "-", "_"})
    return name or "dataset.csv"


async def _save_upload(file: UploadFile, target: Path) -> None:
    """流式保存上传文件，边写边检查大小，避免先写完整文件再校验的TOCTOU窗口。"""
    written = 0
    with target.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 每次读 1MB
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                buffer.close()
                target.unlink()
                raise HTTPException(status_code=413, detail="上传文件超过 50MB 限制")
            buffer.write(chunk)


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

    logger = get_logger("app.api")
    logger.info("收到分析请求: file=%s, type=%s", data_file.filename, analysis_type)

    state = AnalysisState(
        job_id=job_id,
        original_filename=data_file.filename or upload_path.name,
        analysis_goal=goal,
        analysis_type=analysis_type,
        upload_path=upload_path,
        output_dir=job_output_dir,
    )
    state = await asyncio.to_thread(workflow.run, state)
    with _JOBS_LOCK:
        _evict_old_jobs()
        JOBS[job_id] = state
    _cleanup_old_files()
    return state.public_payload()


@app.get("/api/health")
def health():
    """健康检查端点，返回服务状态。"""
    with _JOBS_LOCK:
        return {"status": "ok", "jobs_count": len(JOBS)}


@app.get("/api/jobs")
def list_jobs():
    with _JOBS_LOCK:
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
    with _JOBS_LOCK:
        state = JOBS.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在或服务已重启")
    return state.public_payload()


@app.get("/api/report/{job_id}")
def get_report(job_id: str):
    with _JOBS_LOCK:
        state = JOBS.get(job_id)
    if not state or not state.report_path or not state.report_path.exists():
        report_path = OUTPUT_DIR / job_id / "analysis_report.html"
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="报告不存在")
    else:
        report_path = state.report_path
    return FileResponse(report_path, media_type="text/html", filename=f"analysis_report_{job_id}.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
