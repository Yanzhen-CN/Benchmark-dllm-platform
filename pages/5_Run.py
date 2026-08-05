from __future__ import annotations

import html

import streamlit as st

from platform_core.catalog import (
    discover_experiment_datasets,
    discover_experiments,
    discover_models,
)
from platform_core.commands import RunSelection, build_run_command, command_text
from platform_core.maintenance import (
    clear_all_outputs,
    clear_run_history,
    count_files,
    delete_output_target,
    empty_trash,
    list_trash_entries,
    output_children,
    output_runs,
    output_stages,
    output_target,
    restore_trash_entry,
)
from platform_core.processes import read_log, recent_runs, start_run
from platform_core.selection import select_run_datasets
from platform_core.ui import confirm_clear, configure_page, paths_sidebar, require_ready


configure_page("Run | Benchmark-dllm", "▶")
paths = paths_sidebar()
require_ready(paths)

st.markdown(
    """
    <style>
    .path-preview {
        padding: .8rem 1rem;
        border: 1px solid #d7ded8;
        border-radius: .55rem;
        background: #fffaf0;
        color: #314842;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: .86rem;
        line-height: 1.5;
        overflow-wrap: anywhere;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Run Benchmark")

run_tab, records_tab = st.tabs(["运行", "记录管理"])

with run_tab:
    models = discover_models(paths)
    experiments = discover_experiments(paths)
    model_map = {item.name: item for item in models}
    experiment_map = {item.name: item for item in experiments}
    if not experiment_map:
        st.warning("没有找到实验矩阵。")
        st.stop()

    matrix_names = list(experiment_map)
    matrix_name = st.selectbox(
        "实验矩阵",
        matrix_names,
        index=matrix_names.index("full_matrix") if "full_matrix" in matrix_names else 0,
    )
    matrix = experiment_map[matrix_name]
    datasets = discover_experiment_datasets(paths, matrix.path)

    selected_models = st.multiselect("模型", list(model_map), default=[])
    variants: list[str] = []
    if len(selected_models) == 1:
        variants = st.multiselect(
            "变体",
            list(model_map[selected_models[0]].variants),
        )
    elif len(selected_models) > 1:
        st.info("多模型任务使用矩阵默认变体；选择单个模型后可以继续筛选变体。")

    selected_datasets, hellobench_lengths = select_run_datasets(
        [item.name for item in datasets],
        key_prefix="run",
    )

    stage_labels = {
        "generate": "生成",
        "score": "打分",
        "visualize": "可视化",
        "all": "生成 + 打分 + 可视化",
    }
    left, middle, right = st.columns(3)
    stage = left.selectbox(
        "阶段",
        list(stage_labels),
        index=3,
        format_func=stage_labels.get,
    )
    data_source = middle.radio("数据来源", ["real", "demo"], horizontal=True)
    n_samples_value = right.number_input(
        "样本数（0 表示使用配置值）", min_value=0, value=0
    )

    options = st.columns(2)
    measure_compute = options[0].checkbox("记录计算指标")
    dry_run = options[1].checkbox("仅预览命令", value=True)

    selection = RunSelection(
        models=tuple(selected_models),
        datasets=tuple(selected_datasets),
        matrix=matrix.path,
        stage=stage,
        variants=tuple(variants),
        hellobench_lengths=tuple(hellobench_lengths),
        real_data=data_source == "real",
        n_samples=int(n_samples_value) or None,
        enable_reasoning=False,
        measure_compute=measure_compute,
        dry_run=dry_run,
    )

    def environment_ready(model_name: str) -> bool:
        venv = paths.benchmark_root / ".venvs" / model_name
        python_candidates = (venv / "bin" / "python", venv / "Scripts" / "python.exe")
        launcher = paths.benchmark_root / "venv_scripts" / f"{model_name}.py"
        return launcher.is_file() and any(path.is_file() for path in python_candidates)

    missing_environments = [name for name in selected_models if not environment_ready(name)]
    if missing_environments:
        st.warning(
            "以下模型环境尚未就绪：" + ", ".join(missing_environments)
            + "。仍可使用仅预览模式。"
        )

    if not selected_models:
        command: list[str] = []
        st.info("请至少选择一个模型。")
    elif not selected_datasets:
        command = []
        st.info("请至少选择一个数据集。")
    elif "hellobench" in selected_datasets and not hellobench_lengths:
        command = []
        st.info("请至少选择一个 HelloBench 长度。")
    else:
        try:
            command = build_run_command(paths, selection)
        except ValueError as exc:
            command = []
            st.info(str(exc))

    if command:
        st.subheader("命令预览")
        st.code(command_text(command), language="powershell")
        confirmed = dry_run or st.checkbox("我确认本次运行可能使用 GPU 并产生费用。")
        run_available = dry_run or not missing_environments
        if st.button("开始运行", type="primary", disabled=not confirmed or not run_available):
            record = start_run(paths, command)
            st.success(f"任务已启动，PID {record['pid']}。日志：{record['log_path']}")

    st.subheader("最近的平台任务")
    for record in recent_runs(paths):
        with st.expander(f"{record.get('run_id')} | PID {record.get('pid')}"):
            st.code(command_text(record.get("command", [])), language="powershell")
            st.text(read_log(record))

with records_tab:
    trash_entries = list_trash_entries(paths.output_root)
    with st.expander(f"Recycle bin ({len(trash_entries)})"):
        st.caption("Deleted benchmark outputs are kept here until the recycle bin is emptied.")
        if not trash_entries:
            st.info("The recycle bin is empty.")
        for entry in trash_entries:
            path_column, action_column = st.columns([4, 1], vertical_alignment="center")
            path_column.code(entry["original_relative_path"], language="text")
            if action_column.button("Restore", key=f"restore_output_{entry['id']}"):
                try:
                    restored = restore_trash_entry(paths.output_root, entry["id"])
                except FileExistsError:
                    st.error("The original path already exists. Nothing was overwritten.")
                else:
                    st.success(f"Restored: {restored}")
                    st.rerun()
        if trash_entries:
            purge_confirmation = st.text_input(
                "Type EMPTY to permanently delete recycled outputs",
                key="empty_output_trash_confirmation",
            )
            if st.button(
                "Empty recycle bin",
                key="empty_output_trash",
                disabled=purge_confirmation != "EMPTY",
            ):
                removed = empty_trash(paths.output_root)
                st.success(f"Permanently removed {removed} recycled items.")
                st.rerun()

    st.subheader("Benchmark 输出")
    stages = output_stages(paths)
    if not stages:
        st.info("当前输出目录中没有可管理的 Benchmark 结果。")
    else:
        stage_labels = {
            "model_output": "模型输出",
            "score_output": "评分结果",
            "visualization_output": "可视化结果",
            "model_profiling": "Profiling 结果",
        }
        stage = st.selectbox("结果类型", stages, format_func=stage_labels.get)
        runs = output_runs(paths, stage)
        if not runs:
            st.info("该结果类型下没有模型或运行记录。")
        else:
            run_name = st.selectbox("模型 / 运行", runs)
            children = output_children(paths, stage, run_name)
            child_choice = st.selectbox("数据集 / 分组", ["整个运行", *children])
            child = None if child_choice == "整个运行" else child_choice
            target = output_target(paths, stage, run_name, child)
            st.markdown(
                f'<div class="path-preview">{html.escape(str(target))}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"该路径包含 {count_files(target)} 个文件。")
            if confirm_clear(
                "Clear selected output",
                key="clear_selected_output",
                description=f"将永久删除所选路径中的 {count_files(target)} 个文件。",
                confirmation="DELETE",
            ):
                removed = delete_output_target(paths, stage, run_name, child)
                st.success(f"已删除：{removed}")
                st.rerun()

    st.divider()
    st.subheader("平台任务记录")
    history = recent_runs(paths, limit=1000)
    st.caption(f"当前保存 {len(history)} 条平台任务记录；清理记录不会停止正在运行的进程。")
    if confirm_clear(
        "Clear task history",
        key="clear_task_history",
        description="将删除全部平台任务元数据和日志，但不会停止正在运行的进程。",
    ):
        removed = clear_run_history(paths)
        st.success(f"已删除 {removed} 个任务元数据或日志文件。")
        st.rerun()

    st.divider()
    st.subheader("全部清理")
    if confirm_clear(
        "Clear all",
        key="clear_all_outputs",
        description=(
            "将永久删除全部模型输出、评分结果、可视化、Profiling 和平台任务记录。"
        ),
        confirmation="CLEAR ALL",
    ):
        stages_removed = clear_all_outputs(paths)
        history_removed = clear_run_history(paths)
        st.success(
            f"已清理 {stages_removed} 个输出目录和 {history_removed} 个任务记录文件。"
        )
        st.rerun()
