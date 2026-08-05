from __future__ import annotations

import sys

import streamlit as st

from platform_core.catalog import discover_models
from platform_core.ui import configure_page, paths_sidebar, require_ready, short_path


configure_page("运行环境 | Benchmark-dllm", "◉")
paths = paths_sidebar()
require_ready(paths)

st.title("运行环境")

left, right = st.columns(2)
left.metric("平台 Python", sys.version.split()[0])
right.metric("模型配置", len(discover_models(paths)))

st.subheader("平台环境")
st.code(sys.executable)
st.write("这里只安装 Streamlit 和 PyYAML，不混入 torch 或模型特定的 transformers 版本。")

st.subheader("模型启动器")
scripts_dir = paths.benchmark_root / "venv_scripts"
venvs_dir = paths.benchmark_root / ".venvs"
rows = []
for model in discover_models(paths):
    script = scripts_dir / f"{model.name}.py"
    venv = venvs_dir / model.name
    rows.append(
        {
            "模型": model.name,
            "启动脚本": short_path(script, paths.benchmark_root),
            "脚本可用": script.is_file(),
            "环境目录": short_path(venv, paths.benchmark_root),
            "环境就绪": venv.is_dir(),
        }
    )
st.dataframe(rows, width="stretch", hide_index=True)

st.info(
    "run_bench.py 会把每个模型交给已有启动脚本。平台只显示环境状态，"
    "不会自动创建、更新或删除模型环境。"
)
