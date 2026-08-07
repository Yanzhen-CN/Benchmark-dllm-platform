from __future__ import annotations

import streamlit as st

from platform_core.i18n import tr
from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page(tr("首页 | Benchmark-dllm", "Home | Benchmark-dllm"))
paths = paths_sidebar()
require_ready(paths)

st.markdown(
    """
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 252, 244, .72);
        border-color: #cdd6cf;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #4f8f7d;
        box-shadow: 0 .45rem 1.2rem rgba(32, 70, 59, .08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Benchmark-dllm")
st.caption(tr("运行评测、查看结果，并分析扩散语言模型的生成过程。", "Run benchmarks, inspect results, and analyze diffusion-language-model generation."))


def page_card(column, page: str, title: str, description: str, icon: str) -> None:
    with column:
        with st.container(border=True, height=170):
            st.page_link(page, label=title, icon=icon, use_container_width=True)
            st.write(description)


st.subheader(tr("评测结果", "Evaluation"))
score, detail, performance, trace = st.columns(4)
page_card(score, "pages/Score.py", tr("数据集总分", "Score"), tr("比较模型在各数据集上的主分。", "Compare primary scores across datasets."), ":material/analytics:")
page_card(detail, "pages/Score_Detail.py", tr("指标明细", "Score details"), tr("展开数据集副指标和样本级结果。", "Inspect diagnostic metrics and sample results."), ":material/table_chart:")
page_card(performance, "pages/Performance.py", tr("性能", "Performance"), tr("比较接受 TPS、耗时、能耗、显存与 Profiling。", "Compare accepted TPS, latency, energy, VRAM, and profiling."), ":material/speed:")
page_card(trace, "pages/Trace.py", tr("生成轨迹", "Trace"), tr("查看接受顺序、逐步变化和 Sudoku 动图。", "Inspect acceptance order, revisions, and Sudoku animations."), ":material/timeline:")

st.subheader(tr("运行与管理", "Run & Manage"))
run, catalog, environment, charts = st.columns(4)
page_card(run, "pages/Run.py", tr("运行任务", "Run benchmark"), tr("选择实验矩阵、模型、变体和数据集。", "Select a matrix, models, variants, and datasets."), ":material/play_arrow:")
page_card(catalog, "pages/Catalog.py", tr("模型与数据集", "Catalog"), tr("浏览当前模型配置与数据集设置。", "Browse model and dataset configurations."), ":material/inventory_2:")
page_card(environment, "pages/Environments.py", tr("运行环境", "Environments"), tr("查看模型启动器和隔离环境状态。", "Inspect model launchers and isolated environments."), ":material/deployed_code:")
page_card(charts, "pages/Charts.py", tr("可视化图库", "Charts"), tr("集中浏览和管理已生成的图表与动图。", "Browse and manage generated charts and animations."), ":material/gallery_thumbnail:")
