from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


CANVAS = (960, 560)
BG = "#ffffff"
INK = "#17202a"
MUTED = "#637381"
GRID = "#d9dee5"
BLUE = "#275f7f"
TEAL = "#3d8b7d"
RED = "#b75b5b"


def create_charts(
    dataframe: pd.DataFrame,
    analysis_result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Path]:
    figures_dir = Path(config["report"]["figures_dir"])
    figures_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}
    correlation = analysis_result.get("correlation")
    if isinstance(correlation, pd.DataFrame) and not correlation.empty:
        path = figures_dir / "correlation_heatmap.png"
        _draw_heatmap(correlation, path, "Correlation Heatmap")
        outputs["correlation_heatmap"] = path

    if "region" in dataframe.columns and "revenue" in dataframe.columns:
        path = figures_dir / "revenue_by_region.png"
        region_revenue = dataframe.groupby("region")["revenue"].sum().sort_values(ascending=False)
        _draw_bar_chart(region_revenue, path, "Revenue by Region", "Revenue")
        outputs["revenue_by_region"] = path

    if "category" in dataframe.columns and "revenue" in dataframe.columns:
        path = figures_dir / "revenue_by_category.png"
        category_revenue = dataframe.groupby("category")["revenue"].sum().sort_values(ascending=False)
        _draw_bar_chart(category_revenue, path, "Revenue by Category", "Revenue")
        outputs["revenue_by_category"] = path

    numeric_columns = list(dataframe.select_dtypes(include="number").columns)
    max_columns = config["analysis"]["distributions"].get("max_columns", 12)
    for column in numeric_columns[:max_columns]:
        path = figures_dir / f"distribution_{column}.png"
        _draw_histogram(dataframe[column].dropna(), path, f"Distribution of {column}")
        outputs[f"distribution_{column}"] = path

    return outputs


def _new_canvas(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw, ImageFont.ImageFont]:
    image = Image.new("RGB", CANVAS, BG)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((36, 28), title, fill=INK, font=font)
    return image, draw, font


def _draw_bar_chart(series: pd.Series, path: Path, title: str, ylabel: str) -> None:
    image, draw, font = _new_canvas(title)
    left, top, right, bottom = 92, 88, 910, 470
    draw.rectangle((left, top, right, bottom), outline=GRID)
    draw.text((36, 255), ylabel, fill=MUTED, font=font)

    if series.empty:
        image.save(path)
        return

    values = series.astype(float)
    max_value = max(values.max(), 1.0)
    gap = 18
    bar_width = max(20, int((right - left - gap * (len(values) + 1)) / len(values)))

    for index, (label, value) in enumerate(values.items()):
        x0 = left + gap + index * (bar_width + gap)
        x1 = x0 + bar_width
        bar_height = int((bottom - top - 36) * value / max_value)
        y0 = bottom - bar_height
        draw.rectangle((x0, y0, x1, bottom), fill=BLUE)
        draw.text((x0, bottom + 12), str(label)[:12], fill=INK, font=font)
        draw.text((x0, y0 - 16), f"{value:,.0f}", fill=MUTED, font=font)

    image.save(path)


def _draw_histogram(series: pd.Series, path: Path, title: str) -> None:
    image, draw, font = _new_canvas(title)
    left, top, right, bottom = 92, 88, 910, 470
    draw.rectangle((left, top, right, bottom), outline=GRID)

    if series.empty:
        image.save(path)
        return

    values = series.astype(float)
    bins = min(12, max(4, int(len(values) ** 0.5)))
    counts = pd.cut(values, bins=bins).value_counts(sort=False)
    max_count = max(int(counts.max()), 1)
    gap = 8
    bar_width = max(16, int((right - left - gap * (len(counts) + 1)) / len(counts)))

    for index, (bucket, count) in enumerate(counts.items()):
        x0 = left + gap + index * (bar_width + gap)
        x1 = x0 + bar_width
        bar_height = int((bottom - top - 36) * int(count) / max_count)
        y0 = bottom - bar_height
        draw.rectangle((x0, y0, x1, bottom), fill=TEAL)
        label = f"{bucket.left:.0f}-{bucket.right:.0f}"
        draw.text((x0, bottom + 12), label[:10], fill=INK, font=font)
        draw.text((x0, y0 - 16), str(int(count)), fill=MUTED, font=font)

    image.save(path)


def _draw_heatmap(dataframe: pd.DataFrame, path: Path, title: str) -> None:
    image, draw, font = _new_canvas(title)
    columns = list(dataframe.columns)
    if not columns:
        image.save(path)
        return

    left, top = 180, 96
    size = max(34, min(68, int(680 / len(columns))))

    for row_index, row_name in enumerate(columns):
        draw.text((40, top + row_index * size + 12), str(row_name)[:18], fill=INK, font=font)
        for col_index, col_name in enumerate(columns):
            value = float(dataframe.loc[row_name, col_name])
            color = _correlation_color(value)
            x0 = left + col_index * size
            y0 = top + row_index * size
            draw.rectangle((x0, y0, x0 + size, y0 + size), fill=color, outline=BG)
            draw.text((x0 + 8, y0 + size // 2 - 5), f"{value:.2f}", fill=INK, font=font)

    for col_index, column in enumerate(columns):
        draw.text((left + col_index * size, top - 22), str(column)[:10], fill=INK, font=font)

    image.save(path)


def _correlation_color(value: float) -> str:
    value = max(-1.0, min(1.0, value))
    if value >= 0:
        intensity = int(235 - 105 * value)
        return f"#{intensity:02x}{220:02x}{210:02x}"
    intensity = int(235 - 90 * abs(value))
    return f"#{210:02x}{225:02x}{intensity:02x}"
