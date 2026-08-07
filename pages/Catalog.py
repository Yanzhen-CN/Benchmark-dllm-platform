from __future__ import annotations

import streamlit as st

from platform_core.i18n import tr

from platform_core.catalog import (
    discover_experiment_datasets,
    discover_experiment_models,
    discover_experiments,
)
from platform_core.selection import dataset_label
from platform_core.ui import configure_page, paths_sidebar, require_ready, short_path


configure_page("Catalog | Benchmark-dllm", "▦")
paths = paths_sidebar()
require_ready(paths)

st.title(tr("模型与数据集目录", "Model and dataset catalog"))

experiments = discover_experiments(paths)
experiment_map = {item.name: item for item in experiments}
if not experiment_map:
    st.warning("没有找到实验矩阵。")
    st.stop()

matrix_names = list(experiment_map)
matrix_name = st.selectbox(
    tr("实验矩阵", "Experiment matrix"),
    matrix_names,
    index=matrix_names.index("full_matrix") if "full_matrix" in matrix_names else 0,
)
datasets = discover_experiment_datasets(paths, experiment_map[matrix_name].path)
models = discover_experiment_models(paths, experiment_map[matrix_name].path)
sudoku_count = sum(item.group == "Sudoku" for item in datasets)
hellobench_variants = 2 if any(item.group == "HelloBench" for item in datasets) else 0

summary = st.columns(4)
summary[0].metric("模型配置", len(models))
summary[1].metric("矩阵数据集", len(datasets))
summary[2].metric("Sudoku 子集", sudoku_count)
summary[3].metric("HelloBench 变体", hellobench_variants)

with st.expander(tr("模型与变体", "Models and variants")):
    st.dataframe(
        [
            {
                "model": item.name,
                "variants": ", ".join(item.variants) or "N/A",
                "max context": item.max_context_tokens,
                "config": short_path(item.path, paths.benchmark_root),
            }
            for item in models
        ],
        width="stretch",
        hide_index=True,
    )

with st.expander(tr("数据集配置", "Dataset configurations"), expanded=True):
    if sudoku_count:
        st.info(
            f"Sudoku 是父数据集，当前矩阵包含 {sudoku_count} 个独立子集；"
            "运行和结果页面只有在选择 Sudoku 后才显示这些子集。"
        )
    st.dataframe(
        [
            {
                "group": item.group,
                "subset": (
                    dataset_label(item.name)
                    if item.group == "Sudoku"
                    else "2k（默认）、4k"
                    if item.group == "HelloBench"
                    else item.name
                ),
                "config name": item.name,
                "prompt": item.mode,
                "primary metric": item.primary_metric,
                "sample size": item.sample_size,
                "output budget": item.max_new_tokens,
                "optional": item.optional,
                "config": short_path(item.path, paths.benchmark_root),
            }
            for item in datasets
        ],
        width="stretch",
        hide_index=True,
    )

with st.expander(tr("全部实验矩阵", "Experiment matrices")):
    st.dataframe(
        [
            {
                "experiment": item.name,
                "config": short_path(item.path, paths.benchmark_root),
            }
            for item in experiments
        ],
        width="stretch",
        hide_index=True,
    )
