from __future__ import annotations

import streamlit as st


navigation = st.navigation(
    {
        "评测结果": [
            st.Page(
                "pages/1_Score_Overview.py",
                title="Score",
                icon=":material/analytics:",
                default=True,
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
        "运行": [
            st.Page(
                "pages/5_Run.py",
                title="运行任务",
                icon=":material/play_arrow:",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

navigation.run()
