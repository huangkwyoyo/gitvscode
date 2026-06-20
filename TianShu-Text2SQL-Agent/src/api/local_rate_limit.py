"""Phase 6C —— 本地进程内请求频率限制。

职责：
    1. 单进程全局内存型限流
    2. 认证成功后执行限流
    3. 限流在 AgentRuntime.ask() 之前
    4. 超限返回 429 + Retry-After
    5. 使用 monotonic clock（不受系统时间调整影响）

限制：
    - 不按 IP 区分调用方
    - 不信任 X-Forwarded-For
    - 不宣称支持多 worker 或分布式限流
    - 保留 Phase 6B 的 lock 和 queue timeout
"""

from __future__ import annotations

import logging
import time
from collections import deque

logger = logging.getLogger("tianshu.api.rate_limit")


class RateLimitExceeded(Exception):
    """请求频率超限异常。

    属性：
        status_code: HTTP 429
        retry_after: 建议重试等待秒数
    """

    def __init__(self, retry_after: int = 5):
        self.status_code = 429
        self.retry_after = retry_after
        super().__init__(f"请求频率超限，请在 {retry_after} 秒后重试")


class FixedWindowRateLimiter:
    """固定窗口限流器。

    使用滑动窗口记录请求时间戳（进程内内存），
    不使用 Redis 或外部存储。

    算法：
        - 记录每个请求的 monotonic 时间戳
        - 每次检查时清理窗口外的旧时间戳
        - 窗口内请求数 >= 限额 + burst 时拒绝

    使用方式：
        limiter = FixedWindowRateLimiter(requests_per_minute=30, burst=3)
        try:
            limiter.check_and_record()
        except RateLimitExceeded as e:
            return JSONResponse(status_code=429, headers={"Retry-After": str(e.retry_after)})
    """

    def __init__(self, requests_per_minute: int = 30, burst: int = 3):
        self._rpm = max(1, requests_per_minute)
        self._burst = max(0, burst)
        self._window_seconds = 60.0
        # 使用 deque 记录请求时间戳（monotonic seconds）
        self._timestamps: deque[float] = deque()

    @property
    def requests_per_minute(self) -> int:
        return self._rpm

    @property
    def burst(self) -> int:
        return self._burst

    def check_and_record(self) -> None:
        """检查是否超限，未超限则记录本次请求。

        Raises:
            RateLimitExceeded: 请求频率超限
        """
        now = time.monotonic()

        # ── 清理窗口外的旧时间戳 ──
        window_start = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()

        # ── 检查是否超限 ──
        limit = self._rpm + self._burst
        if len(self._timestamps) >= limit:
            # 计算建议重试时间（基于最早的时间戳）
            oldest = self._timestamps[0]
            retry_after = max(1, int(self._window_seconds - (now - oldest)) + 1)
            logger.warning(
                "请求频率超限：当前窗口内 %d 个请求（限额 %d + burst %d），建议 %d 秒后重试",
                len(self._timestamps), self._rpm, self._burst, retry_after,
            )
            raise RateLimitExceeded(retry_after=retry_after)

        # ── 记录本次请求 ──
        self._timestamps.append(now)


class TokenBucketRateLimiter:
    """令牌桶限流器（扩展能力）。

    当前阶段默认使用 FixedWindowRateLimiter。
    此实现供将来切换或对比使用。

    算法：
        - 令牌以 rate/60 每秒的速度补充
        - 桶容量 = burst
        - 每次请求消耗 1 个令牌
        - 令牌不足时拒绝
    """

    def __init__(self, rate: int = 30, burst: int = 3):
        self._rate = max(1, rate)          # 每分钟请求数
        self._burst = max(1, burst)        # 桶容量（最大突发）
        self._tokens = float(burst)        # 当前令牌数
        self._last_refill = time.monotonic()  # 上次补充时间

    @property
    def requests_per_minute(self) -> int:
        return self._rate

    @property
    def burst(self) -> int:
        return self._burst

    def check_and_record(self) -> None:
        """检查令牌是否足够，足够则消耗 1 个。

        Raises:
            RateLimitExceeded: 令牌不足
        """
        now = time.monotonic()

        # ── 补充令牌 ──
        elapsed = now - self._last_refill
        refill_amount = elapsed * (self._rate / 60.0)
        self._tokens = min(float(self._burst), self._tokens + refill_amount)
        self._last_refill = now

        # ── 检查令牌 ──
        if self._tokens < 1.0:
            # 计算需要等待的时间
            wait_time = max(1, int((1.0 - self._tokens) / (self._rate / 60.0)) + 1)
            logger.warning(
                "令牌桶限流：当前令牌 %.2f（容量 %d），建议 %d 秒后重试",
                self._tokens, self._burst, wait_time,
            )
            raise RateLimitExceeded(retry_after=wait_time)

        # ── 消耗 1 个令牌 ──
        self._tokens -= 1.0


def create_rate_limiter(
    enabled: bool = True,
    requests_per_minute: int = 30,
    burst: int = 3,
) -> FixedWindowRateLimiter | None:
    """工厂函数：根据配置创建限流器。

    Args:
        enabled: 是否启用限流
        requests_per_minute: 每分钟请求限额
        burst: 突发容量

    Returns:
        FixedWindowRateLimiter 实例，未启用时返回 None
    """
    if not enabled:
        return None

    return FixedWindowRateLimiter(
        requests_per_minute=requests_per_minute,
        burst=burst,
    )
