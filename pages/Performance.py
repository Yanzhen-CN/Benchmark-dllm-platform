from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from platform_core.compare import render_comparison
from platform_core.chart_panel import plotly_spec, render_chart_panel
from platform_core.i18n import tr
from platform_core.profiling import load_profiling_detail_records
from platform_core.results import (
    available_metrics,
    default_comparison_runs,
    datasets,
    load_summary_records,
    metric_label,
)
from platform_core.selection import (
    select_dataset_subsets,
    select_model_variants,
    select_single_dataset,
)
from platform_core.ui import (
    configure_page,
    paths_sidebar,
    render_plotly_chart as render_plotly,
    require_ready,
)


configure_page("性能对比 | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Performance")


def average_power(record):
    metrics = record["performance_metrics"]
    if metrics.get("eps") is not None:
        return metrics["eps"]
    energy = metrics.get("energy_per_sample")
    elapsed = metrics.get("time_per_sample")
    if energy is not None and elapsed:
        return energy / elapsed
    total_energy = metrics.get("total_energy_joules")
    total_time = metrics.get("total_time_seconds")
    if total_energy is not None and total_time:
        return total_energy / total_time
    return None


records = load_summary_records(paths.output_root)
if not records:
    st.warning("没有找到正式 score_output 结果。")
    st.stop()

performance_sections = {
    "raw": tr("原始性能", "Raw performance"),
    "adjusted": tr("可选资源折算", "Resource adjustment"),
    "profiling": "Profiling",
}
performance_section = st.segmented_control(
    tr("页面", "Section"),
    list(performance_sections),
    default="raw",
    format_func=performance_sections.get,
    label_visibility="collapsed",
    key="performance_section",
)


if performance_section == "raw":
    with st.expander(tr("选择数据集、模型和指标", "Select a dataset, models, and metrics"), expanded=True):
        dataset_name = select_single_dataset(
            datasets(records),
            key_prefix="performance",
        )
        dataset_records = [
            record for record in records if record["dataset"] == dataset_name
        ]
        selected_runs = select_model_variants(
            dataset_records,
            default_runs=default_comparison_runs([dataset_name]),
            key_prefix="performance",
        )
        selected_records = [
            record for record in dataset_records if record["run"] in selected_runs
        ]
        default_metrics = [
            "primary_score",
            "peak_vram_gb",
            "energy_per_sample",
            "time_per_sample",
            "eps",
            "accepted_tps",
        ]
        available = available_metrics(selected_records, "performance_metrics")
        metric_options = default_metrics + [
            name for name in available if name not in default_metrics
        ]
        selected_metric_values = st.multiselect(
            tr("性能指标", "Performance metrics"),
            metric_options,
            default=default_metrics,
            format_func=metric_label,
        )
        selected_metrics = [
            metric for metric in metric_options if metric in selected_metric_values
        ]

    rows = []
    for record in selected_records:
        for metric in selected_metrics:
            rows.append(
                {
                    "模型": record["run"],
                    "metric": metric_label(metric),
                    "value": (
                        record["primary_score"]
                        if metric == "primary_score"
                        else record["performance_metrics"].get(metric)
                    ),
                }
            )

    overview_rows = [row for row in rows if row["value"] is not None]
    overview_panel = st.expander(
        tr("原始性能总览", "Raw performance overview"), expanded=True
    )
    if overview_rows:
        with overview_panel:
            render_chart_panel(
                paths,
                title=tr("原始性能总览", "Raw performance overview"),
                section="performance",
                key=f"raw_overview_{dataset_name}",
                spec={
                    "kind": "bar",
                    "rows": overview_rows,
                    "facet_key": "metric",
                    "category_key": "模型",
                    "value_key": "value",
                },
                preview=lambda: render_comparison(overview_rows, row_key="模型"),
            )

    with st.expander(tr("单项指标", "Individual metrics")):
        chart_columns = st.columns(2)
        for index, metric in enumerate(selected_metrics):
            label = metric_label(metric)
            metric_rows = [
                row
                for row in rows
                if row["metric"] == label and row["value"] is not None
            ]
            with chart_columns[index % 2]:
                if metric_rows:
                    render_chart_panel(
                        paths,
                        title=label,
                        section="performance",
                        key=f"raw_{dataset_name}_{metric}",
                        spec={
                            "kind": "bar",
                            "rows": metric_rows,
                            "facet_key": "metric",
                            "category_key": "模型",
                            "value_key": "value",
                        },
                        preview=lambda rows=metric_rows: render_comparison(rows, row_key="模型"),
                    )
                else:
                    st.markdown(f"#### {label}")
                    st.info("暂无记录")

    if rows:
        raw_frame = pd.DataFrame(rows).rename(
            columns={"metric": "指标", "value": "数值"}
        )
        raw_frame["数值"] = raw_frame["数值"].where(
            raw_frame["数值"].notna(), ""
        )
        with overview_panel:
            st.markdown(f"#### {tr('原始数值', 'Raw values')}")
            st.dataframe(raw_frame, width="stretch", hide_index=True)
            if any(row["value"] is None for row in rows):
                st.caption("空白表示当前结果没有记录该指标。")


elif performance_section == "adjusted":
    eligible_adjusted_records = [
        record
        for record in records
        if record["primary_score"] is not None
        and record["performance_metrics"].get("time_per_sample")
        and average_power(record) is not None
    ]
    run_names = sorted({record["run"] for record in eligible_adjusted_records})
    run_records = {}
    for record in eligible_adjusted_records:
        run_records.setdefault(record["run"], record)
    model_names = sorted({record["model"] for record in run_records.values()})
    base_run = None
    target_run = None
    if len(run_names) >= 2:
        choose_left, choose_right = st.columns(2)
        default_base_model = (
            run_records["gemma_ar-baseline"]["model"]
            if "gemma_ar-baseline" in run_records
            else model_names[0]
        )
        default_target_model = (
            run_records["diffusiongemma_official"]["model"]
            if "diffusiongemma_official" in run_records
            else model_names[min(1, len(model_names) - 1)]
        )
        with choose_left:
            base_model = st.selectbox(
                "基线模型",
                model_names,
                index=model_names.index(default_base_model),
                key="adjusted_base_model",
            )
            base_run_options = [
                run
                for run in run_names
                if run_records[run]["model"] == base_model
            ]
            base_default = (
                base_run_options.index("gemma_ar-baseline")
                if "gemma_ar-baseline" in base_run_options
                else 0
            )
            base_run = st.selectbox(
                "基线变体",
                base_run_options,
                index=base_default,
                format_func=lambda run: run_records[run]["config"],
                key="adjusted_base_run",
            )
        with choose_right:
            target_model = st.selectbox(
                "折算模型",
                model_names,
                index=model_names.index(default_target_model),
                key="adjusted_target_model",
            )
            target_run_options = [
                run
                for run in run_names
                if run_records[run]["model"] == target_model
            ]
            target_default = (
                target_run_options.index("diffusiongemma_official")
                if "diffusiongemma_official" in target_run_options
                else 0
            )
            target_run = st.selectbox(
                "折算变体",
                target_run_options,
                index=target_default,
                format_func=lambda run: run_records[run]["config"],
                key="adjusted_target_run",
            )

    runs_by_dataset = {}
    for record in eligible_adjusted_records:
        runs_by_dataset.setdefault(record["dataset"], set()).add(record["run"])
    adjusted_datasets = sorted(
        dataset_name
        for dataset_name, available_runs in runs_by_dataset.items()
        if base_run in available_runs and target_run in available_runs
    )
    selected_adjusted_datasets = select_dataset_subsets(
        adjusted_datasets,
        default_datasets=["gsm8k"] if "gsm8k" in adjusted_datasets else adjusted_datasets[:1],
        key_prefix="adjusted",
    )
    dataset_run_maps = {
        dataset_name: {
            record["run"]: record
            for record in eligible_adjusted_records
            if record["dataset"] == dataset_name
        }
        for dataset_name in selected_adjusted_datasets
    }

    if len(run_names) < 2:
        st.warning("至少需要两个具备主分、时间和功率记录的模型。")
    elif base_run == target_run:
        st.info("请选择两个不同的模型进行折算。")
    elif not adjusted_datasets:
        st.info("这两个模型没有共同的完整数据集结果。")
    elif not selected_adjusted_datasets:
        st.info("请选择至少一个数据集。")
    else:
        parameter_left, parameter_right = st.columns(2)
        beta = parameter_left.slider(
            "beta · 资源影响",
            0,
            100,
            50,
            1,
            format="%d%%",
            help="控制速度和功率差异对折算结果的整体影响。",
        )
        gamma = parameter_right.slider(
            "gamma · 功率权重",
            0,
            100,
            50,
            1,
            format="%d%%",
            help="数值越高越看重功率，越低越看重速度。",
        )

        comparison_rows = []
        incomplete_datasets = []
        for selected_dataset in selected_adjusted_datasets:
            base = dataset_run_maps[selected_dataset][base_run]
            target = dataset_run_maps[selected_dataset][target_run]
            base_time = base["performance_metrics"].get("time_per_sample")
            target_time = target["performance_metrics"].get("time_per_sample")
            base_power = average_power(base)
            target_power = average_power(target)
            if not all((base_time, target_time, base_power, target_power)):
                incomplete_datasets.append(selected_dataset)
                continue

            speed_ratio = base_time / target_time
            power_ratio = base_power / target_power
            speed_delta = 1.0 - 1.0 / speed_ratio
            power_delta = 1.0 - 1.0 / power_ratio
            resource_delta = beta / 100.0 * (
                (100.0 - gamma) / 100.0 * speed_delta
                + gamma / 100.0 * power_delta
            )
            comparison_rows.append(
                {
                    "数据集": selected_dataset,
                    "基线分数": base["primary_score"],
                    "目标原始分数": target["primary_score"],
                    "速度倍率": speed_ratio,
                    "功率倍率": power_ratio,
                    "资源修正": resource_delta,
                    "目标折算分数": target["primary_score"] + resource_delta,
                }
            )

        if incomplete_datasets:
            st.warning(
                "以下数据集缺少时间或功率记录，未参与折算："
                + "、".join(incomplete_datasets)
            )

        if comparison_rows:
            color_map = {base_run: "#52796f", target_run: "#e76f51"}
            chart_columns = st.columns(2)

            raw_rows = []
            adjusted_rows = []
            for row in comparison_rows:
                raw_rows.extend(
                    [
                        {"数据集": row["数据集"], "模型": base_run, "数值": row["基线分数"]},
                        {"数据集": row["数据集"], "模型": target_run, "数值": row["目标原始分数"]},
                    ]
                )
                adjusted_rows.extend(
                    [
                        {"数据集": row["数据集"], "模型": base_run, "数值": row["基线分数"]},
                        {"数据集": row["数据集"], "模型": target_run, "数值": row["目标折算分数"]},
                    ]
                )

            raw_figure = px.bar(
                pd.DataFrame(raw_rows),
                x="数据集",
                y="数值",
                color="模型",
                barmode="group",
                title="原始分数",
                text_auto=".4g",
                color_discrete_map=color_map,
            )
            raw_figure.update_traces(textposition="outside", cliponaxis=False)
            raw_figure.update_layout(height=350, yaxis_title="分数")
            with chart_columns[0]:
                render_chart_panel(
                    paths,
                    title=tr("原始分数", "Original score"),
                    section="performance_adjusted",
                    collapsible=True,
                    key="original_score",
                    spec=plotly_spec(raw_figure),
                    preview=lambda: render_plotly(raw_figure, key="adjusted_raw_score"),
                )

            adjusted_figure = px.bar(
                pd.DataFrame(adjusted_rows),
                x="数据集",
                y="数值",
                color="模型",
                barmode="group",
                title="折算结果",
                text_auto=".4g",
                color_discrete_map=color_map,
            )
            adjusted_figure.update_traces(textposition="outside", cliponaxis=False)
            adjusted_figure.update_layout(height=380, yaxis_title="分数")
            adjusted_figure.add_annotation(
                x=1,
                y=1.12,
                xref="paper",
                yref="paper",
                text=f"beta = {beta}% · gamma = {gamma}%",
                showarrow=False,
                xanchor="right",
                font=dict(size=12, color="#555"),
                bgcolor="rgba(245, 245, 245, 0.9)",
                bordercolor="#d0d0d0",
                borderwidth=1,
                borderpad=5,
            )
            def render_adjusted_details() -> None:
                st.markdown("#### 倍率与精确数值")
                st.dataframe(
                    pd.DataFrame(comparison_rows),
                    width="stretch",
                    hide_index=True,
                )
                with st.expander("折算公式"):
                    st.code(
                        "q_adjusted = q + beta/100 * "
                        "[(100-gamma)/100 * delta_speed + "
                        "gamma/100 * delta_power]"
                    )
                    st.caption("每个数据集独立计算，不跨数据集求平均。")

            with chart_columns[1]:
                render_chart_panel(
                    paths,
                    title=tr("折算分数", "Adjusted score"),
                    section="performance_adjusted",
                    collapsible=True,
                    key=f"adjusted_score_b{beta}_g{gamma}",
                    spec=plotly_spec(adjusted_figure),
                    preview=lambda: render_plotly(adjusted_figure, key="adjusted_score"),
                    footer=render_adjusted_details,
                )


elif performance_section == "profiling":
    st.subheader("Profiling")
    profiling_details = load_profiling_detail_records(
        paths.output_root, paths.benchmark_root
    )
    if not profiling_details:
        st.info("model_profiling 中没有可用的单样本记录。")
    else:
        analysis_labels = {
            "accepted_tokens_per_second": tr(
                "端到端接受吞吐（token/s）",
                "End-to-end accepted throughput (token/s)",
            ),
            "compute_per_second": tr("计算速度（TFLOP/s）", "Compute throughput (TFLOP/s)"),
            "compute_tflops": tr("总计算量（TFLOP）", "Total compute (TFLOP)"),
            "compute_per_accepted_token": tr("每接受 token 计算量（TFLOP）", "Compute per accepted token (TFLOP)"),
            "stage_composition": tr("完整运行阶段", "Complete runtime stages"),
            "step_profile": tr("Denoise 逐步明细", "Denoise step details"),
        }
        available_runs = sorted({record["run"] for record in profiling_details})
        with st.expander("选择模型、变体、数据集和指标", expanded=True):
            selected_profile_runs = select_model_variants(
                profiling_details,
                default_runs=available_runs,
                key_prefix="profiling",
            )
            available_profile_datasets = sorted(
                {
                    record["dataset"]
                    for record in profiling_details
                    if record["run"] in selected_profile_runs
                }
            )
            selected_profile_datasets = st.multiselect(
                "数值对比数据集",
                available_profile_datasets,
                default=["gsm8k"] if "gsm8k" in available_profile_datasets else available_profile_datasets[:1],
                key="profiling_datasets",
            )
            selected_analyses = st.multiselect(
                "Compute 指标",
                list(analysis_labels),
                default=["stage_composition", "step_profile"],
                format_func=analysis_labels.get,
                key="profiling_analyses",
            )
        status_rows = []
        for run in selected_profile_runs:
            for dataset in selected_profile_datasets:
                matching = [
                    record
                    for record in profiling_details
                    if record["run"] == run and record["dataset"] == dataset
                ]
                status_rows.append(
                    {
                        "Run": run,
                        "Dataset": dataset,
                        "Status": (
                            "success"
                            if any(record.get("status") == "success" for record in matching)
                            else "oom"
                            if any(record.get("status") == "oom" for record in matching)
                            else "pending"
                        ),
                        "Failure stage": next(
                            (
                                record.get("failure_stage")
                                for record in matching
                                if record.get("status") == "oom"
                            ),
                            None,
                        ),
                        "Error": next(
                            (
                                record.get("error_message")
                                for record in matching
                                if record.get("status") == "oom"
                            ),
                            None,
                        ),
                    }
                )
        if status_rows:
            with st.expander("Profiling 运行状态", expanded=False):
                st.caption("Profiling matrix binding and result availability")
                st.dataframe(
                    pd.DataFrame(status_rows),
                    width="stretch",
                    hide_index=True,
                )
        filtered_profiles = [
            record
            for record in profiling_details
            if record["run"] in selected_profile_runs
            and record["dataset"] in selected_profile_datasets
        ]
        if any(str(record.get("model", "")).startswith("dream") for record in filtered_profiles):
            st.caption(
                tr(
                    "Dream 先完成一次 prefill，随后使用 KV cache 生成。后续 forward 只处理当前活动块，"
                    "所以每步计算量明显低于反复计算完整 canvas 的模型；总成本需要结合总计算量和阶段拆分查看。",
                    "Dream performs one prefill and then generates with a KV cache. Later forwards only process "
                    "the active block, so per-step compute is much lower than models that repeatedly process the "
                    "full canvas; compare total compute and the stage breakdown for end-to-end cost.",
                )
            )

        scalar_metrics = [
            metric
            for metric in selected_analyses
            if metric not in {"stage_composition", "step_profile"}
        ]
        for metric in scalar_metrics:
            metric_rows = [
                {
                    "模型": record["run"],
                    "数据集": record["dataset"],
                    "数值": record["metrics"].get(metric),
                }
                for record in filtered_profiles
                if record["metrics"].get(metric) is not None
            ]
            if not metric_rows:
                st.warning(f"所选结果没有{analysis_labels[metric]}记录。")
                continue
            metric_frame = pd.DataFrame(metric_rows)
            metric_figure = px.bar(
                metric_frame,
                x="数据集",
                y="数值",
                color="模型",
                barmode="group",
                title=analysis_labels[metric],
            )
            def render_metric_values(frame=metric_frame) -> None:
                st.dataframe(
                    frame.pivot_table(
                        index="模型",
                        columns="数据集",
                        values="数值",
                        aggfunc="first",
                    ).reset_index(),
                    width="stretch",
                    hide_index=True,
                )

            render_chart_panel(
                paths,
                title=analysis_labels[metric],
                section="profiling",
                collapsible=True,
                key=f"scalar_{metric}",
                spec=plotly_spec(metric_figure),
                preview=lambda figure=metric_figure, metric=metric: render_plotly(
                    figure, key=f"profiling_{metric}"
                ),
                footer=render_metric_values,
            )

        curve_analyses = [
            metric
            for metric in selected_analyses
            if metric in {"stage_composition", "step_profile"}
        ]
        selected_curve_datasets = selected_profile_datasets if curve_analyses else []
        curve_profiles = [
            record
            for record in profiling_details
            if record["run"] in selected_profile_runs
            and record["dataset"] in selected_curve_datasets
        ]

        def display_stage(stage_name: str) -> str:
            labels = {
                "input_preparation": tr("输入准备", "Input preparation"),
                "canvas_initialization": tr("画布初始化", "Canvas initialization"),
                "prefill": "Prefill",
                "denoise_step": "Denoise forward",
                "decode_cached": "Cached decode",
                "denoise": "Denoise",
                "token_selection": tr("Token 选择", "Token selection"),
                "canvas_update": tr("画布更新", "Canvas update"),
                "cache_finalization": tr("Cache 收尾", "Cache finalization"),
                "finalization": "Finalization",
                "output_decode": tr("输出解码", "Output decode"),
            }
            return labels.get(stage_name, stage_name)

        def major_stage(stage_name: str) -> str:
            if stage_name in {"input_preparation", "canvas_initialization"}:
                return "preparation"
            if stage_name == "prefill":
                return "prefill"
            if stage_name in {
                "denoise_step",
                "decode_cached",
                "denoise",
                "token_selection",
                "canvas_update",
            }:
                return "generation"
            if stage_name in {"cache_finalization", "finalization"}:
                return "finalization"
            if stage_name == "output_decode":
                return "output"
            return "other"

        major_labels = {
            "preparation": tr("准备", "Preparation"),
            "prefill": "Prefill",
            "generation": tr("Denoise / Cached decode", "Denoise / cached decode"),
            "finalization": "Finalization",
            "output": tr("输出", "Output"),
            "other": tr("其他", "Other"),
        }
        major_colors = {
            "preparation": "#9aa6a4",
            "prefill": "#e07a1f",
            "generation": "#187f78",
            "finalization": "#7057b7",
            "output": "#3569c8",
            "other": "#b1a58f",
        }

        if "stage_composition" in selected_analyses:
            st.markdown("#### 完整运行阶段")
            st.caption(
                tr(
                    "从 profiling 开始记录起，按实际顺序展示输入准备、初始化、prefill、denoise、收尾和输出等全部 stage。",
                    "Shows every recorded stage in order from the beginning of profiling, including input preparation, "
                    "initialization, prefill, denoise, finalization, and output.",
                )
            )
            stage_palette = (
                px.colors.qualitative.Set2
                + px.colors.qualitative.Safe
                + px.colors.qualitative.Pastel
            )
            for curve_dataset in selected_curve_datasets:
                dataset_profiles = [
                    record
                    for record in curve_profiles
                    if record["dataset"] == curve_dataset and record["stages"]
                ]
                if not dataset_profiles:
                    continue
                run_labels = [record["run"] for record in dataset_profiles]
                aggregates = {}
                ordered_stages = []
                for record in dataset_profiles:
                    run_values = {}
                    for stage in record["stages"]:
                        raw_stage_name = str(stage.get("stage") or "unknown")
                        stage_name = major_stage(raw_stage_name)
                        if stage_name not in ordered_stages:
                            ordered_stages.append(stage_name)
                        values = run_values.setdefault(
                            stage_name,
                            {"wall_clock_seconds": 0.0, "compute_tflops": 0.0},
                        )
                        for metric_name in ("wall_clock_seconds", "compute_tflops"):
                            value = stage.get(metric_name)
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                values[metric_name] += float(value)
                    aggregates[record["run"]] = run_values

                stage_figure = make_subplots(
                    rows=3,
                    cols=2,
                    specs=[
                        [{"colspan": 2}, None],
                        [{}, {}],
                        [{}, {}],
                    ],
                    subplot_titles=(
                        tr("完整运行阶段", "Complete runtime stages"),
                        tr("阶段耗时（秒）", "Stage time (seconds)"),
                        tr("阶段计算量（TFLOP）", "Stage compute (TFLOP)"),
                        tr("耗时占比", "Time share"),
                        tr("计算量占比", "Compute share"),
                    ),
                    horizontal_spacing=0.1,
                    vertical_spacing=0.14,
                    row_heights=[0.22, 0.39, 0.39],
                )
                semantic_stage_order = [
                    stage_name
                    for stage_name in (
                        "preparation",
                        "prefill",
                        "generation",
                        "finalization",
                        "output",
                        "other",
                    )
                    if stage_name in ordered_stages
                ]
                for group_index, group in enumerate(semantic_stage_order):
                    durations = [
                        aggregates[run]
                        .get(group, {})
                        .get("wall_clock_seconds", 0.0)
                        for run in run_labels
                    ]
                    compute_values = [
                        aggregates[run]
                        .get(group, {})
                        .get("compute_tflops", 0.0)
                        for run in run_labels
                    ]
                    stage_figure.add_trace(
                        go.Bar(
                            x=durations,
                            y=run_labels,
                            customdata=compute_values,
                            name=major_labels[group],
                            marker=dict(
                                color=major_colors[group],
                                line=dict(color="rgba(255,255,255,0.95)", width=2),
                            ),
                            orientation="h",
                            text=[major_labels[group] if value > 0 else "" for value in durations],
                            textposition="inside",
                            insidetextanchor="middle",
                            legendgroup=f"semantic-stage-{group}",
                            legendgrouptitle_text=(
                                "Stage"
                                if group_index == 0
                                else None
                            ),
                            hovertemplate=(
                                "%{y}<br>%{fullData.name}<br>time=%{x:.6f}s"
                                "<br>compute=%{customdata:.4f} TFLOP<extra></extra>"
                            ),
                        ),
                        row=1,
                        col=1,
                    )
                for column, metric_name in enumerate(
                    ("wall_clock_seconds", "compute_tflops"), start=1
                ):
                    totals = {
                        run: sum(
                            values.get(metric_name, 0.0)
                            for values in aggregates[run].values()
                        )
                        for run in run_labels
                    }
                    for color_index, stage_name in enumerate(ordered_stages):
                        absolute_values = [
                            aggregates[run]
                            .get(stage_name, {})
                            .get(metric_name, 0.0)
                            for run in run_labels
                        ]
                        shares = [
                            value / totals[run] if totals[run] > 0 else 0.0
                            for run, value in zip(run_labels, absolute_values)
                        ]
                        color = major_colors.get(
                            stage_name,
                            stage_palette[color_index % len(stage_palette)],
                        )
                        stage_figure.add_trace(
                            go.Bar(
                                x=absolute_values,
                                y=run_labels,
                                name=major_labels.get(stage_name, stage_name),
                                orientation="h",
                                marker_color=color,
                                customdata=shares,
                                legendgroup=stage_name,
                                showlegend=False,
                                hovertemplate=(
                                    "%{y}<br>%{fullData.name}<br>value=%{x:.4f}"
                                    "<br>share=%{customdata:.1%}<extra></extra>"
                                ),
                            ),
                            row=2,
                            col=column,
                        )
                        stage_figure.add_trace(
                            go.Bar(
                                x=shares,
                                y=run_labels,
                                name=major_labels.get(stage_name, stage_name),
                                orientation="h",
                                marker_color=color,
                                customdata=absolute_values,
                                legendgroup=stage_name,
                                showlegend=False,
                                hovertemplate=(
                                    "%{y}<br>%{fullData.name}<br>share=%{x:.1%}"
                                    "<br>value=%{customdata:.4f}<extra></extra>"
                                ),
                            ),
                            row=3,
                            col=column,
                        )
                    stage_figure.add_trace(
                        go.Scatter(
                            x=[totals[run] for run in run_labels],
                            y=run_labels,
                            mode="text",
                            text=[
                                f"{totals[run]:.3f}"
                                for run in run_labels
                            ],
                            textposition="middle right",
                            showlegend=False,
                            hoverinfo="skip",
                        ),
                        row=2,
                        col=column,
                    )
                stage_summary_rows = []
                for run in run_labels:
                    run_stages = aggregates[run]
                    stage_summary_rows.append(
                        {
                            tr("模型", "Model"): run,
                            tr("总耗时（秒）", "Total time (s)"): sum(
                                values.get("wall_clock_seconds", 0.0)
                                for values in run_stages.values()
                            ),
                            tr("总计算量（TFLOP）", "Total compute (TFLOP)"): sum(
                                values.get("compute_tflops", 0.0)
                                for values in run_stages.values()
                            ),
                            "Prefill (TFLOP)": sum(
                                values.get("compute_tflops", 0.0)
                                for stage_name, values in run_stages.items()
                                if stage_name == "prefill"
                            ),
                            "Denoise / cached decode (TFLOP)": sum(
                                values.get("compute_tflops", 0.0)
                                for stage_name, values in run_stages.items()
                                if stage_name == "generation"
                            ),
                            "Finalization (TFLOP)": sum(
                                values.get("compute_tflops", 0.0)
                                for stage_name, values in run_stages.items()
                                if stage_name == "finalization"
                            ),
                        }
                    )
                stage_summary_frame = pd.DataFrame(stage_summary_rows)
                stage_figure.update_layout(
                    barmode="stack",
                    title=f"{curve_dataset} · {tr('完整运行阶段', 'Complete runtime stages')}",
                    height=max(820, 120 * len(run_labels) + 540),
                    legend=dict(orientation="h", y=-0.16, x=0.5, xanchor="center"),
                )
                stage_figure.update_xaxes(
                    title_text=tr("累计阶段耗时（秒）", "Cumulative stage time (s)"),
                    row=1,
                    col=1,
                )
                stage_figure.update_yaxes(
                    title_text=tr("模型", "Model"),
                    autorange="reversed",
                    row=1,
                    col=1,
                )
                stage_figure.update_xaxes(title_text="seconds", row=2, col=1)
                stage_figure.update_xaxes(title_text="TFLOP", row=2, col=2)
                stage_figure.update_xaxes(range=[0, 1], tickformat=".0%", row=3, col=1)
                stage_figure.update_xaxes(range=[0, 1], tickformat=".0%", row=3, col=2)
                for row in (2, 3):
                    for column in (1, 2):
                        stage_figure.update_yaxes(autorange="reversed", row=row, col=column)
                render_chart_panel(
                    paths,
                    title=f"{curve_dataset} · Complete runtime stages",
                    section="profiling",
                    collapsible=True,
                    key=f"stage_{curve_dataset}",
                    spec=plotly_spec(stage_figure),
                    preview=lambda figure=stage_figure, dataset=curve_dataset: render_plotly(
                        figure,
                        key=f"profiling_stage_composition_{dataset}",
                        legend_title="Recorded stage",
                    ),
                    footer=lambda frame=stage_summary_frame: st.dataframe(
                        frame,
                        width="stretch",
                        hide_index=True,
                    ),
                )

        if "step_profile" in selected_analyses:
            st.markdown("#### Denoise 逐步明细")
            st.caption(
                tr(
                    "这里只展开 denoise 或 cached decode 阶段的每次 forward；prefill、收尾和输出请在上方 Stage 图中查看。",
                    "Only forwards inside denoise or cached decode are expanded here. Prefill, finalization, and "
                    "output are shown in the stage chart above.",
                )
            )
            palette = px.colors.qualitative.Dark2
            for curve_dataset in selected_curve_datasets:
                dataset_profiles = [
                    record
                    for record in curve_profiles
                    if record["dataset"] == curve_dataset and record["steps"]
                ]
                if not dataset_profiles:
                    continue
                step_summary_rows = []
                for record in dataset_profiles:
                    generation_steps = [
                        step
                        for step in record["steps"]
                        if major_stage(str(step.get("phase") or "unknown")) == "generation"
                    ]
                    if not generation_steps:
                        generation_steps = record["steps"]
                    phases = []
                    for step in generation_steps:
                        phase = str(step.get("phase") or "unknown")
                        if phase not in phases:
                            phases.append(phase)
                    step_compute = sum(
                        float(step.get("compute_tflops", 0.0) or 0.0)
                        for step in generation_steps
                    )
                    step_summary_rows.append(
                        {
                            tr("模型", "Model"): record["run"],
                            tr("阶段", "Phase"): " / ".join(phases),
                            tr("Denoise forward 数", "Denoise forwards"): len(generation_steps),
                            tr("该阶段计算量（TFLOP）", "Phase compute (TFLOP)"): step_compute,
                            tr("平均每步（TFLOP）", "Average per step (TFLOP)"): (
                                step_compute / len(generation_steps)
                                if generation_steps
                                else 0.0
                            ),
                        }
                    )
                step_summary_frame = pd.DataFrame(step_summary_rows)
                step_figure = make_subplots(
                    rows=2,
                    cols=2,
                    subplot_titles=(
                        tr("累计接受吞吐", "Cumulative accepted throughput"),
                        tr("每步计算量", "Compute per step"),
                        tr("输入与有效上下文", "Input and active context"),
                        tr("KV cache 长度", "KV cache length"),
                    ),
                    vertical_spacing=0.14,
                    horizontal_spacing=0.1,
                )
                for model_index, record in enumerate(dataset_profiles):
                    color = palette[model_index % len(palette)]
                    all_profile_steps = record["steps"]
                    profile_steps = [
                        step
                        for step in all_profile_steps
                        if major_stage(str(step.get("phase") or "unknown")) == "generation"
                    ]
                    if not profile_steps and all_profile_steps:
                        profile_steps = all_profile_steps
                    forward_indices = [
                        int(step.get("step_index", fallback_index) or fallback_index)
                        for fallback_index, step in enumerate(profile_steps)
                    ]
                    x_values = list(range(1, len(profile_steps) + 1))
                    phase_names = [
                        display_stage(str(step.get("phase") or "unknown"))
                        for step in profile_steps
                    ]
                    cumulative_accepted = 0.0
                    cumulative_elapsed = 0.0
                    cumulative_accepted_tps = []
                    accepted_per_step = []
                    for step in profile_steps:
                        elapsed = step.get("wall_clock_seconds")
                        accepted = step.get("accepted_tokens")
                        accepted_value = (
                            float(accepted)
                            if isinstance(accepted, (int, float))
                            and not isinstance(accepted, bool)
                            else 0.0
                        )
                        elapsed_value = (
                            float(elapsed)
                            if isinstance(elapsed, (int, float))
                            and not isinstance(elapsed, bool)
                            and elapsed > 0
                            else 0.0
                        )
                        cumulative_accepted += accepted_value
                        cumulative_elapsed += elapsed_value
                        accepted_per_step.append(accepted_value)
                        cumulative_accepted_tps.append(
                            cumulative_accepted / cumulative_elapsed
                            if cumulative_elapsed > 0
                            else 0.0
                        )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=cumulative_accepted_tps,
                            customdata=list(zip(accepted_per_step, phase_names, forward_indices)),
                            mode="lines+markers",
                            name=record["run"],
                            line=dict(color=color),
                            marker=dict(size=4),
                            legendgroup=record["run"],
                            hovertemplate=(
                                "step %{x}<br>stage=%{customdata[1]}"
                                "<br>forward index=%{customdata[2]}"
                                "<br>cumulative accepted TPS: %{y:.2f}"
                                "<br>accepted at this step: %{customdata[0]:.0f}"
                                "<extra>%{fullData.name}</extra>"
                            ),
                        ),
                        row=1,
                        col=1,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("compute_tflops") for step in profile_steps],
                            customdata=list(zip(phase_names, forward_indices)),
                            mode="lines+markers",
                            line=dict(color=color),
                            marker=dict(size=4),
                            legendgroup=record["run"],
                            showlegend=False,
                            hovertemplate=(
                                "step %{x}<br>stage=%{customdata[0]}"
                                "<br>forward index=%{customdata[1]}"
                                "<br>compute=%{y:.4f} TFLOP<extra>%{fullData.name}</extra>"
                            ),
                        ),
                        row=1,
                        col=2,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("attention_tokens") for step in profile_steps],
                            mode="lines",
                            line=dict(color=color),
                            legendgroup=record["run"],
                            showlegend=False,
                        ),
                        row=2,
                        col=1,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("input_tokens") for step in profile_steps],
                            mode="lines",
                            line=dict(color=color, dash="dash"),
                            legendgroup=record["run"],
                            showlegend=False,
                        ),
                        row=2,
                        col=1,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("kv_cache_tokens") for step in profile_steps],
                            mode="lines",
                            line=dict(color=color),
                            legendgroup=record["run"],
                            showlegend=False,
                        ),
                        row=2,
                        col=2,
                    )
                step_figure.update_layout(
                    title=f"{curve_dataset} · {tr('Denoise 逐步明细', 'Denoise step details')}",
                    height=760,
                    legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
                )
                step_figure.update_yaxes(
                    title_text="cumulative accepted token/s", row=1, col=1
                )
                step_figure.update_yaxes(title_text="TFLOP", row=1, col=2)
                step_figure.update_xaxes(title_text=tr("Denoise step", "Denoise step"), row=2, col=1)
                step_figure.update_xaxes(title_text=tr("Denoise step", "Denoise step"), row=2, col=2)
                step_figure.update_yaxes(title_text="tokens", row=2, col=1)
                step_figure.update_yaxes(title_text="tokens", row=2, col=2)
                render_chart_panel(
                    paths,
                    title=f"{curve_dataset} · Denoise step profile",
                    section="profiling",
                    collapsible=True,
                    key=f"step_{curve_dataset}",
                    spec=plotly_spec(step_figure),
                    preview=lambda figure=step_figure, dataset=curve_dataset: render_plotly(
                        figure,
                        key=f"profiling_step_profile_{dataset}",
                    ),
                    footer=lambda frame=step_summary_frame: (
                        st.dataframe(frame, width="stretch", hide_index=True),
                        st.caption(
                            tr(
                                "曲线只展示 denoise / cached decode 内的 forward。上下文图中实线为有效 attention，"
                                "虚线为本步输入长度。",
                                "Curves only show forwards inside denoise / cached decode. In the context panel, the solid "
                                "line is active attention and the dashed line is current input length.",
                            )
                        ),
                    ),
                )
