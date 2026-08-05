from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from platform_core.results import load_sample_scores, load_trace_assets
from platform_core.maintenance import (
    list_trash_entries,
    move_output_paths_to_trash,
    restore_trash_entry,
)
from platform_core.selection import select_single_dataset
from platform_core.visualization import (
    child_directories,
    launch_visualization,
    sample_ids,
    trace_command,
)
from platform_core.ui import (
    configure_page,
    pausable_gif,
    paths_sidebar,
    require_ready,
    zoomable_image,
)


configure_page("Trace | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Trace")

model_output_root = paths.output_root / "model_output"
def trashed_trace_entries(run_name: str, dataset_name: str, sample_name: str):
    prefix = f"visualization_output/{run_name}/{dataset_name}/".lower()
    sample_prefix = f"{sample_name}_".lower()
    return [
        entry
        for entry in list_trash_entries(paths.output_root)
        if str(entry.get("original_relative_path", "")).replace("\\", "/").lower().startswith(prefix)
        and Path(str(entry.get("original_relative_path", ""))).name.lower().startswith(sample_prefix)
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
mode_options = ["单样本轨迹"]
if any(asset["scope"] == "模型对比" for asset in assets):
    mode_options.insert(0, "模型对比")
mode = st.radio(
    "查看方式",
    mode_options,
    horizontal=True,
)
mode_assets = [asset for asset in assets if asset["scope"] == mode]

if mode == "模型对比":
    model_options = sorted({asset["model"] for asset in mode_assets})
    model_name = st.selectbox("模型", model_options)
    model_assets = [asset for asset in mode_assets if asset["model"] == model_name]
    dataset_name = select_single_dataset(
        {asset["dataset"] for asset in model_assets},
        key_prefix="trace_comparison",
    )
    selected = [asset for asset in model_assets if asset["dataset"] == dataset_name]

    if selected:
        delete_column, _ = st.columns([1, 7])
        if delete_column.button("Delete", key="delete_trace_comparison"):
            confirm_trace_delete([asset["path"] for asset in selected])

    image_assets = [asset for asset in selected if asset["suffix"] == ".png"]
    kind_order = {
        "Accept trace": 0,
        "Forward 效率": 1,
        "首次接受": 2,
        "位置状态": 3,
        "逐步接受": 4,
        "答案区域": 5,
        "Trace": 6,
    }
    image_assets.sort(key=lambda asset: kind_order.get(asset["kind"], 20))
    if image_assets:
        labels = [f"{asset['kind']} · {asset['name']}" for asset in image_assets]
        selected_label = st.selectbox("图表", labels)
        selected_image = image_assets[labels.index(selected_label)]
        zoomable_image(
            selected_image["path"],
            caption=selected_image["kind"],
        )

    csv_assets = [asset for asset in selected if asset["suffix"] == ".csv"]
    if csv_assets:
        with st.expander("逐步数据"):
            for asset in csv_assets:
                st.caption(asset["name"])
                try:
                    frame = pd.read_csv(asset["path"])
                except (OSError, pd.errors.ParserError) as exc:
                    st.error(f"无法读取 {asset['name']}: {exc}")
                else:
                    st.dataframe(frame, width="stretch", hide_index=True)

else:
    source_entries = [
        {
            "model": model,
            "variant": variant,
            "run": f"{model}/{variant}",
        }
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
            key="trace_sample_variant",
        )
        run_name = f"{source_model}/{source_variant}"

        source_datasets = child_directories(
            model_output_root / source_model / source_variant
        )
        dataset_name = select_single_dataset(
            source_datasets,
            key_prefix="trace_sample",
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
            if score is None:
                return f"⚪ 未评分 · {sample_id}"
            if score >= 0.8:
                marker = "🟢"
            elif score >= 0.5:
                marker = "🟡"
            else:
                marker = "🔴"
            return f"{marker} {score:.3f} · {sample_id}"

        sample_name = st.selectbox(
            "样本",
            available_samples,
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
        for asset in assets
        if asset["scope"] == "单样本轨迹"
        and asset["model"] == run_name
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
            st.rerun()

    trace_process = st.session_state.get("trace_visualization_process")
    if trace_process is not None:
        @st.fragment(run_every=1.0)
        def poll_trace_generation() -> None:
            process = st.session_state.get("trace_visualization_process")
            if process is None:
                return
            return_code = process.poll()
            if return_code is None:
                st.info("正在生成 Trace 图片，完成后会自动刷新。")
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

    gif_assets = [asset for asset in sample_assets if asset["suffix"] == ".gif"]
    image_assets = [asset for asset in sample_assets if asset["suffix"] == ".png"]
    left, right = st.columns(2)
    with left:
        st.subheader("生成过程")
        if gif_assets:
            pausable_gif(
                gif_assets[0]["path"],
                caption="答案区域动图",
            )
        else:
            st.info("该样本没有生成动图。")
    with right:
        st.subheader("关键更新")
        if image_assets:
            zoomable_image(
                image_assets[0]["path"],
                caption="Accept 与修改",
            )
        else:
            st.info("该样本没有关键帧图。")
