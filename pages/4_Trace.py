from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from platform_core.maintenance import (
    list_trash_entries,
    move_output_paths_to_trash,
    restore_trash_entry,
)
from platform_core.results import (
    load_sample_scores,
    load_trace_assets,
    load_trace_summary_records,
)
from platform_core.selection import (
    dataset_label,
    select_dataset_subsets,
    select_model_variants,
    select_single_dataset,
)
from platform_core.ui import (
    configure_page,
    pausable_gif,
    paths_sidebar,
    require_ready,
    zoomable_image,
)
from platform_core.visualization import (
    child_directories,
    common_trace_datasets,
    common_trace_samples,
    launch_visualization,
    trace_command,
)


configure_page("Trace | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Trace")

model_output_root = paths.output_root / "model_output"


def trace_type(asset: dict) -> str:
    name = asset["name"]
    if name.endswith("_block_acceptance.png"):
        return "Block 内接受顺序"
    if name.endswith("_accept_trace.png"):
        return "Accept 更新"
    if name.endswith("_all_updates.png"):
        return "全部更新"
    if name.endswith("_sudoku_context_trace.gif"):
        return "数独生成动图"
    if name.endswith("_token_trace.gif"):
        return "Token 演化动图"
    if asset["suffix"] == ".csv":
        return "逐步数据"
    return asset["kind"]


def trashed_trace_entries(run_name: str, dataset_name: str, sample_name: str):
    prefix = f"visualization_output/{run_name}/{dataset_name}/".lower()
    sample_prefix = f"{sample_name}_".lower()
    return [
        entry
        for entry in list_trash_entries(paths.output_root)
        if str(entry.get("original_relative_path", ""))
        .replace("\\", "/")
        .lower()
        .startswith(prefix)
        and Path(str(entry.get("original_relative_path", "")))
        .name.lower()
        .startswith(sample_prefix)
    ]


@st.dialog("移入回收站")
def confirm_trace_delete(asset_paths: list[Path]) -> None:
    st.warning(f"将 {len(asset_paths)} 个 Trace 文件移入回收站？")
    cancel_column, confirm_column = st.columns(2)
    if cancel_column.button("取消", use_container_width=True, key="cancel_trace_delete"):
        st.rerun()
    if confirm_column.button(
        "确认删除",
        type="primary",
        use_container_width=True,
        key="confirm_trace_delete",
    ):
        move_output_paths_to_trash(paths.output_root, asset_paths)
        st.rerun()


assets = load_trace_assets(paths.output_root)
sample_trace_assets = [asset for asset in assets if asset["scope"] == "单样本轨迹"]
trace_summary_records = load_trace_summary_records(paths.output_root)
mode = st.radio(
    "查看方式",
    ["数据集级对比", "同题单样本对照"],
    horizontal=True,
)


trace_process = st.session_state.get("trace_visualization_process")
if trace_process is not None:

    @st.fragment(run_every=1.0)
    def poll_trace_generation() -> None:
        process = st.session_state.get("trace_visualization_process")
        if process is None:
            return
        return_code = process.poll()
        if return_code is None:
            label = st.session_state.get("trace_visualization_label", "Trace")
            st.info(f"正在生成 {label}，完成后会自动刷新。")
            return

        trace_log = st.session_state.get("trace_visualization_log")
        log_lines = []
        if trace_log:
            try:
                log_lines = Path(trace_log).read_text(
                    encoding="utf-8",
                    errors="replace",
                ).splitlines()
            except OSError:
                pass
        st.session_state.pop("trace_visualization_process", None)
        st.session_state.pop("trace_visualization_log", None)
        st.session_state.pop("trace_visualization_label", None)
        if return_code == 0:
            st.session_state.pop("trace_visualization_failure", None)
        else:
            st.session_state["trace_visualization_failure"] = {
                "return_code": return_code,
                "log_lines": log_lines[-30:],
            }
        st.rerun()

    poll_trace_generation()

trace_failure = st.session_state.get("trace_visualization_failure")
if trace_failure:
    st.error(f"生成失败，退出码：{trace_failure['return_code']}")
    if trace_failure["log_lines"]:
        with st.expander("生成日志", expanded=True):
            st.code("\n".join(trace_failure["log_lines"]), language="text")
    if st.button("关闭日志", key="dismiss_trace_failure"):
        st.session_state.pop("trace_visualization_failure", None)
        st.rerun()


if mode == "数据集级对比":
    raw_run_records = [
        {
            "model": model,
            "config": variant,
            "run": f"{model}/{variant}",
        }
        for model in child_directories(model_output_root)
        for variant in child_directories(model_output_root / model)
    ]
    if not raw_run_records:
        st.info("model_output 中没有可比较的运行。")
        st.stop()

    report_trace_runs = [
        run
        for run in (
            "dreamreasoner/p2",
            "illada/p2",
            "illada_vargen/p2",
            "illada_entropy/eb05",
        )
        if any(record["run"] == run for record in raw_run_records)
    ]
    if not report_trace_runs:
        report_trace_runs = [record["run"] for record in raw_run_records[:3]]

    metric_labels = {
        "block_local_tau": "Block 内接受顺序 τ",
        "accepted_tokens_per_forward": "每次 Forward 接受 token",
        "final_stable_tokens_per_forward": "每次 Forward 最终稳定 token",
        "accepted_tps": "接受 TPS",
    }
    with st.expander("选择模型、变体、数据集和 Trace 指标", expanded=True):
        selected_runs = select_model_variants(
            raw_run_records,
            default_runs=report_trace_runs,
            key_prefix="trace_comparison",
        )
        available_datasets = sorted(
            {
                dataset
                for run in selected_runs
                for dataset in child_directories(
                    model_output_root
                    / run.partition("/")[0]
                    / run.partition("/")[2]
                )
            }
        )
        default_trace_dataset = (
            "gsm8k"
            if "gsm8k" in available_datasets
            else "sudoku4_1shot"
            if "sudoku4_1shot" in available_datasets
            else available_datasets[0]
            if available_datasets
            else ""
        )
        selected_datasets = select_dataset_subsets(
            available_datasets,
            default_datasets=(default_trace_dataset,),
            key_prefix="trace_comparison",
        )
        available_metrics = list(metric_labels)
        selected_metrics = st.multiselect(
            "Trace 指标",
            available_metrics,
            default=[
                metric
                for metric in (
                    "block_local_tau",
                    "accepted_tokens_per_forward",
                )
                if metric in available_metrics
            ]
            or available_metrics[:1],
            format_func=metric_labels.get,
            key="trace_comparison_metrics",
        )

    if not selected_runs or not selected_datasets:
        st.info("请选择模型和数据集。")
        st.stop()

    selected_summaries = [
        record
        for record in trace_summary_records
        if record["run"] in selected_runs
        and record["dataset"] in selected_datasets
    ]
    summary_lookup = {
        (record["run"], record["dataset"]): record
        for record in selected_summaries
    }
    compact_rows = []
    for run in selected_runs:
        for dataset_name in selected_datasets:
            record = summary_lookup.get((run, dataset_name))
            metrics = record["metrics"] if record else {}
            row = {
                "模型 / 配置": run,
                "数据集": dataset_label(dataset_name),
            }
            for metric in selected_metrics:
                row[metric_labels[metric]] = metrics.get(metric)
            compact_rows.append(row)
    if compact_rows:
        compact_frame = pd.DataFrame(compact_rows)
        st.dataframe(
            compact_frame,
            width="stretch",
            hide_index=True,
            height=min(250, 36 * (len(compact_frame) + 1) + 4),
            column_config={
                "Block 内接受顺序 τ": st.column_config.NumberColumn(format="%.3f"),
                "每次 Forward 接受 token": st.column_config.NumberColumn(format="%.2f"),
                "每次 Forward 最终稳定 token": st.column_config.NumberColumn(format="%.2f"),
                "接受 TPS": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        if "block_local_tau" in selected_metrics:
            st.caption(
                "τ 越接近 1，block 内越倾向按位置从左到右稳定；"
                "接近 0 表示接受顺序与位置关系弱。"
            )
    else:
        st.warning("所选结果没有对应的数据集级 Trace 指标记录。")
else:
    source_entries = [
        {"model": model, "variant": variant, "run": f"{model}/{variant}"}
        for model in child_directories(model_output_root)
        for variant in child_directories(model_output_root / model)
    ]
    run_options = sorted(entry["run"] for entry in source_entries)
    if len(run_options) < 2:
        st.info("至少需要两个具有模型输出的运行。")
        st.stop()

    preferred_pair = [
        run
        for run in ("llada2_1/qmode", "diffusiongemma/official")
        if run in run_options
    ]
    selected_runs = st.multiselect(
        "选择两个运行",
        run_options,
        default=preferred_pair if len(preferred_pair) == 2 else run_options[:2],
        max_selections=2,
        key="paired_trace_runs",
    )
    if len(selected_runs) != 2:
        st.info("同题单样本对照必须且只能选择两个运行。")
        st.stop()

    common_datasets = common_trace_datasets(model_output_root, selected_runs)
    if not common_datasets:
        st.info("这两个运行没有共同的数据集，不能进行同题对照。")
        st.stop()

    dataset_name = select_single_dataset(
        common_datasets,
        key_prefix="paired_trace",
        default_dataset="sudoku4_1shot",
    )
    if dataset_name is None:
        st.stop()

    common_samples = common_trace_samples(
        model_output_root,
        selected_runs,
        dataset_name,
    )
    if not common_samples:
        st.info("这两个运行在该数据集上没有相同 sample，不能展示单样本对照。")
        st.stop()

    score_maps = {
        run: {
            record["sample"]: record["metrics"].get("primary_score")
            for record in load_sample_scores(paths.output_root, run, dataset_name)
        }
        for run in selected_runs
    }

    def paired_sample_label(sample_id: str) -> str:
        labels = []
        for run in selected_runs:
            score = score_maps[run].get(sample_id)
            labels.append(f"{run}: {'未评分' if score is None else f'{score:.3f}'}")
        return f"{sample_id} · " + " / ".join(labels)

    report_sample = "sudoku4-d1-0164"
    sample_name = st.selectbox(
        "双方共有的 sample",
        common_samples,
        index=(
            common_samples.index(report_sample)
            if dataset_name == "sudoku4_1shot" and report_sample in common_samples
            else 0
        ),
        key="paired_trace_sample",
        format_func=paired_sample_label,
    )

    pair_assets = [
        asset
        for asset in sample_trace_assets
        if asset["model"] in selected_runs
        and asset["dataset"] == dataset_name
        and asset["sample"] == sample_name
    ]
    types_by_run = {
        run: {
            trace_type(asset)
            for asset in pair_assets
            if asset["model"] == run
        }
        for run in selected_runs
    }
    common_types = sorted(set.intersection(*types_by_run.values()))
    if common_types:
        selected_types = st.multiselect(
            "双方共有的 Trace 类型",
            common_types,
            default=[
                name
                for name in (
                    "数独生成动图",
                    "Token 演化动图",
                    "Accept 更新",
                )
                if name in common_types
            ]
            or common_types[:1],
            key="paired_trace_types",
        )
    else:
        selected_types = []
        st.info("双方目前没有已生成的同类型 Trace；可分别点击 Generate 生成。")

    st.caption(
        "这里只展示双方共有的数据集、同一个 sample 和同一种 Trace 类型；"
        "每一种图单独占一行，左右始终是同类型对照。"
    )
    assets_by_run = {
        run: [asset for asset in pair_assets if asset["model"] == run]
        for run in selected_runs
    }

    header_columns = st.columns(2)
    for column, run in zip(header_columns, selected_runs):
        with column:
            score = score_maps[run].get(sample_name)
            score_text = "未评分" if score is None else f"主分 {score:.4f}"
            st.markdown(f"### {run}")
            st.caption(f"{dataset_label(dataset_name)} · {sample_name} · {score_text}")
            all_run_assets = assets_by_run[run]
            recycled_assets = trashed_trace_entries(run, dataset_name, sample_name)
            action_left, action_right = st.columns(2)
            if all_run_assets:
                if action_left.button(
                    "Delete",
                    key=f"delete_pair_{run}_{dataset_name}_{sample_name}",
                    use_container_width=True,
                ):
                    confirm_trace_delete(
                        [asset["path"] for asset in all_run_assets]
                    )
            elif recycled_assets:
                if action_left.button(
                    "Restore",
                    key=f"restore_pair_{run}_{dataset_name}_{sample_name}",
                    use_container_width=True,
                ):
                    restored = 0
                    for entry in recycled_assets:
                        try:
                            restore_trash_entry(paths.output_root, entry["id"])
                        except FileExistsError:
                            continue
                        else:
                            restored += 1
                    if restored:
                        st.rerun()

            needs_generation = not all_run_assets or not common_types
            if needs_generation and action_right.button(
                "Generate",
                key=f"generate_pair_{run}_{dataset_name}_{sample_name}",
                use_container_width=True,
                disabled=st.session_state.get("trace_visualization_process")
                is not None,
            ):
                model, _, variant = run.partition("/")
                command = trace_command(
                    paths,
                    model=model,
                    variant=variant,
                    dataset=dataset_name,
                    sample=sample_name,
                )
                process, log_path = launch_visualization(paths, command)
                st.session_state.pop("trace_visualization_failure", None)
                st.session_state["trace_visualization_process"] = process
                st.session_state["trace_visualization_log"] = str(log_path)
                st.session_state["trace_visualization_label"] = (
                    f"{run} · {dataset_name} · {sample_name}"
                )
                st.rerun()

            if not all_run_assets:
                st.info(
                    "图片在回收站中，可先 Restore。"
                    if recycled_assets
                    else "该运行尚未生成这个 sample 的 Trace 图片。"
                )

    for selected_type in selected_types:
        st.markdown(f"#### {selected_type}")
        type_columns = st.columns(2)
        for column, run in zip(type_columns, selected_runs):
            with column:
                matching_assets = [
                    asset
                    for asset in assets_by_run[run]
                    if trace_type(asset) == selected_type
                ]
                if not matching_assets:
                    st.info(f"{run} 缺少 {selected_type}。")
                    continue
                for asset in matching_assets:
                    if asset["suffix"] == ".gif":
                        pausable_gif(asset["path"], caption=run)
                    elif asset["suffix"] == ".png":
                        zoomable_image(
                            asset["path"],
                            caption=run,
                            preview_width="100%",
                        )
                    elif asset["suffix"] == ".csv":
                        try:
                            frame = pd.read_csv(asset["path"])
                        except (OSError, pd.errors.ParserError) as exc:
                            st.error(f"无法读取 {asset['name']}：{exc}")
                        else:
                            st.dataframe(frame, width="stretch", hide_index=True)
