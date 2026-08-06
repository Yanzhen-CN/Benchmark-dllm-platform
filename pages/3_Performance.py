from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from platform_core.adjustment import adjustment_rows, average_power
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


ADJUSTMENT_PAIRS = (
    {
        "title": "DiffusionGemma vs Gemma AR",
        "base_run": "gemma_ar-baseline",
        "base_label": "Gemma AR（基线）",
        "target_run": "diffusiongemma_official",
        "target_label": "DiffusionGemma（折算对象）",
        "key": "dg_gemma",
    },
    {
        "title": "iLLaDA entropy-eb05 vs iLLaDA P2",
        "base_run": "illada_p2",
        "base_label": "iLLaDA P2（基线）",
        "target_run": "illada_entropy_eb05",
        "target_label": "iLLaDA entropy-eb05（折算对象）",
        "key": "illada_eb05_p2",
    },
)


def render_adjustment_pair(records, pair, *, beta: float, gamma: float) -> None:
    base_run = pair["base_run"]
    target_run = pair["target_run"]
    run_datasets = {
        run: {record["dataset"] for record in records if record["run"] == run}
        for run in (base_run, target_run)
    }
    common_datasets = sorted(run_datasets[base_run] & run_datasets[target_run])

    st.markdown(f"### {pair['title']}")
    st.caption(
        f"基线：{pair['base_label']}；折算对象：{pair['target_label']}。"
        "只在二者具有相同数据集、正式主分、时间和功率记录时计算。"
    )
    if not common_datasets:
        st.info("这组对比目前没有共同且完整的数据集结果。")
        return

    selected_datasets = select_dataset_subsets(
        common_datasets,
        default_datasets=(
            ["gsm8k"] if "gsm8k" in common_datasets else common_datasets[:1]
        ),
        key_prefix=f"adjusted_{pair['key']}",
    )
    if not selected_datasets:
        st.info("请选择至少一个数据集。")
        return

    rows, missing = adjustment_rows(
        records,
        base_run=base_run,
        target_run=target_run,
        selected_datasets=selected_datasets,
        beta=beta,
        gamma=gamma,
    )
    if missing:
        st.warning("缺少完整资源记录，未参与折算：" + "、".join(missing))
    if not rows:
        return

    raw_rows = []
    adjusted_rows = []
    for row in rows:
        raw_rows.extend(
            [
                {
                    "数据集": row["数据集"],
                    "模型": pair["base_label"],
                    "分数": row["基线原始分数"],
                },
                {
                    "数据集": row["数据集"],
                    "模型": pair["target_label"],
                    "分数": row["目标原始分数"],
                },
            ]
        )
        adjusted_rows.extend(
            [
                {
                    "数据集": row["数据集"],
                    "模型": pair["base_label"],
                    "分数": row["基线原始分数"],
                },
                {
                    "数据集": row["数据集"],
                    "模型": pair["target_label"],
                    "分数": row["目标折算指数"],
                },
            ]
        )

    chart_columns = st.columns(2)
    color_map = {
        pair["base_label"]: "#52796f",
        pair["target_label"]: "#e76f51",
    }
    raw_figure = px.bar(
        pd.DataFrame(raw_rows),
        x="数据集",
        y="分数",
        color="模型",
        barmode="group",
        title="原始分数（正式结果）",
        text_auto=".4g",
        color_discrete_map=color_map,
    )
    raw_figure.update_traces(textposition="outside", cliponaxis=False)
    raw_figure.update_layout(height=360, yaxis_title="分数")
    with chart_columns[0]:
        render_plotly(raw_figure, key=f"{pair['key']}_raw_score")

    adjusted_figure = px.bar(
        pd.DataFrame(adjusted_rows),
        x="数据集",
        y="分数",
        color="模型",
        barmode="group",
        title="资源折算敏感性指数（非正式分数）",
        text_auto=".4g",
        color_discrete_map=color_map,
    )
    adjusted_figure.update_traces(textposition="outside", cliponaxis=False)
    adjusted_figure.update_layout(height=360, yaxis_title="分数")
    with chart_columns[1]:
        render_plotly(adjusted_figure, key=f"{pair['key']}_adjusted_score")

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "“目标速度 / 基线速度”大于 1 表示折算对象更快；"
        "“基线功率 / 目标功率”大于 1 表示折算对象平均功率更低。"
        "折算指数不截断到 0–1，因此可能超过 1；它不能作为准确率解读。"
    )


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
    st.warning(
        "资源折算是敏感性分析，不是 benchmark 正式分数。正式结论应使用左侧原始分数。"
    )
    eligible_adjusted_records = [
        record
        for record in records
        if record["primary_score"] is not None
        and record["performance_metrics"].get("time_per_sample")
        and average_power(record) is not None
    ]
    parameter_left, parameter_right = st.columns(2)
    beta_percent = parameter_left.slider(
        "beta · 资源影响",
        0,
        100,
        50,
        1,
        format="%d%%",
        help="控制资源差异对诊断性折算结果的整体影响。",
    )
    gamma_percent = parameter_right.slider(
        "gamma · 功率权重",
        0,
        100,
        50,
        1,
        format="%d%%",
        help="越高越看重平均功率，越低越看重单样本速度。",
    )
    pair_tabs = st.tabs([pair["title"] for pair in ADJUSTMENT_PAIRS])
    for pair_tab, pair in zip(pair_tabs, ADJUSTMENT_PAIRS):
        with pair_tab:
            render_adjustment_pair(
                eligible_adjusted_records,
                pair,
                beta=beta_percent / 100.0,
                gamma=gamma_percent / 100.0,
            )

    with st.expander("折算公式与方向"):
        st.code(
            "q_adjusted = q_target + beta * "
            "[(1-gamma) * (1 - t_target/t_base) + "
            "gamma * (1 - power_target/power_base)]"
        )
        st.caption(
            "每个数据集独立计算，不跨数据集求平均；beta、gamma 在公式中使用 0–1。"
        )


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
