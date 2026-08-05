from __future__ import annotations

import pandas as pd
import streamlit as st

from platform_core.radar import render_radar
from platform_core.results import (
    DEFAULT_COMPARISON_RUNS,
    DEFAULT_DATASETS,
    datasets,
    load_summary_records,
)
from platform_core.selection import select_dataset_subsets, select_model_variants
from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page("数据集总分 | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Score")

records = load_summary_records(paths.output_root)
if not records:
    st.warning("没有找到正式 score_output 结果。")
    st.stop()

with st.expander("选择数据集、模型与变体", expanded=True):
    dataset_options = datasets(records)
    selected_datasets = select_dataset_subsets(
        dataset_options,
        default_datasets=[name for name in DEFAULT_DATASETS if name in dataset_options],
        key_prefix="score_overview",
    )
    candidate_records = [
        record for record in records if record["dataset"] in selected_datasets
    ]
    selected_runs = select_model_variants(
        candidate_records,
        default_runs=DEFAULT_COMPARISON_RUNS,
        key_prefix="score_overview",
    )
    reportable_only = st.checkbox("只显示可报告结果", value=True)

filtered = [
    record
    for record in candidate_records
    if record["run"] in selected_runs
    and record["primary_score"] is not None
    and (record["reportable"] or not reportable_only)
]

if not filtered:
    st.info("当前选择没有可展示的正式主分。")
    st.stop()

headline = st.columns(3)
headline[0].metric("模型 / 变体", len({record["run"] for record in filtered}))
headline[1].metric("数据集", len({record["dataset"] for record in filtered}))
headline[2].metric("有效结果", len(filtered))

st.subheader("模型多任务对比")
radar_rows = [
    {"model": record["run"], "dataset": record["dataset"], "value": record["primary_score"]}
    for record in filtered
]
scale_col, fill_col = st.columns(2)
with scale_col:
    radar_scale = st.selectbox(
        "径向刻度",
        ["固定 0-1", "自动适应当前结果"],
        help="只改变坐标轴显示范围，不改变分数。",
    )
with fill_col:
    radar_fill = st.slider("区域填充", 0.0, 0.35, 0.12, 0.01)
render_radar(
    radar_rows,
    scale_mode="fixed" if radar_scale == "固定 0-1" else "auto",
    fill_opacity=radar_fill,
)

with st.expander("精确分数表"):
    rows = [
        {
            "模型": record["run"],
            "指标": f'{record["dataset"]} · {record["primary_metric"]}',
            "分数": record["primary_score"],
            "样本数": record["n_samples"],
        }
        for record in filtered
    ]
    frame = pd.DataFrame(rows)
    table = frame.pivot_table(
        index="模型",
        columns="指标",
        values="分数",
        aggfunc="first",
    ).reset_index()
    st.dataframe(table, width="stretch", hide_index=True)
    st.caption("缺失结果在雷达图中按 0 显示，表格中保留为空。")

if any(name.startswith("sudoku") for name in selected_datasets):
    with st.expander("如何理解 Sudoku 主分"):
        st.write(
            "六个 Sudoku 子集独立展示。完整解必须保留全部题面数字，并满足行、列和宫约束；"
            "空格正确率、题面保留率和答案区域检出率在“指标明细”中查看。"
        )
