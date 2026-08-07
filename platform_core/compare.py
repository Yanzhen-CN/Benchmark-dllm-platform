from __future__ import annotations

import html
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st


def render_comparison(
    rows: list[dict[str, Any]],
    *,
    row_key: str,
    metric_key: str = "metric",
    value_key: str = "value",
) -> None:
    if not rows:
        st.info("当前选择没有可比较的数值。")
        return

    frame = pd.DataFrame(rows)
    model_names = list(dict.fromkeys(frame[row_key].astype(str)))
    metric_names = list(dict.fromkeys(frame[metric_key].astype(str)))
    is_group_overview = len(metric_names) > 1
    palette = [
        "#4c78a8",
        "#f58518",
        "#e45756",
        "#72b7b2",
        "#54a24b",
        "#eeca3b",
        "#b279a2",
        "#ff9da6",
        "#9d755d",
        "#bab0ac",
    ]
    model_colors = {
        model: palette[index % len(palette)]
        for index, model in enumerate(model_names)
    }
    if is_group_overview:
        legend_items = "".join(
            (
                '<span style="display:inline-flex;align-items:center;gap:.28rem;'
                'white-space:nowrap;font-size:.75rem;line-height:1.15">'
                f'<span style="width:.52rem;height:.52rem;border-radius:2px;'
                f'background:{model_colors[model]};display:inline-block"></span>'
                f"{html.escape(model)}</span>"
            )
            for model in model_names
        )
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:.28rem .7rem;'
            f'margin:0 0 .4rem">{legend_items}</div>',
            unsafe_allow_html=True,
        )

    # A faceted Vega chart keeps a fixed child width even when Streamlit's
    # sidebar reduces the available page width.  Render each metric as its own
    # responsive block instead: the charts still form one overview panel, but
    # every block is sized directly by the current Streamlit container.
    chart_height = max(130, min(340, 28 * frame[row_key].nunique()))
    for metric_name in metric_names:
        metric_frame = frame[frame[metric_key].astype(str) == metric_name]
        chart = (
            alt.Chart(metric_frame)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y(
                    f"{row_key}:N",
                    title=None,
                    sort="-x",
                    axis=(
                        alt.Axis(labels=False, ticks=False, domain=False)
                        if is_group_overview
                        else alt.Axis(labelLimit=190, labelOverlap=False)
                    ),
                ),
                x=alt.X(
                    f"{value_key}:Q",
                    title=None,
                    scale=alt.Scale(zero=False),
                ),
                color=alt.Color(
                    f"{row_key}:N",
                    legend=None,
                    scale=alt.Scale(
                        domain=model_names,
                        range=[model_colors[model] for model in model_names],
                    ),
                ),
                tooltip=[
                    alt.Tooltip(f"{row_key}:N", title="模型"),
                    alt.Tooltip(f"{metric_key}:N", title="指标"),
                    alt.Tooltip(f"{value_key}:Q", title="数值", format=".5g"),
                ],
            )
            .properties(title=metric_name, height=chart_height)
        )
        st.altair_chart(chart, width="stretch")
