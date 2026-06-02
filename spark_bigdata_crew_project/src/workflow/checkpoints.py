"""
工作流检查点模块
支持状态持久化、断点续跑、Gate审批状态记录
"""
import json
import os
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "output", "checkpoints"
)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "artifacts"
)
os.makedirs(ARTIFACT_DIR, exist_ok=True)


def save_state(run_id: str, state: dict) -> None:
    """持久化工作流状态"""
    filepath = os.path.join(CHECKPOINT_DIR, f"{run_id}_state.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    logger.info("状态已保存: %s", filepath)


def load_state(run_id: str) -> Optional[dict]:
    """加载工作流状态"""
    filepath = os.path.join(CHECKPOINT_DIR, f"{run_id}_state.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_gate_approval(run_id: str, gate_id: str, approved: bool, approver: str = "", comment: str = "") -> None:
    """记录Gate审批结果"""
    record = {
        "run_id": run_id,
        "gate_id": gate_id,
        "approved": approved,
        "approver": approver,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
    }
    filepath = os.path.join(CHECKPOINT_DIR, f"{run_id}_gate_{gate_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    status = "通过" if approved else "驳回"
    logger.info("Gate审批 [%s]: %s (审批人: %s)", gate_id, status, approver or "未指定")


def save_artifact(run_id: str, name: str, content: str) -> str:
    """保存交付物"""
    filepath = os.path.join(ARTIFACT_DIR, f"{run_id}_{name}")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("交付物已归档: %s", filepath)
    return filepath


def list_artifacts(run_id: str) -> list:
    """列出某次运行的所有交付物"""
    if not os.path.exists(ARTIFACT_DIR):
        return []
    return sorted([
        f for f in os.listdir(ARTIFACT_DIR)
        if f.startswith(run_id)
    ])


def list_runs() -> list:
    """列出所有历史运行"""
    if not os.path.exists(CHECKPOINT_DIR):
        return []
    runs = set()
    for f in os.listdir(CHECKPOINT_DIR):
        if f.endswith("_state.json"):
            runs.add(f.replace("_state.json", ""))
    return sorted(runs, reverse=True)
