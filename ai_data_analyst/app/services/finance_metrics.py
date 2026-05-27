"""私募产品分析框架：年化收益率、累计收益率、超额收益率、滚动收益率、年化波动率、最大回撤、回撤持续时间、夏普比率。"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
RISK_FREE_RATE = 0.03
ROLLING_WINDOWS = {"3个月": 63, "6个月": 126, "1年": 252}


def _safe_float(value) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), 6)


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
    """准备按日期排序的净值序列和日期序列，去除缺失值。"""
    df_sorted = df.sort_values(date_col).copy()
    nav = df_sorted.set_index(date_col)[value_col].dropna()
    if len(nav) < 5:
        raise ValueError(f"字段 {value_col} 有效数据点不足 (需 >= 5)")
    if (nav <= 0).any():
        nav = nav.clip(lower=1e-10)
    return nav, nav.index.to_series().sort_values()


def calculate_returns(nav: pd.Series) -> pd.Series:
    """计算日收益率序列。"""
    return nav.pct_change().dropna()


def annualized_return(nav: pd.Series, dates: pd.Series) -> float:
    """年化收益率 = (期末净值/期初净值)^(365/区间天数) - 1"""
    days = (dates.iloc[-1] - dates.iloc[0]).days
    if days <= 0:
        return 0.0
    total_return = nav.iloc[-1] / nav.iloc[0]
    if total_return <= 0:
        return -1.0
    return float((total_return ** (365.0 / days)) - 1)


def cumulative_return(nav: pd.Series) -> float:
    """累计收益率 = 期末净值/期初净值 - 1"""
    return float(nav.iloc[-1] / nav.iloc[0] - 1)


def excess_return(nav: pd.Series, benchmark: pd.Series, dates: pd.Series) -> float | None:
    """超额收益率 = 组合年化收益率 - 基准年化收益率"""
    bench_aligned = benchmark.reindex(nav.index).dropna()
    if len(bench_aligned) < 5:
        return None
    common_idx = nav.index.intersection(bench_aligned.index)
    if len(common_idx) < 5:
        return None
    port_ann = annualized_return(nav.loc[common_idx], dates.loc[common_idx])
    bench_ann = annualized_return(bench_aligned.loc[common_idx], dates.loc[common_idx])
    return port_ann - bench_ann


def rolling_returns(nav: pd.Series, dates: pd.Series) -> dict[str, list[dict]]:
    """计算多窗口滚动收益率序列，用于绘制滚动收益曲线。"""
    result = {}
    for label, window in ROLLING_WINDOWS.items():
        if len(nav) <= window:
            continue
        roll = nav.pct_change(periods=window).dropna()
        if len(roll) == 0:
            continue
        roll_dates = dates.iloc[window:].reset_index(drop=True)
        result[label] = [
            {"date": str(d.date()), "value": _safe_float(v)}
            for d, v in zip(roll_dates, roll)
            if _safe_float(v) is not None
        ]
    return result


def annualized_volatility(nav: pd.Series) -> float:
    """年化波动率 = 日收益率标准差 * sqrt(252)"""
    rets = calculate_returns(nav)
    if len(rets) < 2:
        return 0.0
    return float(rets.std() * np.sqrt(TRADING_DAYS))


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
    peak_idx = running_max.loc[:max_dd_end_idx].idxmax()

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
        "max_drawdown": _safe_float(max_dd),
        "peak_date": peak_date,
        "trough_date": trough_date,
        "recovery_date": recovery_date,
        "drawdown_days": int(drawdown_days),
        "recovery_days": recovery_days if recovery_days is None else int(recovery_days),
        "recovered": recovery_date is not None,
    }


def sharpe_ratio(nav: pd.Series, dates: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float | None:
    """夏普比率 = (年化收益率 - 无风险利率) / 年化波动率"""
    ann_ret = annualized_return(nav, dates)
    ann_vol = annualized_volatility(nav)
    if ann_vol == 0 or ann_vol is None:
        return None
    return float((ann_ret - risk_free_rate) / ann_vol)


def compute_finance_metrics(
    df: pd.DataFrame,
    date_col: str,
    value_cols: list[str],
    benchmark_col: str | None = None,
) -> dict:
    """计算所有8项金融指标，返回结构化结果。"""
    results: dict[str, dict] = {}

    for col in value_cols:
        try:
            nav, dates = _prepare_series(df, date_col, col)
        except ValueError:
            continue

        returns = calculate_returns(nav)
        ann_ret = annualized_return(nav, dates)
        cum_ret = cumulative_return(nav)
        ann_vol = annualized_volatility(nav)
        max_dd, dd_series = max_drawdown(nav)
        dd_info = drawdown_duration(nav, dd_series)
        sharpe = sharpe_ratio(nav, dates)
        rolling = rolling_returns(nav, dates)

        metrics = {
            "field": col,
            "data_points": len(nav),
            "start_date": str(dates.iloc[0].date()),
            "end_date": str(dates.iloc[-1].date()),
            "annualized_return": _safe_float(ann_ret),
            "cumulative_return": _safe_float(cum_ret),
            "annualized_volatility": _safe_float(ann_vol),
            "sharpe_ratio": _safe_float(sharpe) if sharpe is not None else None,
            "max_drawdown": _safe_float(max_dd),
            "drawdown_info": dd_info,
            "rolling_returns": rolling,
            "cumulative_curve": [
                {"date": str(d.date()), "value": _safe_float(nav.iloc[i] / nav.iloc[0] - 1)}
                for i, d in enumerate(dates)
            ],
            "drawdown_curve": [
                {"date": str(d.date()), "value": _safe_float(dd_series.iloc[i])}
                for i, d in enumerate(dates)
            ],
        }

        if benchmark_col and benchmark_col in df.columns:
            bench_nav = df.set_index(date_col)[benchmark_col].dropna()
            excess = excess_return(nav, bench_nav, dates)
            metrics["excess_return"] = _safe_float(excess) if excess is not None else None
            metrics["benchmark_field"] = benchmark_col

        calmar = None
        if ann_ret is not None and max_dd != 0 and abs(max_dd) > 1e-10:
            calmar = ann_ret / abs(max_dd)
        metrics["calmar_ratio"] = _safe_float(calmar) if calmar is not None else None

        results[col] = metrics

    return results
