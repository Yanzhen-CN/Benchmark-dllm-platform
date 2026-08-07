from __future__ import annotations

import streamlit as st

from platform_core.i18n import language_selector, tr


language_selector()


navigation = st.navigation(
    {
        "": [
            st.Page(
                "pages/Home.py",
                title=tr("首页", "Home"),
                icon=":material/home:",
                default=True,
            )
        ],
        tr("评测结果", "Evaluation"): [
            st.Page(
                "pages/Score.py",
                title=tr("数据集总分", "Score"),
                icon=":material/analytics:",
            ),
            st.Page(
                "pages/Score_Detail.py",
                title=tr("指标明细", "Score details"),
                icon=":material/table_chart:",
            ),
            st.Page(
                "pages/Performance.py",
                title=tr("性能", "Performance"),
                icon=":material/speed:",
            ),
            st.Page(
                "pages/Trace.py",
                title=tr("生成轨迹", "Trace"),
                icon=":material/timeline:",
            ),
        ],
        tr("运行与管理", "Run & Manage"): [
            st.Page(
                "pages/Run.py",
                title=tr("运行任务", "Run benchmark"),
                icon=":material/play_arrow:",
            ),
            st.Page(
                "pages/Catalog.py",
                title=tr("模型与数据集", "Catalog"),
                icon=":material/inventory_2:",
            ),
            st.Page(
                "pages/Environments.py",
                title=tr("运行环境", "Environments"),
                icon=":material/deployed_code:",
            ),
            st.Page(
                "pages/Charts.py",
                title=tr("可视化图库", "Charts"),
                icon=":material/gallery_thumbnail:",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

navigation.run()
