from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from platform_core.chart_panel import render_chart_panel
from platform_core.i18n import tr
from platform_core.results import load_trace_summary_records
from platform_core.trace import (
    load_trace_record,
    sudoku_animation_figure,
    trace_event_activity,
    trace_figure,
)
from platform_core.ui import (
    configure_page,
    paths_sidebar,
    render_plotly_chart as render_plotly,
    require_ready,
)
from platform_core.visualization import (
    child_directories,
    comparable_sudoku_samples,
    run_visualization_command,
    sample_ids,
    trace_artifacts,
    trace_batch_command,
    trace_command,
)


configure_page("Trace | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Trace")
st.markdown(
    """
    <style>
    [data-testid="stExpander"] { margin-bottom: .55rem; }
    [data-testid="stExpander"] details {
        border-color: #d9dfda;
        border-radius: .7rem;
        background: rgba(255, 252, 244, .58);
    }
    [data-testid="stExpander"] summary { min-height: 2.65rem; }
    [data-testid="stExpander"] details[open] > summary {
        border-bottom: 1px solid rgba(205, 214, 207, .72);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

model_output_root = paths.output_root / "model_output"


def available_runs() -> list[str]:
    return [
        f"{model}/{variant}"
        for model in child_directories(model_output_root)
        for variant in child_directories(model_output_root / model)
    ]


def run_root(run: str, dataset: str | None = None) -> Path:
    model, _, variant = run.partition("/")
    root = model_output_root / model / variant
    return root / dataset if dataset else root


def datasets_for_run(run: str) -> set[str]:
    return set(child_directories(run_root(run)))


def common_datasets(runs: list[str], *, sudoku_only: bool = False) -> list[str]:
    if not runs:
        return []
    values = set.intersection(*(datasets_for_run(run) for run in runs))
    if sudoku_only:
        values = {name for name in values if name.startswith("sudoku")}
    return sorted(values)


def common_sample_ids(runs: list[str], dataset: str) -> list[str]:
    if not runs:
        return []
    sample_sets = [set(sample_ids(run_root(run, dataset))) for run in runs]
    return sorted(set.intersection(*sample_sets)) if sample_sets else []


@st.cache_data(show_spinner=False, ttl=30)
def cached_record(path: str, modified_ns: int) -> dict:
    del modified_ns
    return load_trace_record(path)


def record_for(run: str, dataset: str, sample: str) -> dict:
    path = run_root(run, dataset) / f"{sample}.json"
    if not path.is_file():
        return {}
    return cached_record(str(path), path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False, ttl=60)
def eligible_sudoku_samples(
    output_root: str,
    selected_runs: tuple[str, ...],
    dataset: str,
) -> list[str]:
    return comparable_sudoku_samples(
        Path(output_root) / "model_output",
        list(selected_runs),
        dataset,
    )


def generate_official(command: list[str] | list[list[str]], label: str) -> None:
    commands = command if command and isinstance(command[0], list) else [command]
    failures = []
    with st.spinner(f"正在生成 {label}..."):
        for item in commands:
            result = run_visualization_command(paths, item)
            if result.returncode != 0:
                detail = "\n".join(
                    (result.stdout + "\n" + result.stderr).splitlines()[-30:]
                )
                failures.append(detail)
    if not failures:
        st.success(f"{label} 已保存到 visualization_output。")
        return
    st.error(f"{label} 生成失败。")
    detail = "\n\n".join(value for value in failures if value)
    if detail:
        st.code(detail, language="text")


runs = available_runs()
if not runs:
    st.info("model_output 中没有可查看的结果。")
    st.stop()

summaries = load_trace_summary_records(paths.output_root)
trace_sections = {
    "comparison": tr("模型对比", "Model comparison"),
    "sudoku": tr("数独解题轨迹", "Sudoku solve trace"),
}
trace_section = st.segmented_control(
    tr("页面", "Section"),
    list(trace_sections),
    default="comparison",
    format_func=trace_sections.get,
    label_visibility="collapsed",
    key="trace_section",
)


if trace_section == "comparison":
    st.caption(tr("预览直接读取保存的 forward 数据；正式图由 visualization 生成。", "Preview reads saved forward data; Generated shows files created by visualization."))

    default_runs = [
        run
        for run in (
            "illada/p1",
            "dreamreasoner/p1",
            "diffusiongemma/official",
            "gemma/ar-baseline",
        )
        if run in runs
    ]
    with st.expander("选择模型、数据集和样本", expanded=True):
        selected_runs = st.multiselect(
            "模型与变体",
            runs,
            default=default_runs or runs[:2],
            key="trace_general_runs",
        )
        dataset_options = common_datasets(selected_runs)
        if dataset_options:
            dataset_name = st.selectbox(
                "共同数据集",
                dataset_options,
                key="trace_general_dataset",
            )
            sample_options = common_sample_ids(selected_runs, dataset_name)
        else:
            dataset_name = ""
            sample_options = []

        if sample_options:
            preferred = next(
                (
                    value
                    for value in ("sudoku-test-0758", "sudoku4-d1-0021")
                    if value in sample_options
                ),
                sample_options[0],
            )
            sample_name = st.selectbox(
                "共同样本",
                sample_options,
                index=sample_options.index(preferred),
                key="trace_general_sample",
            )
        else:
            sample_name = ""
            if selected_runs:
                st.info("所选运行没有共同的数据集或样本。")

    if selected_runs and dataset_name:
        summary_rows = []
        for summary in summaries:
            if (
                summary.get("run") in selected_runs
                and summary.get("dataset") == dataset_name
            ):
                row = {"模型": summary["run"]}
                row.update(summary.get("metrics") or {})
                summary_rows.append(row)
        if summary_rows:
            with st.expander("数据集 Trace 指标", expanded=False):
                st.dataframe(
                    pd.DataFrame(summary_rows),
                    width="stretch",
                    hide_index=True,
                )

    if sample_name:
        for run in selected_runs:
            model, _, variant = run.partition("/")
            record = record_for(run, dataset_name, sample_name)
            artifacts = trace_artifacts(
                paths, model=model, variant=variant,
                dataset=dataset_name, sample=sample_name,
            )
            command = trace_command(
                paths, model=model, variant=variant,
                dataset=dataset_name, sample=sample_name,
            )
            with st.expander(run, expanded=True):
                st.caption(f"{dataset_name} · {sample_name}")
                render_chart_panel(
                    paths,
                    title=tr("接受轨迹", "Accept trace"),
                    section="trace",
                    key=f"{model}_{variant}_{dataset_name}_{sample_name}",
                    generated_path=artifacts["accept_trace"],
                    command=command,
                    preview=lambda record=record, run=run: render_plotly(
                        trace_figure(record, title=f"{run} · {dataset_name} · {sample_name}"),
                        key=f"live_trace_{run}_{dataset_name}_{sample_name}",
                        legend_title="",
                        margin=dict(l=55, r=20, t=75, b=50),
                    ) if record.get("trace") else st.info("No forward trace is available."),
                    prefer_generated=True,
                )


elif trace_section == "sudoku":
    st.caption("每个模型单独占一行：左侧播放解题过程，右侧查看同一批 forward 的 token 状态。")

    sudoku_filters = st.expander("选择模型、数据集和样本", expanded=True)
    default_sudoku_runs = [
        run
        for run in ("diffusiongemma/official", "llada2_1/qmode")
        if run in runs
    ]
    sudoku_runs = tuple(
        sudoku_filters.multiselect(
            "模型与变体",
            runs,
            default=default_sudoku_runs or runs[:2],
            key="sudoku_trace_runs",
        )
    )

    shared_datasets = common_datasets(list(sudoku_runs), sudoku_only=True)
    candidate_map = {
        dataset: eligible_sudoku_samples(
            str(paths.output_root),
            sudoku_runs,
            dataset,
        )
        for dataset in shared_datasets
    }
    eligible_datasets = [
        dataset for dataset in shared_datasets if candidate_map[dataset]
    ]
    dataset_options = eligible_datasets or shared_datasets

    if not dataset_options:
        sudoku_filters.info("已选模型没有共同 Sudoku 数据集。")
    else:
        dataset_column, sample_column = sudoku_filters.columns(2)
        with dataset_column:
            preferred_dataset = (
                "sudoku4_1shot"
                if "sudoku4_1shot" in dataset_options
                else dataset_options[0]
            )
            sudoku_dataset = st.selectbox(
                "数据集",
                dataset_options,
                index=dataset_options.index(preferred_dataset),
                key="sudoku_trace_dataset",
            )
        sudoku_samples = candidate_map[sudoku_dataset]
        if not sudoku_samples:
            sudoku_samples = common_sample_ids(list(sudoku_runs), sudoku_dataset)
            sudoku_filters.warning("该数据集没有所有模型都形成完整答案区域的样本；当前列表用于检查失败轨迹。")
        if sudoku_samples:
            with sample_column:
                def activity(sample: str) -> tuple[int, int, int, int]:
                    values = [
                        trace_event_activity(
                            record_for(run, sudoku_dataset, sample)
                        )
                        for run in sudoku_runs
                    ]
                    revisions = [value[0] for value in values]
                    later_events = [value[1] for value in values]
                    return (
                        min(revisions, default=0),
                        sum(revisions),
                        min(later_events, default=0),
                        sum(later_events),
                    )

                preferred_sample = max(
                    sudoku_samples,
                    key=lambda sample: (activity(sample), sample),
                )
                sudoku_sample = st.selectbox(
                    "样本",
                    sudoku_samples,
                    index=sudoku_samples.index(preferred_sample),
                    key="sudoku_trace_sample",
                )
        else:
            sudoku_sample = ""
            sample_column.info("所选运行没有共同样本。")

        for run in sudoku_runs if sudoku_sample else ():
            model_panel = st.expander(run, expanded=True)
            model_panel.caption(f"{sudoku_dataset} · {sudoku_sample}")
            record = record_for(run, sudoku_dataset, sudoku_sample)
            model, _, variant = run.partition("/")
            is_sudoku9 = sudoku_dataset.startswith("sudoku9")
            row_height = 460 if is_sudoku9 else 360
            animation_column, trace_column = model_panel.columns(
                [0.42, 0.58],
                gap="medium",
            )
            artifacts = trace_artifacts(
                paths, model=model, variant=variant,
                dataset=sudoku_dataset, sample=sudoku_sample,
            )
            command = trace_command(
                paths, model=model, variant=variant,
                dataset=sudoku_dataset, sample=sudoku_sample,
            )
            with animation_column:
                def preview_sudoku(record=record, run=run):
                    animation = sudoku_animation_figure(
                        record,
                        dataset=sudoku_dataset,
                        title="数独解题过程",
                    )
                    if animation is None:
                        st.info("该样本无法从原始 trace 对齐 Sudoku 区域。")
                    else:
                        animation.update_layout(
                            height=row_height,
                            margin=dict(l=20, r=10, t=52, b=62),
                        )
                        render_plotly(
                            animation,
                            key=f"sudoku_animation_{run}_{sudoku_dataset}_{sudoku_sample}",
                        )
                render_chart_panel(
                    paths,
                    title=tr("数独解题过程", "Sudoku solve"),
                    section="sudoku_trace",
                    key=f"{model}_{variant}_{sudoku_dataset}_{sudoku_sample}_board",
                    generated_path=artifacts["sudoku_trace"],
                    command=command,
                    preview=preview_sudoku,
                    prefer_generated=True,
                    generated_width="stretch",
                    generated_height=row_height,
                    compact_header=True,
                )
            with trace_column:
                def preview_accept(record=record, run=run):
                    if record.get("trace"):
                        token_trace = trace_figure(record, title="Token 接受与修改")
                        token_trace.update_layout(
                            height=row_height,
                            margin=dict(l=42, r=20, t=52, b=45),
                        )
                        render_plotly(
                            token_trace,
                            key=f"sudoku_trace_{run}_{sudoku_dataset}_{sudoku_sample}",
                            legend_title="",
                            margin=dict(l=55, r=20, t=75, b=50),
                        )
                    else:
                        st.info("该样本没有可用的 forward trace。")
                render_chart_panel(
                    paths,
                    title=tr("接受与修改轨迹", "Accept trace"),
                    section="sudoku_trace",
                    key=f"{model}_{variant}_{sudoku_dataset}_{sudoku_sample}_accept",
                    generated_path=artifacts["accept_trace"],
                    command=command,
                    preview=preview_accept,
                    prefer_generated=True,
                    generated_width="stretch",
                    generated_height=row_height,
                    compact_header=True,
                )
