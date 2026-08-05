from __future__ import annotations

import pandas as pd
import streamlit as st

from platform_core.compare import render_comparison
from platform_core.results import (
    available_metrics,
    DEFAULT_COMPARISON_RUNS,
    datasets,
    load_sample_scores,
    load_summary_records,
    metric_label,
)
from platform_core.selection import select_model_variants, select_single_dataset
from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page("指标明细 | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("2. 数据集指标明细")

records = load_summary_records(paths.output_root)
if not records:
    st.warning("没有找到正式 score_output 结果。")
    st.stop()

with st.expander("选择数据集、模型与指标", expanded=True):
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
        default_runs=DEFAULT_COMPARISON_RUNS,
        key_prefix="score_detail",
    )
    selected_records = [
        record for record in dataset_records if record["run"] in selected_runs
    ]

    metric_options = available_metrics(selected_records, "score_metrics")
    primary_names = {record["primary_metric"] for record in selected_records}
    default_metrics = [name for name in metric_options if name in primary_names]
    fallback_order = (
        ("blank_cell_accuracy", "given_preservation_rate", "puzzle_success_rate")
        if dataset_name.startswith("sudoku")
        else ("valid_rate", "complete_rate", "answer_region_detected_rate")
    )
    for fallback in fallback_order:
        if fallback in metric_options and fallback not in default_metrics:
            default_metrics.append(fallback)
    selected_metrics = st.multiselect(
        "指标",
        metric_options,
        default=default_metrics[:4] or metric_options[:3],
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
    render_comparison(rows, row_key="模型")
else:
    st.info("当前组合没有可比较的指标。")

with st.expander("样本级明细"):
    if not selected_runs:
        st.info("请先选择模型或变体。")
    else:
        detail_run = st.selectbox("查看模型", selected_runs)
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
