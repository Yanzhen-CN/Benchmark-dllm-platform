from __future__ import annotations

import streamlit as st


navigation = st.navigation(
    {
        "": [
            st.Page(
                "pages/0_Home.py",
                title="首页",
                icon=":material/home:",
                default=True,
            )
        ],
        "评测结果": [
            st.Page(
                "pages/1_Score_Overview.py",
                title="数据集总分",
                icon=":material/analytics:",
            ),
            st.Page(
                "pages/2_Score_Detail.py",
                title="指标明细",
                icon=":material/table_chart:",
            ),
            st.Page(
                "pages/3_Performance.py",
                title="性能",
                icon=":material/speed:",
            ),
            st.Page(
                "pages/4_Trace.py",
                title="生成轨迹",
                icon=":material/timeline:",
            ),
        ],
        "运行与管理": [
            st.Page(
                "pages/5_Run.py",
                title="运行任务",
                icon=":material/play_arrow:",
            ),
            st.Page(
                "pages/6_Catalog.py",
                title="模型与数据集",
                icon=":material/inventory_2:",
            ),
            st.Page(
                "pages/7_Environments.py",
                title="运行环境",
                icon=":material/deployed_code:",
            ),
            st.Page(
                "pages/8_Charts.py",
                title="可视化图库",
                icon=":material/gallery_thumbnail:",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

navigation.run()
