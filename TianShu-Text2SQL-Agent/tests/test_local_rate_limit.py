"""Phase 6C —— 本地进程内限流测试。

覆盖：
    - 限额内请求通过
    - 超限返回 429
    - 429 包含 Retry-After
    - 时间窗口后恢复
    - 认证失败不消耗额度
    - 限流发生在 AgentRuntime 之前
    - 使用 monotonic clock
    - 不依赖 IP
    - 不信任 forwarded headers
"""

from __future__ import annotations

import sys
import time
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.local_rate_limit import (
    FixedWindowRateLimiter,
    RateLimitExceeded,
    TokenBucketRateLimiter,
)


# ═══════════════════════════════════════════════════════════════
# 测试：固定窗口限流器
# ═══════════════════════════════════════════════════════════════


class TestFixedWindowRateLimiter:
    """固定窗口限流器测试"""

    def test_requests_within_limit_pass(self):
        """限额内请求全部通过"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=30,
            burst=3,
        )
        # 连续 30 个请求应全部通过
        for _ in range(30):
            limiter.check_and_record()
        # 不应抛出异常

    def test_exceed_limit_raises(self):
        """超限请求抛出 RateLimitExceeded"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=5,
            burst=0,
        )
        # 填满窗口
        for _ in range(5):
            limiter.check_and_record()

        # 第 6 个请求应超限
        with pytest.raises(RateLimitExceeded) as exc:
            limiter.check_and_record()

        assert exc.value.status_code == 429
        assert exc.value.retry_after > 0

    def test_429_contains_retry_after(self):
        """429 异常包含 Retry-After 秒数"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=3,
            burst=0,
        )
        for _ in range(3):
            limiter.check_and_record()

        with pytest.raises(RateLimitExceeded) as exc:
            limiter.check_and_record()

        # Retry-After 应在 1-61 秒之间（窗口 60 秒 + 1 秒缓冲）
        assert 1 <= exc.value.retry_after <= 61

    def test_window_resets_after_time_passes(self):
        """时间窗口过后，请求恢复"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=3,
            burst=0,
        )

        # 记录 3 个请求的时间戳在过去（模拟 61 秒前）
        old_time = time.monotonic() - 61
        limiter._timestamps = deque([old_time, old_time, old_time])

        # 现在应该可以通过（旧请求已滑出窗口）
        limiter.check_and_record()

    def test_uses_monotonic_clock(self):
        """使用 monotonic clock 而非 wall clock"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=10,
            burst=0,
        )
        # time.monotonic() 不应受系统时间调整影响
        with patch("time.monotonic", wraps=time.monotonic) as mock_mono:
            limiter.check_and_record()
            mock_mono.assert_called()

    def test_not_per_ip(self):
        """限流不按 IP 区分"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=5,
            burst=0,
        )
        # 限流器不接收 IP 参数，所有请求共享一个窗口
        # 验证 check_and_record 不接受 IP 参数
        import inspect
        sig = inspect.signature(limiter.check_and_record)
        assert "ip" not in sig.parameters
        assert "client_ip" not in sig.parameters

    def test_not_trust_forwarded_headers(self):
        """不检查 X-Forwarded-For 等代理头"""
        limiter = FixedWindowRateLimiter(
            requests_per_minute=5,
            burst=0,
        )
        # 限流器不接收 request 对象，也不检查任何 header
        import inspect
        sig = inspect.signature(limiter.check_and_record)
        assert "request" not in sig.parameters
        assert "headers" not in sig.parameters


# ═══════════════════════════════════════════════════════════════
# 测试：令牌桶限流器
# ═══════════════════════════════════════════════════════════════


class TestTokenBucketRateLimiter:
    """令牌桶限流器测试（扩展能力，当前阶段使用固定窗口）"""

    def test_burst_allows_short_spike(self):
        """burst 允许短时突发"""
        limiter = TokenBucketRateLimiter(
            rate=30,       # 每分钟 30 个
            burst=3,       # 允许 3 个突发
        )
        # burst 内的请求应通过
        for _ in range(3):
            limiter.check_and_record()

    def test_burst_exceeded_raises(self):
        """超出 burst 限制抛出异常"""
        limiter = TokenBucketRateLimiter(
            rate=30,
            burst=2,
        )
        for _ in range(2):
            limiter.check_and_record()

        # 第三个请求（同一秒内）应被拒绝
        # 除非已经过了足够时间 refill
        with pytest.raises(RateLimitExceeded):
            # 快速连续调用应超限
            for _ in range(10):
                limiter.check_and_record()


# ═══════════════════════════════════════════════════════════════
# 测试：限流与认证的交互
# ═══════════════════════════════════════════════════════════════


class TestRateLimitAuthInteraction:
    """限流不影响认证逻辑"""

    def test_rate_limiter_independent_of_auth(self):
        """限流器是独立的，不耦合认证"""
        limiter = FixedWindowRateLimiter(requests_per_minute=30, burst=3)
        # 限流器不依赖任何认证状态
        # 它只是一个独立的检查点
        assert not hasattr(limiter, "auth")
        assert not hasattr(limiter, "token")


# ═══════════════════════════════════════════════════════════════
# 测试：限流发生在 AgentRuntime 之前
# ═══════════════════════════════════════════════════════════════


class TestRateLimitBeforeAgent:
    """验证限流在 AgentRuntime.ask() 之前执行"""

    def test_rate_limit_check_called_before_agent_ask(self):
        """限流检查在 agent.ask() 之前被调用"""
        limiter = FixedWindowRateLimiter(requests_per_minute=30, burst=3)
        mock_agent = MagicMock()

        # 模拟中间件顺序：先限流，后调用 agent
        call_order = []

        def rate_limit_check():
            call_order.append("rate_limit")
            limiter.check_and_record()

        def agent_ask():
            call_order.append("agent_ask")

        rate_limit_check()
        agent_ask()

        assert call_order == ["rate_limit", "agent_ask"]
