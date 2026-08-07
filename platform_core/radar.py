from __future__ import annotations

from collections import defaultdict
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from .ui import render_plotly_chart


PALETTE = (
    "#0f4c45",
    "#d97706",
    "#2563a6",
    "#b33a3a",
    "#6b5b2a",
    "#28856f",
    "#9b4f74",
    "#52677d",
    "#8a5a2b",
    "#3b7f3f",
)


def _rgba(hex_color: str, alpha: float) -> str:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha:.3f})"


def render_radar(
    rows: list[dict[str, Any]],
    *,
    scale_mode: str = "fixed",
    fill_opacity: float = 0.12,
) -> None:
    dimensions = list(dict.fromkeys(str(row["dataset"]) for row in rows))
    if len(dimensions) < 3:
        st.info("雷达图至少需要选择三个有结果的数据集。")
        return

    by_model: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        value = row.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            by_model[str(row["model"])][str(row["dataset"])] = float(value)

    plotted = {model: values for model, values in by_model.items() if values}
    if not plotted:
        st.info("当前模型没有可绘制的数据集结果。")
        return

    incomplete = {
        model: [dimension for dimension in dimensions if dimension not in model_values]
        for model, model_values in plotted.items()
        if any(dimension not in model_values for dimension in dimensions)
    }
    if incomplete:
        details = "；".join(
            f"{model}：{', '.join(missing)}" for model, missing in incomplete.items()
        )
        st.warning(
            "以下模型存在未测试数据集，雷达图暂按 0 显示，仅用于补全图形，"
            "不代表模型实际得分；表格仍保持空白：" + details
        )

    if len(plotted) > len(PALETTE):
        st.warning(f"雷达图最多叠加 {len(PALETTE)} 个模型，当前只画前 {len(PALETTE)} 个。")
        plotted = dict(list(plotted.items())[: len(PALETTE)])

    values = [value for model_values in plotted.values() for value in model_values.values()]
    observed_max = max(values, default=1.0)
    if scale_mode == "fixed" and observed_max <= 1.0:
        scale_max = 1.0
    else:
        scale_max = max(observed_max * 1.05, 0.1)

    figure = go.Figure()
    closed_dimensions = dimensions + [dimensions[0]]
    for index, (model, model_values) in enumerate(plotted.items()):
        color = PALETTE[index]
        model_complete = all(dimension in model_values for dimension in dimensions)
        model_scores = [model_values.get(dimension, 0.0) for dimension in dimensions]
        point_status = [
            "已测试" if dimension in model_values else "未测试（按 0 占位）"
            for dimension in dimensions
        ]
        figure.add_trace(
            go.Scatterpolar(
                r=model_scores + [model_scores[0]],
                theta=closed_dimensions,
                customdata=point_status + [point_status[0]],
                mode="lines+markers",
                name=model,
                line={
                    "color": color,
                    "width": 3,
                    "dash": "solid" if model_complete else "dot",
                },
                marker={"color": color, "size": 7},
                fill="toself" if fill_opacity > 0 else None,
                fillcolor=_rgba(color, fill_opacity),
                connectgaps=True,
                hovertemplate=(
                    f"<b>{model}</b><br>"
                    "%{theta}: %{r:.4f}<br>%{customdata}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=620,
        margin={"l": 70, "r": 210, "t": 45, "b": 45},
        paper_bgcolor="rgba(0,0,0,0)",
        polar={
            "bgcolor": "#fbf7ed",
            "radialaxis": {
                "visible": True,
                "range": [0, scale_max],
                "tickformat": ".2f",
                "gridcolor": "#c8d2ca",
                "linecolor": "#9fb0a5",
            },
            "angularaxis": {
                "gridcolor": "#b8c4bc",
                "linecolor": "#9fb0a5",
                "tickfont": {"color": "#173f39", "size": 14},
            },
        },
        legend={
            "title": {"text": "模型"},
            "orientation": "v",
            "x": 1.08,
            "xanchor": "left",
            "y": 1.0,
            "yanchor": "top",
            "font": {"size": 13},
        },
        hovermode="closest",
        uirevision="dataset-score-radar",
    )
    render_plotly_chart(
        figure,
        key="dataset_score_radar",
        legend_title="模型",
        margin={"l": 70, "r": 210, "t": 45, "b": 45},
    )
    st.caption(
        "单击图例可隐藏或恢复模型，双击可只看一个模型；鼠标悬停显示原始主分。"
        "虚线表示模型缺少部分所选数据集，缺失位置在图中按 0 显示。"
        f"当前径向范围为 0–{scale_max:.3g}，没有折算或归一化。"
    )
