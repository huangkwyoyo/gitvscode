"""
流水线韧性模块：重试机制 + MCP检查点断点续跑
"""
import functools
import time
import json
import os

from src.logger import logger
from src.mcp.context_protocol import mcp


CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
CHECKPOINT_FILE = os.path.join(CHECKPOINT_DIR, "pipeline_checkpoint.json")


def save_checkpoint(task_index: int, task_name: str):
    checkpoint = {
        "task_index": task_index,
        "task_name": task_name,
        "timestamp": time.time(),
        "context_snapshot": {k: str(v)[:500] for k, v in mcp._context.items()}
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    logger.info("检查点已保存: task_%d (%s)", task_index, task_name)


def load_checkpoint() -> dict | None:
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


def retry(max_attempts: int = 3, delay_seconds: int = 5, backoff: float = 2.0):
    """重试装饰器，支持指数退避"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay_seconds
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        logger.warning(
                            "第 %d/%d 次执行失败: %s，%d秒后重试...",
                            attempt, max_attempts, str(e)[:100], current_delay
                        )
                        time.sleep(current_delay)
                        current_delay = int(current_delay * backoff)
                    else:
                        logger.error("已达最大重试次数 %d，最终失败: %s", max_attempts, str(e)[:100])
            raise last_error
        return wrapper
    return decorator
