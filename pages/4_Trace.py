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
    launch_visualization,
    sample_ids,
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


def score_marker(score: float | None) -> str:
    if score is None:
        return "⚪"
    if score >= 0.8:
        return "🟢"
    if score >= 0.5:
        return "🟡"
    return "🔴"


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
    ["模型对比", "单样本轨迹"],
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


if mode == "模型对比":
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

    sudoku_sample = "sudoku4-d1-0004"
    sudoku_case_root = paths.output_root / "visualization_output"
    sudoku_case_assets = {
        "LLaDA2.1 / qmode": sudoku_case_root
        / "llada2_1"
        / "qmode"
        / "sudoku4_1shot"
        / f"{sudoku_sample}_token_trace.gif",
        "DiffusionGemma / official": sudoku_case_root
        / "diffusiongemma"
        / "official"
        / "sudoku4_1shot"
        / f"{sudoku_sample}_token_trace.gif",
    }
    available_sudoku_case_assets = {
        label: path for label, path in sudoku_case_assets.items() if path.is_file()
    }
    if available_sudoku_case_assets:
        st.subheader("数独同题 Trace：LLaDA2.1 vs DiffusionGemma")
        st.caption(
            f"固定展示同一样本 {sudoku_sample}。该样本按共同 Trace 的最终输出长度中位数规则选择，"
            "用于观察生成过程，不代表总体准确率。"
        )
        selected_sudoku_models = st.multiselect(
            "展示模型",
            list(available_sudoku_case_assets),
            default=list(available_sudoku_case_assets),
            key="sudoku_case_models",
        )
        if selected_sudoku_models:
            columns = st.columns(len(selected_sudoku_models))
            for column, label in zip(columns, selected_sudoku_models):
                with column:
                    st.markdown(f"**{label}**")
                    pausable_gif(
                        available_sudoku_case_assets[label],
                        caption=f"{label} · Token 演化",
                    )
        else:
            st.info("请选择 LLaDA2.1、DiffusionGemma，或同时选择两者。")

        comparison_root = (
            sudoku_case_root / "sudoku_model_comparison" / "sudoku4_1shot"
        )
        comparison_figures = (
            ("位置状态", comparison_root / "trace_position_state.png"),
            ("接受与修订", comparison_root / "accept_trace.png"),
        )
        existing_figures = [item for item in comparison_figures if item[1].is_file()]
        if len(selected_sudoku_models) == 2 and existing_figures:
            figure_columns = st.columns(len(existing_figures))
            for column, (caption, path) in zip(figure_columns, existing_figures):
                with column:
                    zoomable_image(path, caption=caption)
        st.divider()

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
        st.warning("所选结果没有对应的 Trace 指标记录。")

    tau_by_run_dataset = {
        key: record["metrics"].get("block_local_tau")
        for key, record in summary_lookup.items()
    }

    comparison_assets = [
        asset
        for asset in sample_trace_assets
        if asset["model"] in selected_runs
        and asset["dataset"] in selected_datasets
    ]
    if not comparison_assets:
        st.caption("原始 Trace 已记录，但当前选择还没有生成单样本图片。")

    st.subheader("真实 Trace 对比")
    available_types = sorted({trace_type(asset) for asset in comparison_assets}) or [
        "Accept 更新"
    ]
    default_types = [
        name
        for name in ("Block 内接受顺序", "Accept 更新")
        if name in available_types
    ]
    trace_control, trace_note = st.columns([2, 3], vertical_alignment="bottom")
    with trace_control:
        selected_types = st.multiselect(
            "Trace 图",
            available_types,
            default=default_types or available_types[:1],
            key="trace_comparison_types",
        )
    with trace_note:
        st.caption("图像使用同一数据集、同一样本并排展示；τ 来自该运行的数据集级汇总。")

    if not selected_types:
        st.stop()

    for dataset_name in selected_datasets:
        dataset_all_assets = [
            asset
            for asset in comparison_assets
            if asset["dataset"] == dataset_name
        ]
        dataset_assets = [
            asset
            for asset in dataset_all_assets
            if trace_type(asset) in selected_types
        ]
        samples_by_run = {
            run: set(
                sample_ids(
                    model_output_root
                    / run.partition("/")[0]
                    / run.partition("/")[2]
                    / dataset_name
                )
            )
            for run in selected_runs
        }
        nonempty_sample_sets = [samples for samples in samples_by_run.values() if samples]
        if not nonempty_sample_sets:
            st.warning(f"{dataset_label(dataset_name)} 没有原始模型输出。")
            continue
        common_samples = sorted(set.intersection(*nonempty_sample_sets))
        sample_options = common_samples or sorted(set.union(*nonempty_sample_sets))

        score_maps = {
            run: {
                record["sample"]: record["metrics"].get("primary_score")
                for record in load_sample_scores(paths.output_root, run, dataset_name)
            }
            for run in selected_runs
        }

        def comparison_sample_label(sample_id: str) -> str:
            scores = [
                score_maps[run].get(sample_id)
                for run in selected_runs
                if score_maps[run].get(sample_id) is not None
            ]
            average = sum(scores) / len(scores) if scores else None
            coverage = sum(sample_id in samples_by_run[run] for run in selected_runs)
            score_text = "未评分" if average is None else f"均分 {average:.3f}"
            return (
                f"{score_marker(average)} {score_text} · "
                f"{coverage}/{len(selected_runs)} 个运行 · {sample_id}"
            )

        st.subheader(dataset_label(dataset_name))
        if not common_samples and len(selected_runs) > 1:
            st.caption("所选运行没有完全相同的 Trace 样本；缺失位置会保留为空。")
        sample_name = st.selectbox(
            "样本",
            sample_options,
            format_func=comparison_sample_label,
            key=f"trace_comparison_sample_{dataset_name}",
        )

        for start in range(0, len(selected_runs), 2):
            row_runs = selected_runs[start : start + 2]
            columns = st.columns(len(row_runs))
            for column, run in zip(columns, row_runs):
                with column:
                    score = score_maps[run].get(sample_name)
                    tau = tau_by_run_dataset.get((run, dataset_name))
                    tau_text = "N/A" if tau is None else f"{tau:.3f}"
                    score_text = "未评分" if score is None else f"主分 {score:.4f}"
                    st.markdown(f"**{run}** · `τ = {tau_text}`")
                    st.caption(score_text)
                    all_run_assets = [
                        asset
                        for asset in dataset_all_assets
                        if asset["model"] == run and asset["sample"] == sample_name
                    ]
                    run_assets = [
                        asset
                        for asset in dataset_assets
                        if asset["model"] == run and asset["sample"] == sample_name
                    ]
                    recycled_assets = trashed_trace_entries(
                        run,
                        dataset_name,
                        sample_name,
                    )
                    action_left, action_right = st.columns(2)
                    if all_run_assets:
                        if action_left.button(
                            "Delete",
                            key=f"delete_comparison_{run}_{dataset_name}_{sample_name}",
                            use_container_width=True,
                        ):
                            confirm_trace_delete(
                                [asset["path"] for asset in all_run_assets]
                            )
                    elif recycled_assets:
                        if action_left.button(
                            "Restore",
                            key=f"restore_comparison_{run}_{dataset_name}_{sample_name}",
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

                    needs_generation = (
                        not all_run_assets and not recycled_assets
                    ) or (bool(all_run_assets) and not run_assets)
                    if needs_generation:
                        model, _, variant = run.partition("/")
                        if action_right.button(
                            "Generate",
                            key=f"generate_comparison_{run}_{dataset_name}_{sample_name}",
                            use_container_width=True,
                            disabled=st.session_state.get(
                                "trace_visualization_process"
                            )
                            is not None,
                        ):
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
                        message = (
                            "图片在回收站中，可先 Restore。"
                            if recycled_assets
                            else "原始 Trace 已记录，尚未生成图片。"
                        )
                        st.info(message)
                        continue
                    if not run_assets:
                        st.info("已有其他 Trace 图片，但所选图尚未生成。")
                        continue
                    run_assets.sort(
                        key=lambda asset: selected_types.index(trace_type(asset))
                    )
                    for asset in run_assets:
                        if asset["suffix"] == ".gif":
                            pausable_gif(asset["path"], caption=trace_type(asset))
                        elif asset["suffix"] == ".png":
                            zoomable_image(asset["path"], caption=trace_type(asset))
                        elif asset["suffix"] == ".csv":
                            try:
                                frame = pd.read_csv(asset["path"])
                            except (OSError, pd.errors.ParserError) as exc:
                                st.error(f"无法读取 {asset['name']}：{exc}")
                            else:
                                st.dataframe(frame, width="stretch", hide_index=True)


else:
    source_entries = [
        {"model": model, "variant": variant, "run": f"{model}/{variant}"}
        for model in child_directories(model_output_root)
        for variant in child_directories(model_output_root / model)
    ]
    if not source_entries:
        st.info("model_output 中没有可生成 Trace 的结果。")
        st.stop()

    with st.expander("选择模型、变体、数据集和样本", expanded=True):
        source_models = sorted({entry["model"] for entry in source_entries})
        default_model = (
            source_models.index("diffusiongemma")
            if "diffusiongemma" in source_models
            else 0
        )
        source_model = st.selectbox(
            "主模型",
            source_models,
            index=default_model,
            key="trace_sample_model",
        )
        source_variants = sorted(
            entry["variant"]
            for entry in source_entries
            if entry["model"] == source_model
        )
        source_variant = st.selectbox(
            "变体 / 运行",
            source_variants,
            index=(
                source_variants.index("official")
                if "official" in source_variants
                else 0
            ),
            key="trace_sample_variant",
        )
        run_name = f"{source_model}/{source_variant}"

        source_datasets = child_directories(
            model_output_root / source_model / source_variant
        )
        dataset_name = select_single_dataset(
            source_datasets,
            key_prefix="trace_sample",
            default_dataset="sudoku4_1shot",
        )
        if dataset_name is None:
            st.info("当前模型变体没有可用数据集。")
            st.stop()

        available_samples = sample_ids(
            model_output_root / source_model / source_variant / dataset_name
        )
        if not available_samples:
            st.info("当前数据集没有可用样本。")
            st.stop()
        score_records = load_sample_scores(paths.output_root, run_name, dataset_name)
        scores_by_sample = {
            record["sample"]: record["metrics"].get("primary_score")
            for record in score_records
        }

        def sample_label(sample_id: str) -> str:
            score = scores_by_sample.get(sample_id)
            score_text = "未评分" if score is None else f"{score:.3f}"
            return f"{score_marker(score)} {score_text} · {sample_id}"

        report_sample = "sudoku4-d1-0004"
        sample_name = st.selectbox(
            "样本",
            available_samples,
            index=(
                available_samples.index(report_sample)
                if dataset_name == "sudoku4_1shot"
                and report_sample in available_samples
                else 0
            ),
            key="trace_sample_id",
            format_func=sample_label,
        )
        selected_score = scores_by_sample.get(sample_name)
        if selected_score is None:
            st.caption("当前样本尚未评分。绿色 ≥ 0.8，黄色 ≥ 0.5，红色 < 0.5。")
        else:
            score_color = (
                "#18794e"
                if selected_score >= 0.8
                else "#9a6700"
                if selected_score >= 0.5
                else "#b42318"
            )
            st.markdown(
                f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
                f'background:{score_color}18;color:{score_color};font-weight:600;">'
                f'样本主分 {selected_score:.4f}</span>',
                unsafe_allow_html=True,
            )
            st.caption("绿色 ≥ 0.8，黄色 ≥ 0.5，红色 < 0.5。")

    sample_assets = [
        asset
        for asset in sample_trace_assets
        if asset["model"] == run_name
        and asset["dataset"] == dataset_name
        and asset["sample"] == sample_name
    ]
    recycled_assets = trashed_trace_entries(run_name, dataset_name, sample_name)

    action_column, _ = st.columns([1, 7])
    with action_column:
        if sample_assets:
            if st.button("Delete", key="delete_trace_sample", use_container_width=True):
                confirm_trace_delete([asset["path"] for asset in sample_assets])
        elif recycled_assets:
            if st.button("Restore", key="restore_trace_sample", use_container_width=True):
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
        elif st.button("Generate", key="generate_trace_sample", use_container_width=True):
            command = trace_command(
                paths,
                model=source_model,
                variant=source_variant,
                dataset=dataset_name,
                sample=sample_name,
            )
            process, log_path = launch_visualization(paths, command)
            st.session_state.pop("trace_visualization_failure", None)
            st.session_state["trace_visualization_process"] = process
            st.session_state["trace_visualization_log"] = str(log_path)
            st.session_state["trace_visualization_label"] = (
                f"{run_name} · {dataset_name} · {sample_name}"
            )
            st.rerun()

    gif_assets = [asset for asset in sample_assets if asset["suffix"] == ".gif"]
    image_assets = [asset for asset in sample_assets if asset["suffix"] == ".png"]
    left, right = st.columns(2)
    with left:
        st.subheader("生成过程")
        if gif_assets:
            for asset in gif_assets:
                pausable_gif(asset["path"], caption="答案区域动图")
        else:
            st.info("该样本没有生成动图。")
    with right:
        st.subheader("关键更新")
        if image_assets:
            for asset in image_assets:
                zoomable_image(asset["path"], caption=trace_type(asset))
        else:
            st.info("该样本没有关键更新图。")
