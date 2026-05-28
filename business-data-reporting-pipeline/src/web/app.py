#!/usr/bin/env python3
"""FastAPI Web 服务：提供数据上传、管道运行和报告查看功能。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import uvicorn
import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import load_config
from src.pipeline import run_pipeline

# 项目根目录及各关键路径
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "default.yaml"
RAW_DATA_DIR = ROOT / "data" / "raw"
REPORT_PATH = ROOT / "reports" / "output" / "report.html"

app = FastAPI(title="业务数据分析")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/reports", StaticFiles(directory=ROOT / "reports"), name="reports")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """渲染主页：展示配置文件信息，判断报告是否已存在。"""
    config = load_config(CONFIG_PATH)
    report_exists = REPORT_PATH.exists()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "report_exists": report_exists,
            "report_url": "/reports/output/report.html" if report_exists else None,
        },
    )


@app.post("/run", response_class=HTMLResponse)
async def run_report(
    request: Request,
    source_file: Annotated[UploadFile | None, File()] = None,
    enable_llm: Annotated[bool, Form()] = False,
    title: Annotated[str, Form()] = "业务数据分析报告",
) -> HTMLResponse:
    """处理分析请求：接收文件上传、修改配置、运行管道并返回结果页面。"""
    config = load_config(CONFIG_PATH)
    config["report"]["title"] = title
    config["llm"]["enabled"] = enable_llm

    # 若提供了文件，则校验格式并保存到原始数据目录
    if source_file and source_file.filename:
        suffix = Path(source_file.filename).suffix.lower()
        if suffix not in {".csv", ".xlsx", ".xls"}:
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "config": config,
                    "report_exists": REPORT_PATH.exists(),
                    "report_url": "/reports/output/report.html" if REPORT_PATH.exists() else None,
                    "error": "仅支持 CSV、XLSX、XLS 文件。",
                },
                status_code=400,
            )

        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        upload_path = RAW_DATA_DIR / f"uploaded{suffix}"
        with upload_path.open("wb") as file:
            shutil.copyfileobj(source_file.file, file)
        config["input"]["path"] = str(upload_path.relative_to(ROOT))
        config["input"]["source_type"] = "excel" if suffix in {".xlsx", ".xls"} else "csv"

    # 将当前配置写为运行时配置，执行管道
    run_config_path = ROOT / "configs" / "web_run.yaml"
    run_config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report_path = run_pipeline(run_config_path)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "config": config,
            "report_exists": True,
            "report_url": f"/reports/output/{report_path.name}",
            "success": "报告已生成。",
        },
    )


@app.get("/report")
def report() -> RedirectResponse:
    """重定向到生成的报告页面。"""
    return RedirectResponse("/reports/output/report.html")


def run_web_app(host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动 FastAPI 服务。"""
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)

