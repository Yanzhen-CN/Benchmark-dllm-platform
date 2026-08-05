from __future__ import annotations

import streamlit as st

from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page("Home | Benchmark-dllm", "●")
paths = paths_sidebar()
require_ready(paths)

st.markdown(
    """
    <style>
    .home-grid {
        display: grid;
        gap: 1rem;
        margin: .8rem 0 2rem;
    }
    .home-grid.evaluation { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .home-grid.run { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .home-card {
        box-sizing: border-box;
        min-height: 12.5rem;
        padding: 1.15rem 1.1rem;
        border: 1px solid #cdd6cf;
        border-radius: .7rem;
        background: rgba(255, 252, 244, .72);
        color: #173b34 !important;
        text-decoration: none !important;
        display: flex;
        flex-direction: column;
        transition: border-color .16s ease, transform .16s ease, box-shadow .16s ease;
    }
    .home-card:hover {
        border-color: #4f8f7d;
        box-shadow: 0 .45rem 1.2rem rgba(32, 70, 59, .09);
        transform: translateY(-2px);
    }
    .home-card h3 { margin: 0 0 .75rem; font-size: 1.55rem; }
    .home-card p { margin: 0; color: #344c46; line-height: 1.65; }
    .home-card span { margin-top: auto; padding-top: 1rem; font-weight: 600; }
    @media (max-width: 980px) {
        .home-grid.evaluation, .home-grid.run { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 620px) {
        .home-grid.evaluation, .home-grid.run { grid-template-columns: 1fr; }
        .home-card { min-height: 10rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Benchmark-dllm")
st.caption("一个方便运行 Benchmark、查看评测结果和分析模型表现的平台。")

st.subheader("Evaluation")
st.markdown(
    """
    <div class="home-grid evaluation">
      <a class="home-card" href="Score_Overview" target="_self">
        <h3>Score</h3><p>比较数据集主分、模型和变体。</p><span>打开 Score →</span>
      </a>
      <a class="home-card" href="Performance" target="_self">
        <h3>Performance</h3><p>查看延迟、吞吐、能量和 profiling。</p><span>打开 Performance →</span>
      </a>
      <a class="home-card" href="Trace" target="_self">
        <h3>Trace</h3><p>检查逐步生成、关键帧和答案区域。</p><span>打开 Trace →</span>
      </a>
      <a class="home-card" href="Charts" target="_self">
        <h3>Charts</h3><p>浏览已经生成的配置图表和 GIF 动图。</p><span>打开 Charts →</span>
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Run Benchmark")
st.markdown(
    """
    <div class="home-grid run">
      <a class="home-card" href="Catalog" target="_self">
        <h3>Catalog</h3><p>查看模型、变体、数据集和实验矩阵。</p><span>打开 Catalog →</span>
      </a>
      <a class="home-card" href="Environments" target="_self">
        <h3>Environment</h3><p>确认模型启动脚本和隔离环境状态。</p><span>打开 Environment →</span>
      </a>
      <a class="home-card" href="Run" target="_self">
        <h3>Run</h3><p>选择矩阵、模型和数据集并生成命令。</p><span>打开 Run →</span>
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)
