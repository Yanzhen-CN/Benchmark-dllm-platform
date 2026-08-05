from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from platform_core.compare import render_comparison
from platform_core.profiling import load_profiling_detail_records
from platform_core.results import (
    available_metrics,
    DEFAULT_COMPARISON_RUNS,
    datasets,
    load_summary_records,
    metric_label,
)
from platform_core.selection import (
    select_dataset_subsets,
    select_model_variants,
    select_single_dataset,
)
from platform_core.ui import configure_page, paths_sidebar, require_ready


configure_page("性能对比 | Benchmark-dllm")
paths = paths_sidebar()
require_ready(paths)

st.title("Performance")


def render_plotly(figure, *, key: str, legend_title: str = "模型") -> None:
    figure.update_layout(
        dragmode=False,
        margin=dict(l=35, r=20, t=58, b=45),
        legend_title_text=legend_title,
    )
    st.plotly_chart(
        figure,
        width="stretch",
        key=key,
        config={
            "scrollZoom": False,
            "displaylogo": False,
            "displayModeBar": True,
            "modeBarButtonsToRemove": [
                "zoom2d",
                "pan2d",
                "select2d",
                "lasso2d",
                "zoomIn2d",
                "zoomOut2d",
                "autoScale2d",
                "resetScale2d",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": key,
                "scale": 2,
            },
        },
    )


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

raw_tab, adjusted_tab, profiling_tab = st.tabs(
    ["原始性能", "可选资源折算", "Profiling"]
)


with raw_tab:
    with st.expander("选择数据集、模型和指标", expanded=True):
        dataset_name = select_single_dataset(
            datasets(records),
            key_prefix="performance",
        )
        dataset_records = [
            record for record in records if record["dataset"] == dataset_name
        ]
        selected_runs = select_model_variants(
            dataset_records,
            default_runs=DEFAULT_COMPARISON_RUNS,
            key_prefix="performance",
        )
        selected_records = [
            record for record in dataset_records if record["run"] in selected_runs
        ]
        default_metrics = [
            "accepted_tps",
            "eps",
            "peak_vram_gb",
            "time_per_sample",
            "accepted_tokens_per_sample",
            "energy_per_sample",
        ]
        available = available_metrics(selected_records, "performance_metrics")
        metric_options = default_metrics + [
            name for name in available if name not in default_metrics
        ]
        selected_metrics = st.multiselect(
            "性能指标",
            metric_options,
            default=default_metrics,
            format_func=metric_label,
        )

    rows = []
    for record in selected_records:
        for metric in selected_metrics:
            rows.append(
                {
                    "模型": record["run"],
                    "metric": metric_label(metric),
                    "value": record["performance_metrics"].get(metric),
                }
            )

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
                render_comparison(metric_rows, row_key="模型")
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
        st.markdown("#### 原始数值")
        st.dataframe(raw_frame, width="stretch", hide_index=True)
        if any(row["value"] is None for row in rows):
            st.caption("空白表示当前结果没有记录该指标。")


with adjusted_tab:
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
                render_plotly(raw_figure, key="adjusted_raw_score")

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
            with chart_columns[1]:
                render_plotly(adjusted_figure, key="adjusted_score")

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


with profiling_tab:
    st.subheader("Profiling")
    profiling_details = load_profiling_detail_records(paths.output_root)
    if not profiling_details:
        st.info("model_profiling 中没有可用的单样本记录。")
    else:
        analysis_labels = {
            "compute_per_second": "计算速度（TFLOP/s）",
            "compute_tflops": "单样本计算量（TFLOP）",
            "compute_per_accepted_token": "每接受 token 计算量（TFLOP）",
            "stage_composition": "阶段构成",
            "step_profile": "逐步计算与上下文",
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
                default=list(analysis_labels),
                format_func=analysis_labels.get,
                key="profiling_analyses",
            )
        filtered_profiles = [
            record
            for record in profiling_details
            if record["run"] in selected_profile_runs
            and record["dataset"] in selected_profile_datasets
        ]

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
            render_plotly(metric_figure, key=f"profiling_{metric}")
            st.dataframe(
                metric_frame.pivot_table(
                    index="模型",
                    columns="数据集",
                    values="数值",
                    aggfunc="first",
                ).reset_index(),
                width="stretch",
                hide_index=True,
            )

        curve_analyses = [
            metric
            for metric in selected_analyses
            if metric in {"stage_composition", "step_profile"}
        ]
        selected_curve_datasets = []
        if curve_analyses:
            selected_curve_datasets = st.multiselect(
                "曲线数据集",
                available_profile_datasets,
                default=["gsm8k"] if "gsm8k" in available_profile_datasets else available_profile_datasets[:1],
                key="profiling_curve_datasets",
            )
        curve_profiles = [
            record
            for record in profiling_details
            if record["run"] in selected_profile_runs
            and record["dataset"] in selected_curve_datasets
        ]

        if "stage_composition" in selected_analyses:
            stage_order = [
                "input_preparation",
                "canvas_initialization",
                "prefill",
                "denoise_step",
                "token_selection",
                "canvas_update",
                "cache_finalization",
                "output_decode",
            ]
            stage_labels = {
                "input_preparation": "输入准备",
                "canvas_initialization": "画布初始化",
                "prefill": "Prefill",
                "denoise_step": "Denoise / Decode",
                "token_selection": "Token 选择",
                "canvas_update": "画布更新",
                "cache_finalization": "Cache 收尾",
                "output_decode": "输出解码",
            }
            stage_colors = {
                stage: px.colors.qualitative.Set2[index % len(px.colors.qualitative.Set2)]
                for index, stage in enumerate(stage_order)
            }
            st.markdown("#### 阶段构成")
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
                observed = set()
                for record in dataset_profiles:
                    run_values = {}
                    for stage in record["stages"]:
                        stage_name = str(stage.get("stage", "unknown"))
                        observed.add(stage_name)
                        values = run_values.setdefault(
                            stage_name,
                            {"wall_clock_seconds": 0.0, "compute_tflops": 0.0},
                        )
                        for metric_name in ("wall_clock_seconds", "compute_tflops"):
                            value = stage.get(metric_name)
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                values[metric_name] += float(value)
                    aggregates[record["run"]] = run_values

                ordered_stages = [stage for stage in stage_order if stage in observed]
                ordered_stages += sorted(observed.difference(stage_order))
                stage_figure = make_subplots(
                    rows=1,
                    cols=2,
                    subplot_titles=("记录时间占比", "记录计算量占比"),
                    horizontal_spacing=0.08,
                )
                for column, metric_name in enumerate(("wall_clock_seconds", "compute_tflops"), start=1):
                    totals = {
                        run: sum(values.get(metric_name, 0.0) for values in aggregates[run].values())
                        for run in run_labels
                    }
                    for color_index, stage_name in enumerate(ordered_stages):
                        shares = [
                            aggregates[run].get(stage_name, {}).get(metric_name, 0.0) / totals[run]
                            if totals[run] > 0
                            else 0.0
                            for run in run_labels
                        ]
                        stage_figure.add_trace(
                            go.Bar(
                                x=shares,
                                y=run_labels,
                                name=stage_labels.get(stage_name, stage_name),
                                orientation="h",
                                marker_color=stage_colors.get(
                                    stage_name,
                                    px.colors.qualitative.Set2[color_index % len(px.colors.qualitative.Set2)],
                                ),
                                legendgroup=stage_name,
                                showlegend=column == 1,
                                hovertemplate=(
                                    "%{y}<br>"
                                    + stage_labels.get(stage_name, stage_name)
                                    + ": %{x:.1%}<extra></extra>"
                                ),
                            ),
                            row=1,
                            col=column,
                        )
                stage_figure.update_layout(
                    barmode="stack",
                    title=f"{curve_dataset} · 生成阶段构成",
                    height=max(430, 70 * len(run_labels) + 240),
                    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                )
                stage_figure.update_xaxes(range=[0, 1], tickformat=".0%")
                stage_figure.update_yaxes(autorange="reversed")
                render_plotly(
                    stage_figure,
                    key=f"profiling_stage_composition_{curve_dataset}",
                    legend_title="阶段",
                )

        if "step_profile" in selected_analyses:
            st.markdown("#### 逐步计算与上下文")
            palette = px.colors.qualitative.Dark2
            for curve_dataset in selected_curve_datasets:
                dataset_profiles = [
                    record
                    for record in curve_profiles
                    if record["dataset"] == curve_dataset and record["steps"]
                ]
                if not dataset_profiles:
                    continue
                step_figure = make_subplots(
                    rows=2,
                    cols=2,
                    subplot_titles=(
                        "每步接受吞吐",
                        "每步计算量",
                        "输入与有效上下文",
                        "KV cache 长度",
                    ),
                    vertical_spacing=0.14,
                    horizontal_spacing=0.1,
                )
                for model_index, record in enumerate(dataset_profiles):
                    color = palette[model_index % len(palette)]
                    generation_steps = [
                        step
                        for step in record["steps"]
                        if str(step.get("phase", "")) not in {"prefill", "finalization"}
                    ]
                    if not generation_steps:
                        generation_steps = record["steps"]
                    x_values = [
                        int(step.get("step_index", index))
                        for index, step in enumerate(generation_steps)
                    ]
                    accepted_tps = []
                    for step in generation_steps:
                        elapsed = step.get("wall_clock_seconds")
                        accepted = step.get("accepted_tokens")
                        accepted_tps.append(
                            float(accepted) / float(elapsed)
                            if isinstance(accepted, (int, float))
                            and isinstance(elapsed, (int, float))
                            and elapsed > 0
                            else 0.0
                        )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=accepted_tps,
                            mode="lines+markers",
                            name=record["run"],
                            line=dict(color=color),
                            marker=dict(size=4),
                            legendgroup=record["run"],
                        ),
                        row=1,
                        col=1,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("compute_tflops") for step in generation_steps],
                            mode="lines",
                            line=dict(color=color),
                            legendgroup=record["run"],
                            showlegend=False,
                        ),
                        row=1,
                        col=2,
                    )
                    step_figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=[step.get("attention_tokens") for step in generation_steps],
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
                            y=[step.get("input_tokens") for step in generation_steps],
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
                            y=[step.get("kv_cache_tokens") for step in generation_steps],
                            mode="lines",
                            line=dict(color=color),
                            legendgroup=record["run"],
                            showlegend=False,
                        ),
                        row=2,
                        col=2,
                    )
                step_figure.update_layout(
                    title=f"{curve_dataset} · 逐步计算与上下文",
                    height=760,
                    legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                )
                step_figure.update_xaxes(title_text="真实 step", row=2, col=1)
                step_figure.update_xaxes(title_text="真实 step", row=2, col=2)
                step_figure.update_yaxes(title_text="accepted token/s", row=1, col=1)
                step_figure.update_yaxes(title_text="TFLOP", row=1, col=2)
                step_figure.update_yaxes(title_text="tokens", row=2, col=1)
                step_figure.update_yaxes(title_text="tokens", row=2, col=2)
                render_plotly(
                    step_figure,
                    key=f"profiling_step_profile_{curve_dataset}",
                )
                st.caption("上下文面板中实线为有效 attention，虚线为本步输入长度。")
