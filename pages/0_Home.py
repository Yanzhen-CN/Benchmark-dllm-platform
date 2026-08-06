from __future__ import annotations

import streamlit as st

from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page("首页 | Benchmark-dllm")
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
st.caption("运行评测、查看结果，并分析扩散语言模型的生成过程。")


def page_card(column, page: str, title: str, description: str, icon: str) -> None:
    with column:
        with st.container(border=True, height=170):
            st.page_link(page, label=title, icon=icon, use_container_width=True)
            st.write(description)


st.subheader("评测结果")
score, detail, performance, trace = st.columns(4)
page_card(score, "pages/1_Score_Overview.py", "数据集总分", "比较模型在各数据集上的主分。", ":material/analytics:")
page_card(detail, "pages/2_Score_Detail.py", "指标明细", "展开数据集副指标和样本级结果。", ":material/table_chart:")
page_card(performance, "pages/3_Performance.py", "性能", "比较接受 TPS、耗时、能耗、显存与 Profiling。", ":material/speed:")
page_card(trace, "pages/4_Trace.py", "生成轨迹", "查看接受顺序、逐步变化和 Sudoku 动图。", ":material/timeline:")

st.subheader("运行与管理")
run, catalog, environment, charts = st.columns(4)
page_card(run, "pages/5_Run.py", "运行任务", "选择实验矩阵、模型、变体和数据集。", ":material/play_arrow:")
page_card(catalog, "pages/6_Catalog.py", "模型与数据集", "浏览当前模型配置与数据集设置。", ":material/inventory_2:")
page_card(environment, "pages/7_Environments.py", "运行环境", "查看模型启动器和隔离环境状态。", ":material/deployed_code:")
page_card(charts, "pages/8_Charts.py", "可视化图库", "集中浏览和管理已生成的图表与动图。", ":material/gallery_thumbnail:")
