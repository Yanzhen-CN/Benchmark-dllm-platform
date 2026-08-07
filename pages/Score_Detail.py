from __future__ import annotations

import pandas as pd
import streamlit as st

from platform_core.chart_panel import render_chart_panel
from platform_core.i18n import tr
from platform_core.compare import render_comparison
from platform_core.results import (
    available_metrics,
    default_comparison_runs,
    datasets,
    load_sample_scores,
    load_summary_records,
    metric_label,
    score_metric_options,
)
from platform_core.selection import select_model_variants, select_single_dataset
from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page(tr("指标明细 | Benchmark-dllm", "Score details | Benchmark-dllm"))
paths = paths_sidebar()
require_ready(paths)

st.title(tr("指标明细", "Score details"))

records = load_summary_records(paths.output_root)
if not records:
    st.warning("没有找到正式 score_output 结果。")
    st.stop()

with st.expander(tr("选择数据集、模型与指标", "Select a dataset, models, and metrics"), expanded=True):
    dataset_name = select_single_dataset(
        datasets(records),
        key_prefix="score_detail",
    )
    if dataset_name is None:
        st.warning("没有可用结果。")
        st.stop()

    dataset_records = [
        record for record in records if record["dataset"] == dataset_name
    ]
    selected_runs = select_model_variants(
        dataset_records,
        default_runs=default_comparison_runs([dataset_name]),
        key_prefix="score_detail",
    )
    selected_records = [
        record for record in dataset_records if record["run"] in selected_runs
    ]

    metric_options = score_metric_options(dataset_name, selected_records)
    selected_metrics = st.multiselect(
        tr("指标", "Metrics"),
        metric_options,
        default=metric_options[:6],
        format_func=metric_label,
    )

rows = []
for record in selected_records:
    for metric in selected_metrics:
        value = record["score_metrics"].get(metric)
        if value is not None:
            rows.append(
                {
                    "模型": record["run"],
                    "metric": metric_label(metric),
                    "value": value,
                }
            )

if rows:
    with st.expander(tr("评分指标", "Score metrics"), expanded=True):
        render_chart_panel(
            paths,
            title=tr("评分指标", "Score metrics"),
            section="score_detail",
            key=f"{dataset_name}_metrics",
            spec={
                "kind": "bar",
                "rows": rows,
                "facet_key": "metric",
                "category_key": "模型",
                "value_key": "value",
            },
            preview=lambda: render_comparison(rows, row_key="模型"),
        )
else:
    st.info("当前组合没有可比较的指标。")

with st.expander(tr("样本级明细", "Sample details")):
    if not selected_runs:
        st.info("请先选择模型或变体。")
    else:
        detail_run = st.selectbox(tr("查看模型", "Run"), selected_runs)
        samples = load_sample_scores(paths.output_root, detail_run, dataset_name)
        sample_rows = []
        for sample in samples:
            row = {
                "sample": sample["sample"],
                "valid": sample["valid"],
                "complete": sample["complete"],
            }
            for metric in selected_metrics:
                row[metric_label(metric)] = sample["metrics"].get(metric)
            sample_rows.append(row)
        if sample_rows:
            st.dataframe(
                pd.DataFrame(sample_rows),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("该模型与数据集没有样本级评分文件。")
