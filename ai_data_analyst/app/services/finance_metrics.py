"""私募产品分析框架：年化收益率、累计收益率、超额收益率、滚动收益率、年化波动率、最大回撤、回撤持续时间、夏普比率、索提诺比率、信息比率。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.utils import safe_float
from app.settings import RISK_FREE_RATE, ROLLING_WINDOWS, TRADING_DAYS

# 频率检测的交易日阈值（年交易日数的容忍区间）
FREQUENCY_THRESHOLDS = {
    "daily": (200, 260),       # 日频：200-260 天/年
    "weekly": (40, 60),        # 周频：40-60 天/年
    "monthly": (10, 14),       # 月频：10-14 天/年
}
# 各频率对应的年化乘数
FREQUENCY_MULTIPLIER = {
    "daily": 252,
    "weekly": 52,
    "monthly": 12,
}



def _detect_frequency(dates: pd.Series) -> str:
    """根据日期序列的分布密度自动检测数据频率。

    通过计算平均每年的有效数据点数来区分日频/周频/月频。
    """
    if len(dates) < 10:
        return "daily"  # 数据太少时默认日频

    start = pd.Timestamp(dates.iloc[0])
    end = pd.Timestamp(dates.iloc[-1])
    years = (end - start).days / 365.25
    if years <= 0:
        return "daily"

    avg_per_year = len(dates) / years

    for freq, (low, high) in FREQUENCY_THRESHOLDS.items():
        if low <= avg_per_year <= high:
            return freq

    # 超出日频范围（数据非常密集）仍按日频处理
    if avg_per_year > FREQUENCY_THRESHOLDS["daily"][1]:
        return "daily"

    # 低于月频范围（季度/半年度）按 4 次年化处理
    return "quarterly"


def _get_trading_days(frequency: str) -> int:
    """根据频率返回对应的年化交易日乘数。"""
    if frequency in FREQUENCY_MULTIPLIER:
        return FREQUENCY_MULTIPLIER[frequency]
    # 季度频等特殊频率使用 4 次/年
    return 4


def detect_time_series(df: pd.DataFrame) -> tuple[str | None, list[str], str | None]:
    """自动检测时间序列数据，返回 (日期列, 净值候选列列表, 基准列)。"""
    date_col = None
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_col = col
            break
    if date_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(hint in col_lower for hint in ["date", "time", "日期", "时间"]):
                try:
                    converted = pd.to_datetime(df[col], errors="coerce")
                    if converted.notna().sum() / len(df) > 0.8:
                        date_col = col
                        break
                except Exception:
                    pass
    if date_col is None:
        return None, [], None

    nav_candidates = []
    for col in df.columns:
        if col == date_col:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if df[col].nunique() < 3:
            continue
        nav_candidates.append(col)

    benchmark_col = None
    for col in nav_candidates:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ["benchmark", "基准", "index", "指数", "hs300", "csi300", "沪深300"]):
            benchmark_col = col
            break

    return date_col, nav_candidates, benchmark_col


def _prepare_series(df: pd.DataFrame, date_col: str, value_col: str) -> tuple[pd.Series, pd.Series]:
    """准备按日期排序的净值序列和日期序列，去除缺失值。

    净值必须为正数，否则抛出异常（负净值会导致收益率计算完全失真）。
    """
    df_sorted = df.sort_values(date_col).copy()
    nav = df_sorted.set_index(date_col)[value_col].dropna()
    if len(nav) < 5:
        raise ValueError(f"字段 {value_col} 有效数据点不足 (需 >= 5)")
    if (nav <= 0).any():
        raise ValueError(f"字段 {value_col} 包含非正净值，无法计算收益率")
    return nav, nav.index.to_series().sort_values()


def calculate_returns(nav: pd.Series) -> pd.Series:
    """计算收益率序列。"""
    return nav.pct_change().dropna()


def annualized_return(nav: pd.Series, dates: pd.Series, frequency: str | None = None) -> float:
    """年化收益率：优先按真实日期跨度计算，日期解析失败时回退到频率乘数法。"""
    if frequency is None:
        frequency = _detect_frequency(dates)

    total_return = nav.iloc[-1] / nav.iloc[0]
    if total_return <= 0:
        return -1.0

    try:
        start = pd.Timestamp(dates.iloc[0])
        end = pd.Timestamp(dates.iloc[-1])
        years = (end - start).days / 365
        if years > 0:
            return float((total_return ** (1 / years)) - 1)
    except Exception:
        pass

    periods = max(len(nav) - 1, 1)
    ann_mult = _get_trading_days(frequency)
    return float((total_return ** (ann_mult / periods)) - 1)

def cumulative_return(nav: pd.Series) -> float:
    """累计收益率 = 期末净值/期初净值 - 1"""
    return float(nav.iloc[-1] / nav.iloc[0] - 1)


def excess_return(nav: pd.Series, benchmark: pd.Series, dates: pd.Series, frequency: str | None = None) -> float | None:
    """超额收益率 = 组合年化收益率 - 基准年化收益率"""
    bench_aligned = benchmark.reindex(nav.index).dropna()
    if len(bench_aligned) < 5:
        return None
    common_idx = nav.index.intersection(bench_aligned.index)
    if len(common_idx) < 5:
        return None
    port_ann = annualized_return(nav.loc[common_idx], dates.loc[common_idx], frequency)
    bench_ann = annualized_return(bench_aligned.loc[common_idx], dates.loc[common_idx], frequency)
    return port_ann - bench_ann


def rolling_returns(nav: pd.Series, dates: pd.Series, frequency: str | None = None) -> dict[str, list[dict]]:
    """计算多窗口滚动收益率序列，用于绘制滚动收益曲线。

    窗口大小根据数据频率自动缩放（周频/月频时按交易日比例缩减窗口）。
    """
    if frequency is None:
        frequency = _detect_frequency(dates)
    freq_mult = _get_trading_days(frequency) / TRADING_DAYS

    result = {}
    for label, daily_window in ROLLING_WINDOWS.items():
        window = max(3, int(daily_window * freq_mult))
        if len(nav) <= window:
            continue
        roll = nav.pct_change(periods=window).dropna()
        if len(roll) == 0:
            continue
        # 使用 nav 的索引作为日期，与 roll 的长度严格对齐
        roll_dates = nav.index[-len(roll):]
        result[label] = [
            {"date": str(d.date()), "value": safe_float(v)}
            for d, v in zip(roll_dates, roll)
            if safe_float(v) is not None
        ]
    return result


def annualized_volatility(nav: pd.Series, frequency: str | None = None) -> float:
    """年化波动率 = 收益率标准差 * sqrt(年化乘数)"""
    if frequency is None:
        frequency = _detect_frequency(nav.index.to_series())
    ann_mult = _get_trading_days(frequency)

    rets = calculate_returns(nav)
    if len(rets) < 2:
        return 0.0
    return float(rets.std() * np.sqrt(ann_mult))


def max_drawdown(nav: pd.Series) -> tuple[float, pd.Series]:
    """最大回撤及回撤序列。返回 (最大回撤值, 回撤序列)。"""
    cumulative = nav / nav.iloc[0]
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_dd = float(drawdown.min())
    return max_dd, drawdown


def drawdown_duration(nav: pd.Series, drawdown_series: pd.Series) -> dict:
    """回撤持续时间分析：最大回撤的起止日期、持续天数、恢复天数。"""
    max_dd = drawdown_series.min()
    max_dd_end_idx = drawdown_series.idxmin()

    cumulative = nav / nav.iloc[0]
    running_max = cumulative.cummax()

    # 在等值平台期选择最接近谷底的峰值索引（需严格在谷底之前）
    peak_values = running_max.loc[:max_dd_end_idx]
    peak_idx = peak_values.idxmax()
    max_val = peak_values.max()
    all_peaks = peak_values[peak_values == max_val]
    if len(all_peaks) > 1:
        # 排除谷底索引本身，取最后一个严格在谷底之前的峰值
        candidates = all_peaks.index[all_peaks.index < max_dd_end_idx]
        if len(candidates) > 0:
            peak_idx = candidates[-1]
        else:
            peak_idx = all_peaks.index[-2] if len(all_peaks) > 1 else all_peaks.index[0]

    def _fmt_date(idx) -> str:
        try:
            return str(pd.Timestamp(idx).date())
        except Exception:
            return str(idx)

    peak_date = _fmt_date(peak_idx)
    trough_date = _fmt_date(max_dd_end_idx)

    drawdown_days = (max_dd_end_idx - peak_idx).days

    recovery_days = None
    recovery_date = None
    peak_value = cumulative.loc[peak_idx]
    future = cumulative.loc[max_dd_end_idx:]
    recovered = future[future >= peak_value]
    if len(recovered) > 0:
        recovery_idx = recovered.index[0]
        recovery_days = (recovery_idx - max_dd_end_idx).days
        recovery_date = _fmt_date(recovery_idx)

    return {
        "max_drawdown": safe_float(max_dd),
        "peak_date": peak_date,
        "trough_date": trough_date,
        "recovery_date": recovery_date,
        "drawdown_days": int(drawdown_days),
        "recovery_days": int(recovery_days) if recovery_days is not None else None,
        "recovered": recovery_date is not None,
    }


def sharpe_ratio(nav: pd.Series, dates: pd.Series, risk_free_rate: float = RISK_FREE_RATE, frequency: str | None = None) -> float | None:
    """夏普比率 = (年化收益率 - 无风险利率) / 年化波动率"""
    ann_ret = annualized_return(nav, dates, frequency)
    ann_vol = annualized_volatility(nav, frequency)
    if ann_vol == 0:
        return None
    return float((ann_ret - risk_free_rate) / ann_vol)


def sortino_ratio(nav: pd.Series, dates: pd.Series, risk_free_rate: float = RISK_FREE_RATE, frequency: str | None = None) -> float | None:
    """索提诺比率 = (年化收益率 - 无风险利率) / 下行波动率

    下行波动率采用标准定义：将正收益替换为零，对含零的全序列求标准差后年化。
    这与业界通用做法一致——分子分母使用相同的观测数，避免只取负收益子集导致 std 偏高。
    """
    if frequency is None:
        frequency = _detect_frequency(dates)
    ann_mult = _get_trading_days(frequency)

    ann_ret = annualized_return(nav, dates, frequency)
    rets = calculate_returns(nav)
    if len(rets) < 2:
        return None

    # 下行序列：正收益置零，负收益保留原值
    downside_series = rets.clip(upper=0)
    downside_std = downside_series.std(ddof=1) * np.sqrt(ann_mult)
    if downside_std == 0:
        return None
    return float((ann_ret - risk_free_rate) / downside_std)


def information_ratio(nav: pd.Series, benchmark: pd.Series, dates: pd.Series, frequency: str | None = None) -> float | None:
    """信息比率 = 平均超额收益 / 跟踪误差

    衡量组合相对基准的主动管理效率。
    """
    bench_aligned = benchmark.reindex(nav.index).dropna()
    if len(bench_aligned) < 10:
        return None
    common_idx = nav.index.intersection(bench_aligned.index)
    if len(common_idx) < 10:
        return None

    nav_common = nav.loc[common_idx]
    bench_common = bench_aligned.loc[common_idx]

    # 计算每日超额收益
    active_returns = nav_common.pct_change() - bench_common.pct_change()
    active_returns = active_returns.dropna()

    if len(active_returns) < 10:
        return None

    tracking_error = active_returns.std() * np.sqrt(_get_trading_days(frequency or "daily"))
    if tracking_error == 0:
        return None

    mean_active = active_returns.mean() * _get_trading_days(frequency or "daily")
    return float(mean_active / tracking_error)


def win_rate_stats(nav: pd.Series, frequency: str | None = None) -> dict:
    """计算胜率统计：交易日胜率、盈亏比、平均盈利/亏损。

    帮助投资者了解产品的收益分布特征。
    """
    rets = calculate_returns(nav)
    if len(rets) < 5:
        return {}

    positive = rets[rets > 0]
    negative = rets[rets < 0]

    win_rate = len(positive) / len(rets) if len(rets) > 0 else 0
    avg_win = positive.mean() if len(positive) > 0 else 0
    avg_loss = abs(negative.mean()) if len(negative) > 0 else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else None

    return {
        "win_rate": round(win_rate, 4),
        "total_periods": len(rets),
        "winning_periods": len(positive),
        "losing_periods": len(negative),
        "avg_win": safe_float(avg_win),
        "avg_loss": safe_float(avg_loss),
        "profit_loss_ratio": safe_float(profit_loss_ratio) if profit_loss_ratio is not None else None,
    }


def compute_finance_metrics(
    df: pd.DataFrame,
    date_col: str,
    value_cols: list[str],
    benchmark_col: str | None = None,
    errors: list[str] | None = None,
) -> dict:
    """计算所有金融指标，返回结构化结果。

    支持自动频率检测，覆盖日频/周频/月频净值数据。
    """
    results: dict[str, dict] = {}

    for col in value_cols:
        try:
            nav, dates = _prepare_series(df, date_col, col)
        except ValueError as exc:
            if errors is not None:
                errors.append(f"金融指标 {col}: {exc}")
            continue

        frequency = _detect_frequency(dates)

        returns = calculate_returns(nav)
        ann_ret = annualized_return(nav, dates, frequency)
        cum_ret = cumulative_return(nav)
        ann_vol = annualized_volatility(nav, frequency)
        max_dd, dd_series = max_drawdown(nav)
        dd_info = drawdown_duration(nav, dd_series)
        sharpe = sharpe_ratio(nav, dates, frequency=frequency)
        sortino = sortino_ratio(nav, dates, frequency=frequency)
        rolling = rolling_returns(nav, dates, frequency)
        win_stats = win_rate_stats(nav, frequency)

        metrics = {
            "field": col,
            "data_points": len(nav),
            "start_date": str(dates.iloc[0].date()),
            "end_date": str(dates.iloc[-1].date()),
            "frequency": frequency,
            "annualized_return": safe_float(ann_ret),
            "cumulative_return": safe_float(cum_ret),
            "annualized_volatility": safe_float(ann_vol),
            "sharpe_ratio": safe_float(sharpe) if sharpe is not None else None,
            "sortino_ratio": safe_float(sortino) if sortino is not None else None,
            "max_drawdown": safe_float(max_dd),
            "drawdown_info": dd_info,
            "rolling_returns": rolling,
            "win_rate_stats": win_stats,
            "cumulative_curve": [
                {"date": str(d.date()), "value": safe_float(nav.iloc[i] / nav.iloc[0] - 1)}
                for i, d in enumerate(dates)
            ],
            "drawdown_curve": [
                {"date": str(d.date()), "value": safe_float(dd_series.iloc[i])}
                for i, d in enumerate(dates)
            ],
        }

        if benchmark_col and benchmark_col in df.columns:
            try:
                bench_nav = df.set_index(date_col)[benchmark_col].dropna()
                excess = excess_return(nav, bench_nav, dates, frequency)
                metrics["excess_return"] = safe_float(excess) if excess is not None else None
                metrics["benchmark_field"] = benchmark_col

                info_ratio = information_ratio(nav, bench_nav, dates, frequency)
                metrics["information_ratio"] = safe_float(info_ratio) if info_ratio is not None else None
            except Exception as bench_exc:
                if errors is not None:
                    errors.append(f"基准对比 {col}: {bench_exc}")

        calmar = None
        if ann_ret is not None and max_dd != 0 and abs(max_dd) > 1e-10:
            calmar = ann_ret / abs(max_dd)
        metrics["calmar_ratio"] = safe_float(calmar) if calmar is not None else None

        results[col] = metrics

    return results
