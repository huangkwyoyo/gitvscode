"""金融指标计算函数的单元测试。"""

import numpy as np
import pandas as pd
import pytest

from app.services.finance_metrics import (
    annualized_return,
    annualized_volatility,
    cumulative_return,
    calculate_returns,
    excess_return,
    information_ratio,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    win_rate_stats,
    drawdown_duration,
    rolling_returns,
    _detect_frequency,
)


@pytest.fixture
def sample_nav():
    """构造一段模拟净值序列（日频，约100个交易日）。"""
    dates = pd.date_range("2023-01-01", periods=100, freq="B")  # 工作日
    np.random.seed(42)
    # 模拟年化约8%、波动率约15%的净值曲线
    daily_return = 0.08 / 252
    daily_vol = 0.15 / np.sqrt(252)
    returns = np.random.normal(daily_return, daily_vol, 100)
    nav_values = (1 + returns).cumprod()
    nav_values = np.insert(nav_values, 0, 1.0)  # 初始净值1.0
    return pd.Series(nav_values[:100], index=dates[:100])


@pytest.fixture
def sample_dates(sample_nav):
    return sample_nav.index.to_series()


@pytest.fixture
def drawdown_nav():
    """构造有明确回撤的净值序列：先涨后跌再恢复。"""
    dates = pd.date_range("2023-01-01", periods=48, freq="B")
    values = (
        [1.0, 1.02, 1.05, 1.08, 1.10, 1.12]  # 涨到1.12（峰值）
        + [1.10, 1.07, 1.04, 1.00, 0.96, 0.94]  # 跌到0.94（谷底，回撤约16%）
        + [0.96, 0.98, 1.00, 1.03, 1.06, 1.09]  # 恢复中
        + [1.12, 1.15, 1.18, 1.20, 1.22, 1.25]  # 新高（确认恢复）
        + [1.25 + i * 0.003 for i in range(24)]  # 延续增长
    )
    return pd.Series(values, index=dates)


class TestCalculateReturns:
    def test_basic_returns(self, sample_nav):
        rets = calculate_returns(sample_nav)
        assert len(rets) == len(sample_nav) - 1
        assert rets.dropna().between(-1, 10).all()  # 收益率应在合理范围内

    def test_constant_nav_returns_zero(self):
        nav = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
        rets = calculate_returns(nav)
        assert (rets == 0).all()


class TestCumulativeReturn:
    def test_simple(self):
        nav = pd.Series([1.0, 1.1, 1.2])
        assert cumulative_return(nav) == pytest.approx(0.2, rel=1e-9)

    def test_loss(self):
        nav = pd.Series([1.0, 0.9, 0.8])
        assert cumulative_return(nav) == pytest.approx(-0.2, rel=1e-9)


class TestAnnualizedReturn:
    def test_positive_return(self, sample_nav, sample_dates):
        ann = annualized_return(sample_nav, sample_dates, frequency="daily")
        assert isinstance(ann, float)
        assert -1 < ann < 10  # 年化收益率应在合理范围内

    def test_constant_nav(self):
        nav = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="B"))
        ann = annualized_return(nav, dates, frequency="daily")
        assert ann == pytest.approx(0.0, abs=0.01)


class TestAnnualizedVolatility:
    def test_positive_volatility(self, sample_nav):
        vol = annualized_volatility(sample_nav, frequency="daily")
        assert vol > 0

    def test_constant_nav_zero_vol(self):
        nav = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
        vol = annualized_volatility(nav, frequency="daily")
        assert vol == 0.0


class TestMaxDrawdown:
    def test_no_draw(self):
        nav = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4])
        dd, _ = max_drawdown(nav)
        assert dd == 0.0

    def test_drawdown_value(self, drawdown_nav):
        dd, _ = max_drawdown(drawdown_nav)
        # 从1.12跌到0.94，回撤约16%
        assert dd < 0
        assert dd > -0.20  # 不应超过20%


class TestDrawdownDuration:
    def test_recovery(self, drawdown_nav):
        dd_series = max_drawdown(drawdown_nav)[1]
        info = drawdown_duration(drawdown_nav, dd_series)
        assert info["drawdown_days"] > 0
        assert info["recovered"] is True
        assert info["recovery_days"] > 0


class TestSharpeRatio:
    def test_positive_sharpe(self, sample_nav, sample_dates):
        sharpe = sharpe_ratio(sample_nav, sample_dates, risk_free_rate=0.03, frequency="daily")
        assert sharpe is not None
        assert isinstance(sharpe, float)

    def test_zero_vol_returns_none(self):
        nav = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="B"))
        assert sharpe_ratio(nav, dates) is None


class TestSortinoRatio:
    def test_sortino_value(self, sample_nav, sample_dates):
        sortino = sortino_ratio(sample_nav, sample_dates, risk_free_rate=0.03, frequency="daily")
        assert sortino is not None

    def test_no_downside_returns_none(self):
        nav = pd.Series([1.0, 1.01, 1.02, 1.03, 1.04])
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="B"))
        assert sortino_ratio(nav, dates) is None


class TestWinRateStats:
    def test_basic_stats(self, sample_nav):
        stats = win_rate_stats(sample_nav, frequency="daily")
        assert "win_rate" in stats
        assert 0 <= stats["win_rate"] <= 1
        assert "total_periods" in stats
        assert stats["total_periods"] > 0

    def test_too_few_data_points(self):
        nav = pd.Series([1.0, 1.01, 1.02])
        assert win_rate_stats(nav) == {}


class TestDetectFrequency:
    def test_daily_frequency(self):
        dates = pd.Series(pd.date_range("2023-01-01", periods=250, freq="B"))
        assert _detect_frequency(dates) == "daily"

    def test_monthly_frequency(self):
        dates = pd.Series(pd.date_range("2023-01-01", periods=12, freq="MS"))
        assert _detect_frequency(dates) == "monthly"

    def test_few_data_points(self):
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="B"))
        assert _detect_frequency(dates) == "daily"  # 数据少时默认日频


class TestExcessReturn:
    def test_excess_return_value(self, sample_nav, sample_dates):
        benchmark = sample_nav * 0.98 + np.random.normal(0, 0.001, len(sample_nav))
        bench_series = pd.Series(benchmark, index=sample_nav.index)
        excess = excess_return(sample_nav, bench_series, sample_dates, frequency="daily")
        assert excess is not None
        assert isinstance(excess, float)

    def test_insufficient_benchmark_data(self, sample_nav, sample_dates):
        bench = pd.Series([1.0, 1.01], index=sample_nav.index[:2])
        assert excess_return(sample_nav, bench, sample_dates) is None


class TestInformationRatio:
    def test_info_ratio_value(self, sample_nav, sample_dates):
        benchmark = sample_nav * 0.99 + np.random.normal(0, 0.002, len(sample_nav))
        bench_series = pd.Series(benchmark, index=sample_nav.index)
        ir = information_ratio(sample_nav, bench_series, sample_dates, frequency="daily")
        assert ir is not None
        assert isinstance(ir, float)

    def test_insufficient_data(self, sample_nav, sample_dates):
        bench = pd.Series([1.0, 1.01], index=sample_nav.index[:2])
        assert information_ratio(sample_nav, bench, sample_dates) is None


class TestRollingReturns:
    def test_multiple_windows(self, sample_nav, sample_dates):
        result = rolling_returns(sample_nav, sample_dates, frequency="daily")
        assert isinstance(result, dict)
        # 100个点，63日窗口应该有数据
        assert len(result) > 0

    def test_too_short_series(self):
        nav = pd.Series([1.0, 1.01, 1.02, 1.03, 1.04])
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="B"))
        result = rolling_returns(nav, dates, frequency="daily")
        assert result == {}  # 数据太少无滚动收益
