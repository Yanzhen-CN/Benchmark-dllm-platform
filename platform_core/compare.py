from __future__ import annotations

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
    metric_count = frame[metric_key].nunique()
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            y=alt.Y(
                f"{row_key}:N",
                title=None,
                sort="-x",
                axis=alt.Axis(labelLimit=190),
            ),
            x=alt.X(
                f"{value_key}:Q",
                title=None,
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(f"{row_key}:N", legend=None),
            tooltip=[
                alt.Tooltip(f"{row_key}:N", title="模型"),
                alt.Tooltip(f"{metric_key}:N", title="指标"),
                alt.Tooltip(f"{value_key}:Q", title="数值", format=".5g"),
            ],
        )
        .properties(
            width=220,
            height=max(130, min(340, 28 * frame[row_key].nunique())),
        )
        .facet(
            facet=alt.Facet(f"{metric_key}:N", title=None),
            columns=min(2, metric_count),
        )
        .resolve_scale(x="independent")
    )
    st.altair_chart(chart, width="stretch")
