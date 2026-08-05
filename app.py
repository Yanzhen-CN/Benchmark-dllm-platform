from __future__ import annotations

import streamlit as st


navigation = st.navigation(
    {
        "": [
            st.Page(
                "pages/0_Home.py",
                title="Home",
                icon=":material/home:",
                default=True,
            )
        ],
        "Evaluation": [
            st.Page(
                "pages/1_Score_Overview.py",
                title="Score",
                icon=":material/analytics:",
            ),
            st.Page(
                "pages/3_Performance.py",
                title="Performance",
                icon=":material/speed:",
            ),
            st.Page(
                "pages/4_Trace.py",
                title="Trace",
                icon=":material/timeline:",
            ),
            st.Page(
                "pages/8_Charts.py",
                title="Charts",
                icon=":material/gallery_thumbnail:",
            ),
        ],
        "Run Benchmark": [
            st.Page(
                "pages/6_Catalog.py",
                title="Catalog",
                icon=":material/inventory_2:",
            ),
            st.Page(
                "pages/7_Environments.py",
                title="Environment",
                icon=":material/deployed_code:",
            ),
            st.Page(
                "pages/5_Run.py",
                title="Run",
                icon=":material/play_arrow:",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

navigation.run()
