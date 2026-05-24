#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局LLM客户端工厂 — 一套代码通吃所有大模型
=============================================
支持：OpenAI GPT | DeepSeek | 通义千问(Qwen) | 智谱GLM | Moonshot Kimi
       Ollama本地 | LLaMA(OpenRouter) | 自定义OpenAI兼容中转API

核心能力：
  1. 读取 config/llm_config.json 获取全量提供商配置
  2. auto模式：自动探测环境变量识别当前使用的模型提供商
  3. 单例缓存：全局共享一个 LLM 实例，避免重复创建
  4. CrewAI 原生 LLM 对象，可直接传入 Agent/Crew

使用方式：
  from config.llm_client import get_llm
  llm = get_llm()                        # 自动探测
  llm = get_llm("deepseek")              # 指定提供商
  llm = get_llm("ollama", model="qwen2") # 指定提供商+覆盖模型
"""
import json
import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "llm_config.json"
_llm_instance: Optional[object] = None
_current_provider: str = "unknown"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_provider_config(provider: str) -> dict:
    cfg = _load_config()
    providers = cfg.get("providers", {})
    if provider not in providers:
        available = list(providers.keys())
        raise KeyError(f"未知LLM提供商 '{provider}'，可用: {available}")
    return providers[provider]


def _resolve_api_key(provider_cfg: dict) -> Optional[str]:
    key_env = provider_cfg.get("api_key_env")
    if key_env is None:
        return None
    return os.getenv(key_env)


def auto_detect_provider() -> str:
    """自动探测当前环境配置的LLM提供商"""
    cfg = _load_config()
    providers = cfg.get("providers", {})

    # 1. 按API密钥环境变量探测（最可靠）
    detection_order = ["deepseek", "qwen", "zhipu", "moonshot", "openai"]
    for name in detection_order:
        pcfg = providers.get(name, {})
        key_env = pcfg.get("api_key_env")
        if key_env and os.getenv(key_env):
            logger.info("自动探测 -> %s (检测到 %s)", providers[name]["name"], key_env)
            return name

    # 2. 按 OPENAI_API_BASE 内容特征探测
    api_base = os.getenv("OPENAI_API_BASE", "")
    if "deepseek" in api_base.lower():
        return "deepseek"
    if "dashscope" in api_base.lower():
        return "qwen"
    if "bigmodel" in api_base.lower():
        return "zhipu"
    if "moonshot" in api_base.lower():
        return "moonshot"

    # 3. 检测本地Ollama
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        import urllib.request
        urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=1)
        logger.info("自动探测 -> Ollama本地服务 (%s)", ollama_host)
        return "ollama"
    except Exception:
        pass

    # 4. 有 OPENAI_API_KEY 就默认走 openai
    if os.getenv("OPENAI_API_KEY"):
        logger.info("自动探测 -> OpenAI (检测到 OPENAI_API_KEY)")
        return "openai"

    # 5. 最后兜底 openai（会在实际调用时报错提示配置）
    logger.warning("未检测到任何LLM API密钥，请配置 .env 中的 API_KEY")
    return "openai"


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """
    创建 CrewAI LLM 实例

    Args:
        provider: 提供商名称，None=auto探测，可选: openai/deepseek/qwen/zhipu/moonshot/ollama/llama/custom
        model: 覆盖配置中的模型名称
        temperature: 覆盖默认温度
        max_tokens: 覆盖默认最大token数
        base_url: 覆盖默认API地址
        api_key: 覆盖环境变量中的API密钥

    Returns:
        crewai.LLM 实例
    """
    from crewai import LLM

    cfg = _load_config()
    defaults = cfg.get("default_params", {})

    if provider is None:
        provider = cfg.get("active_provider", "auto")
    if provider == "auto":
        provider = auto_detect_provider()

    pcfg = _get_provider_config(provider)

    resolved_model = model or os.getenv("MODEL_NAME") or pcfg["model"]
    resolved_api_key = api_key or _resolve_api_key(pcfg)
    resolved_base_url = base_url or os.getenv("OPENAI_API_BASE") or pcfg["base_url"]
    resolved_temperature = temperature if temperature is not None else pcfg.get("temperature", defaults.get("temperature", 0.3))
    resolved_max_tokens = max_tokens or pcfg.get("max_tokens", defaults.get("max_tokens", 4096))

    if not resolved_api_key and provider != "ollama":
        logger.warning(
            "%s 的API密钥未配置 (env: %s)，请检查 .env 文件",
            pcfg["name"], pcfg.get("api_key_env", "N/A")
        )

    llm_kwargs = {
        "model": resolved_model,
        "base_url": resolved_base_url,
        "temperature": resolved_temperature,
        "max_tokens": resolved_max_tokens,
    }
    if resolved_api_key:
        llm_kwargs["api_key"] = resolved_api_key

    logger.info(
        "LLM已创建 | 提供商: %s | 模型: %s | base_url: %s",
        pcfg["name"], resolved_model, resolved_base_url
    )

    return LLM(**llm_kwargs)


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
):
    """
    获取全局LLM单例（推荐使用此函数）

    首次调用时创建实例并缓存，后续调用返回同一实例。
    如需不同配置的LLM，直接调用 create_llm()。

    Args:
        provider: 提供商名称，None=auto探测
        model: 覆盖模型名称
        **kwargs: 传递给 create_llm 的其他参数

    Returns:
        crewai.LLM 实例
    """
    global _llm_instance, _current_provider
    if _llm_instance is not None:
        return _llm_instance
    _llm_instance = create_llm(provider=provider, model=model, **kwargs)
    _current_provider = provider or "auto"
    return _llm_instance


def get_llm_info() -> dict:
    """返回当前LLM实例的配置信息"""
    global _llm_instance, _current_provider
    cfg = _load_config()
    provider = _current_provider
    if provider in ("auto", "unknown", None):
        provider = cfg.get("active_provider", "auto")
    if provider == "auto":
        try:
            provider = auto_detect_provider()
        except Exception:
            provider = "unknown"
    pcfg = cfg.get("providers", {}).get(provider, {})
    return {
        "provider": provider,
        "provider_name": pcfg.get("name", "未知"),
        "model": os.getenv("MODEL_NAME") or pcfg.get("model", "unknown"),
        "base_url": os.getenv("OPENAI_API_BASE") or pcfg.get("base_url", ""),
        "has_api_key": bool(_resolve_api_key(pcfg) if pcfg else None),
        "description": pcfg.get("description", ""),
    }


def reset_llm():
    """重置LLM单例缓存（切换模型时使用）"""
    global _llm_instance, _current_provider
    _llm_instance = None
    _current_provider = "unknown"


def list_providers() -> list[dict]:
    """列出所有可用的LLM提供商及其配置"""
    cfg = _load_config()
    result = []
    for key, pcfg in cfg.get("providers", {}).items():
        result.append({
            "id": key,
            "name": pcfg.get("name", key),
            "model": pcfg.get("model", ""),
            "base_url": pcfg.get("base_url", ""),
            "api_key_env": pcfg.get("api_key_env"),
            "configured": bool(_resolve_api_key(pcfg)) if pcfg.get("api_key_env") else (key == "ollama"),
            "description": pcfg.get("description", ""),
        })
    return result
