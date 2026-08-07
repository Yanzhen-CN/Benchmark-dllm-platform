from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from .i18n import language


PERFORMANCE_METRICS = (
    "accepted_tps",
    "eps",
    "peak_vram_gb",
    "time_per_sample",
    "accepted_tokens_per_sample",
    "energy_per_sample",
)

DEFAULT_DATASETS = (
    "gsm8k",
    "hellobench_2k",
    "mbpp",
    "ruler",
    "structeval_t",
    "sudoku4_1shot",
    "sudoku9_1shot",
)

DEFAULT_COMPARISON_RUNS = (
    "illada_p1",
    "dreamreasoner_p1",
    "diffusiongemma_official",
    "gemma_ar-baseline",
)

SUDOKU_COMPARISON_RUNS = (
    "diffusiongemma_official",
    "llada2_1_qmode",
)


def default_comparison_runs(dataset_names: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Use the designated LLaDA2.1-vs-DG pair for every Sudoku dataset."""
    selected = tuple(dataset_names)
    sudoku = tuple(name for name in selected if name.startswith("sudoku"))
    if selected and len(sudoku) == len(selected):
        return SUDOKU_COMPARISON_RUNS
    if sudoku:
        return tuple(dict.fromkeys((*DEFAULT_COMPARISON_RUNS, *SUDOKU_COMPARISON_RUNS)))
    return DEFAULT_COMPARISON_RUNS

METRIC_LABELS = {
    "primary_score": "主分",
    "accepted_tps": "接受 TPS",
    "total_accepted_tokens": "Accepted tokens",
    "accepted_tokens_per_sample": "单样本接受 token",
    "sps": "样本/秒",
    "eps": "平均功率",
    "cps": "计算量/秒",
    "time_per_sample": "单样本时间",
    "energy_per_sample": "单样本能耗",
    "compute_per_sample": "单样本计算量",
    "peak_vram_gb": "峰值显存",
    "total_time_seconds": "总时间",
    "total_energy_joules": "总能耗",
    "total_output_tokens": "输出 Token 数",
    "score_per_energy": "单位能耗得分",
    "score_per_compute": "单位计算量得分",
    "valid_rate": "有效率",
    "complete_rate": "完成率",
    "accuracy": "准确率",
    "pass_at_1": "Pass@1",
    "official_score": "官方规则得分",
    "final_eval_score": "结构化最终分",
    "puzzle_success_rate": "数独成功率",
    "blank_cell_accuracy": "空格准确率",
    "cell_accuracy": "单元格准确率",
    "given_preservation_rate": "题面保留率",
    "complete_reference_sequence_accuracy": "完整答案准确率",
    "strict_reference_exact_match": "参考答案完全匹配",
    "answer_region_detected_rate": "答案区域识别率",
    "output_budget_utilization": "输出预算利用率",
}

METRIC_LABELS.update({
    "primary_score": "Primary score",
    "accuracy": "Accuracy",
    "pass_at_1": "Pass@1",
    "final_eval_score": "Final evaluation score",
    "long_output_integrity_score": "Long-output integrity",
    "ruler_string_match_all": "String match",
    "accepted_tps": "Accepted TPS",
    "eps": "Average power (W)",
    "peak_vram_gb": "Peak VRAM (GB)",
    "time_per_sample": "Seconds / sample",
    "accepted_tokens_per_sample": "Accepted tokens / sample",
    "energy_per_sample": "Energy / sample (J)",
    "answer_region_detected_rate": "Answer detected",
    "answer_position_token_mapped_rate": "Answer position mapped",
    "answer_start_ratio_mean": "Mean answer start position",
    "reasoning_tokens_before_answer": "Reasoning tokens before answer",
    "unclosed_thinking_rate": "Unclosed thinking",
    "answer_marker_complete_rate": "Complete answer marker",
    "executable_rate": "Executable code",
    "answer_local_structure_first_score": "Structure-first score",
    "official_render_score": "Render score",
    "official_key_validation_score": "Key validation score",
    "field_completion_rate": "Field completion",
    "format_valid_rate": "Valid format",
    "complete_correct_rate": "Complete and correct",
    "blank_cell_accuracy": "Blank-cell accuracy",
    "given_preservation_rate": "Fixed-clue preservation",
    "constraint_valid": "Constraint-valid solution",
    "puzzle_success_rate": "Puzzle success",
    "exact_solve_rate": "Exact solve",
    "strict_16_digit_format_rate": "Strict 16-digit format",
    "strict_81_digit_format_rate": "Strict 81-digit format",
    "direct_answer_instruction_following_rate": "Direct-answer compliance",
    "length_compliance_rate": "Length compliance",
    "seq_rep_4": "Seq-Rep-4",
    "repeated_segment_fraction": "Repeated segment fraction",
    "refusal_issue_rate": "Refusal rate",
    "corrupt_text_issue_rate": "Corrupt-text rate",
    "objective_structure_score": "Structure cues",
    "terminal_punctuation_rate": "Natural ending",
})

METRIC_LABELS_ZH = {
    "primary_score": "主分",
    "accuracy": "准确率",
    "pass_at_1": "一次通过率",
    "final_eval_score": "最终结构评分",
    "long_output_integrity_score": "长文本完整性",
    "ruler_string_match_all": "字符串命中率",
    "accepted_tps": "接受吞吐率",
    "eps": "平均功率",
    "peak_vram_gb": "峰值显存",
    "time_per_sample": "单样本耗时",
    "accepted_tokens_per_sample": "单样本接受 token 数",
    "energy_per_sample": "单样本能耗",
    "answer_region_detected_rate": "答案区域检出率",
    "answer_position_token_mapped_rate": "答案位置映射率",
    "answer_start_ratio_mean": "平均答案起始位置",
    "reasoning_tokens_before_answer": "答案前 reasoning token 数",
    "unclosed_thinking_rate": "thinking 未闭合率",
    "answer_marker_complete_rate": "答案标记完整率",
    "executable_rate": "代码可执行率",
    "answer_local_structure_first_score": "结构优先分",
    "official_render_score": "渲染分",
    "official_key_validation_score": "关键字段验证分",
    "field_completion_rate": "字段完成率",
    "format_valid_rate": "格式有效率",
    "complete_correct_rate": "完整且正确率",
    "blank_cell_accuracy": "空格正确率",
    "given_preservation_rate": "题面数字保留率",
    "constraint_valid": "约束合法率",
    "puzzle_success_rate": "整题成功率",
    "exact_solve_rate": "完整解题率",
    "strict_reference_exact_match": "严格参考答案匹配率",
    "strict_16_digit_format_rate": "严格 16 位格式率",
    "strict_81_digit_format_rate": "严格 81 位格式率",
    "direct_answer_instruction_following_rate": "直接作答遵循率",
    "answer_start_char_ratio": "正文起始位置",
    "reasoning_word_count": "正文前 reasoning 词数",
    "length_compliance_rate": "长度达标率",
    "seq_rep_4": "四元组重复率",
    "repeated_segment_fraction": "重复段落比例",
    "refusal_issue_rate": "拒答率",
    "corrupt_text_issue_rate": "损坏文本率",
    "objective_structure_score": "结构提示分",
    "terminal_punctuation_rate": "自然结束率",
    "all_answers_match": "全部答案命中率",
    "position_robustness_context_4160": "位置稳健性",
}

SCORE_METRIC_WHITELISTS = {
    "gsm8k": (
        "accuracy", "answer_region_detected_rate", "answer_position_token_mapped_rate",
        "answer_start_ratio_mean", "reasoning_tokens_before_answer", "unclosed_thinking_rate",
    ),
    "mbpp": (
        "pass_at_1", "answer_region_detected_rate", "executable_rate",
        "answer_marker_complete_rate", "answer_local_structure_first_score",
        "answer_start_ratio_mean", "unclosed_thinking_rate",
    ),
    "structeval_t": (
        "final_eval_score", "official_render_score", "official_key_validation_score",
        "field_completion_rate", "format_valid_rate", "complete_correct_rate",
        "answer_region_detected_rate", "answer_marker_complete_rate",
        "answer_local_structure_first_score", "answer_start_ratio_mean",
        "unclosed_thinking_rate",
    ),
    "ruler": (
        "ruler_string_match_all", "all_answers_match", "position_robustness_context_4160",
        "answer_region_detected_rate", "answer_start_ratio_mean",
    ),
    "hellobench": (
        "long_output_integrity_score", "length_compliance_rate", "seq_rep_4",
        "repeated_segment_fraction", "refusal_issue_rate", "corrupt_text_issue_rate",
        "answer_start_char_ratio", "reasoning_word_count", "objective_structure_score",
        "terminal_punctuation_rate",
    ),
    "sudoku4": (
        "blank_cell_accuracy", "given_preservation_rate", "constraint_valid",
        "puzzle_success_rate", "strict_16_digit_format_rate",
        "direct_answer_instruction_following_rate", "answer_region_detected_rate",
    ),
    "sudoku9": (
        "strict_reference_exact_match", "blank_cell_accuracy", "given_preservation_rate",
        "constraint_valid", "exact_solve_rate", "strict_81_digit_format_rate",
        "direct_answer_instruction_following_rate", "answer_region_detected_rate",
    ),
}


def score_metric_options(
    dataset_name: str, records: list[dict[str, Any]]
) -> list[str]:
    available = set(available_metrics(records, "score_metrics"))
    family = next(
        (name for name in SCORE_METRIC_WHITELISTS if dataset_name.startswith(name)),
        dataset_name,
    )
    return [
        metric for metric in SCORE_METRIC_WHITELISTS.get(family, ())
        if metric in available
    ]

def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def metric_label(name: str) -> str:
    labels = METRIC_LABELS_ZH if language() == "zh" else METRIC_LABELS
    label = labels.get(name)
    return f"{label} ({name})" if label and label != name else name


@st.cache_data(show_spinner=False, ttl=30)
def load_summary_records(output_root: Path) -> list[dict[str, Any]]:
    score_root = output_root / "score_output"
    records: list[dict[str, Any]] = []
    if not score_root.is_dir():
        return records

    for path in sorted(score_root.rglob("summary.json")):
        data = _read_json(path)
        if not data:
            continue

        aux = data.get("aux") if isinstance(data.get("aux"), dict) else {}
        scoring = (
            data.get("scoring_metadata")
            if isinstance(data.get("scoring_metadata"), dict)
            else {}
        )
        primary_score = data.get("q") if _is_number(data.get("q")) else None
        primary_metric = str(scoring.get("primary_metric") or "primary_score")

        score_metrics: dict[str, float] = {}
        if primary_score is not None:
            score_metrics["primary_score"] = float(primary_score)
            score_metrics.setdefault(primary_metric, float(primary_score))
        for name, value in aux.items():
            if _is_number(value):
                score_metrics[name] = float(value)

        performance_metrics = {
            name: float(data[name])
            for name in PERFORMANCE_METRICS
            if _is_number(data.get(name))
        }
        accepted_tokens = data.get("total_accepted_tokens")
        timed_samples = data.get("timed_sample_count")
        total_time = data.get("total_time_seconds")
        if _is_number(accepted_tokens) and _is_number(timed_samples) and timed_samples > 0:
            performance_metrics.setdefault(
                "accepted_tokens_per_sample",
                float(accepted_tokens) / float(timed_samples),
            )
        if _is_number(accepted_tokens) and _is_number(total_time) and total_time > 0:
            performance_metrics.setdefault(
                "accepted_tps",
                float(accepted_tokens) / float(total_time),
            )
        legacy_run_name = path.parents[1].name
        model_name = str(data.get("model_name") or legacy_run_name)
        if legacy_run_name == "gemma_dflash" or legacy_run_name.startswith("gemma_dflash_"):
            model_name = "gemma"
        config_name = str(data.get("config_name") or "default")
        run_name = (
            model_name
            if (model_name, config_name)
            in {
                ("gemma_dflash", "dflash"),
                ("qwen3_4b", "ar-baseline"),
                ("qwen3_8b", "ar-baseline"),
            }
            else f"{model_name}_{config_name}"
        )

        dataset_name = str(data.get("dataset_name") or path.parent.name)
        base_record = {
            "run": run_name,
            "model": model_name,
            "config": config_name,
            "dataset": dataset_name,
            "primary_metric": primary_metric,
            "primary_score": primary_score,
            "score_metrics": score_metrics,
            "performance_metrics": performance_metrics,
            "n_samples": data.get("n_samples"),
            "reportable": bool(scoring.get("reportable", True)),
            "path": path,
        }

        if dataset_name != "hellobench":
            records.append(base_record)
            continue

        for words, short_name in ((2000, "hellobench_2k"), (4000, "hellobench_4k")):
            suffix = f"_{words}_words"
            split_score = aux.get(f"long_output_integrity{suffix}")
            if not _is_number(split_score):
                split_score = aux.get(f"objective_quality{suffix}")
            if not _is_number(split_score):
                continue

            split_metrics: dict[str, float] = {
                "primary_score": float(split_score),
                primary_metric: float(split_score),
            }
            for name, value in aux.items():
                if name.endswith(suffix) and _is_number(value):
                    split_metrics[name[: -len(suffix)]] = float(value)

            split_performance: dict[str, float] = {}
            elapsed = aux.get(f"generation_time_mean_seconds{suffix}")
            output_tokens = aux.get(f"mean_generated_tokens{suffix}")
            if _is_number(elapsed) and float(elapsed) > 0:
                split_performance["time_per_sample"] = float(elapsed)
            sample_count = aux.get(f"sample_count{suffix}")
            records.append(
                {
                    **base_record,
                    "dataset": short_name,
                    "primary_score": float(split_score),
                    "score_metrics": split_metrics,
                    "performance_metrics": split_performance,
                    "n_samples": int(sample_count) if _is_number(sample_count) else None,
                }
            )
    return records


def datasets(records: list[dict[str, Any]]) -> list[str]:
    return sorted({record["dataset"] for record in records})


def runs(records: list[dict[str, Any]]) -> list[str]:
    return sorted({record["run"] for record in records})


def preferred_runs(records: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["model"]].append(record)

    preference = {
        "official": 0,
        "best": 1,
        "default": 2,
        "base": 3,
        "p1": 4,
        "fast": 5,
    }
    selected = []
    for model_records in grouped.values():
        unique = {record["run"]: record for record in model_records}.values()
        choice = min(
            unique,
            key=lambda record: (
                preference.get(record["config"].lower(), 20),
                len(record["run"]),
                record["run"],
            ),
        )
        selected.append(choice["run"])
    return sorted(selected)


def available_metrics(
    records: list[dict[str, Any]], bucket: str
) -> list[str]:
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(record.get(bucket, {}).keys())
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


@st.cache_data(show_spinner=False, ttl=30)
def load_sample_scores(
    output_root: Path, run_name: str, dataset_name: str
) -> list[dict[str, Any]]:
    hellobench_words = None
    if dataset_name in {"hellobench_2k", "hellobench_4k"}:
        hellobench_words = "2000" if dataset_name.endswith("_2k") else "4000"
        folder_dataset = "hellobench"
    else:
        folder_dataset = dataset_name
    folder = None
    score_root = output_root / "score_output"
    for summary_path in score_root.rglob("summary.json") if score_root.is_dir() else ():
        summary = _read_json(summary_path)
        if not summary:
            continue
        model = str(summary.get("model_name") or "")
        config = str(summary.get("config_name") or "default")
        candidate_run = (
            model
            if (model, config)
            in {
                ("gemma_dflash", "dflash"),
                ("qwen3_4b", "ar-baseline"),
                ("qwen3_8b", "ar-baseline"),
            }
            else f"{model}_{config}"
        )
        if candidate_run == run_name and summary_path.parent.name == folder_dataset:
            folder = summary_path.parent
            break
    if folder is None:
        folder = output_root / "score_output" / run_name / folder_dataset
    samples = []
    if not folder.is_dir():
        return samples
    for path in sorted(folder.glob("*.json")):
        if path.name == "summary.json":
            continue
        data = _read_json(path)
        if not data:
            continue
        metadata = data.get("_score_metadata") if isinstance(data.get("_score_metadata"), dict) else {}
        sample_id = str(metadata.get("sample_id") or path.stem)
        if hellobench_words and f"-{hellobench_words}-" not in sample_id:
            continue
        metrics: dict[str, float] = {}
        if _is_number(data.get("primary_score")):
            metrics["primary_score"] = float(data["primary_score"])
        aux = data.get("aux") if isinstance(data.get("aux"), dict) else {}
        for name, value in aux.items():
            if _is_number(value):
                metrics[name] = float(value)
        samples.append(
            {
                "sample": sample_id,
                "valid": data.get("valid"),
                "complete": data.get("complete"),
                "metrics": metrics,
            }
        )
    return samples


def _asset_kind(path: Path) -> str:
    name = path.stem.lower()
    if path.suffix.lower() == ".gif":
        return "动图"
    if "accept_trace" in name:
        return "Accept trace"
    if "first_accept" in name:
        return "首次接受"
    if "position_state" in name:
        return "位置状态"
    if "step_events" in name or "stepwise" in name:
        return "逐步接受"
    if "answer_trace" in name or "all_updates" in name:
        return "答案区域"
    if "forward_efficiency" in name:
        return "Forward 效率"
    if "trace" in name:
        return "Trace"
    return "其他"


@st.cache_data(show_spinner=False, ttl=30)
def load_trace_assets(output_root: Path) -> list[dict[str, Any]]:
    visual_root = output_root / "visualization_output"
    assets = []
    if not visual_root.is_dir():
        return assets

    comparison_files = {
        "accept_trace.png",
        "block_local_tau_comparison.png",
        "forward_efficiency.png",
        "trace_first_accept.png",
        "trace_position_state.png",
        "trace_step_events.png",
        "answer_trace.png",
        "trace_stepwise.csv",
    }
    sample_suffixes = (
        "_accept_trace.png",
        "_all_updates.png",
        "_block_acceptance.png",
        "_sudoku_context_trace.gif",
        "_token_trace.gif",
    )

    for path in sorted(visual_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".gif", ".csv"}:
            continue
        relative = path.relative_to(visual_root)
        parts = relative.parts
        if len(parts) < 2:
            continue
        comparison = len(parts) > 2 and parts[1] == "model_comparison"
        if comparison and path.name not in comparison_files:
            continue
        if not comparison and not path.name.endswith(sample_suffixes):
            continue
        if comparison:
            model_name = parts[0]
            dataset_name = parts[2] if len(parts) > 3 else parts[1]
        elif len(parts) >= 4:
            model_name = f"{parts[0]}/{parts[1]}"
            dataset_name = parts[2]
        else:
            model_name = parts[0]
            dataset_name = parts[1]
        sample_name = ""
        if not comparison:
            sample_name = path.name
            for suffix in sample_suffixes:
                if sample_name.endswith(suffix):
                    sample_name = sample_name[: -len(suffix)]
                    break
        assets.append(
            {
                "model": model_name,
                "dataset": dataset_name,
                "scope": "模型对比" if comparison else "单样本轨迹",
                "kind": _asset_kind(path),
                "sample": sample_name,
                "name": path.name,
                "path": path,
                "relative_path": relative.as_posix(),
                "suffix": path.suffix.lower(),
            }
        )
    return assets


@st.cache_data(show_spinner=False, ttl=30)
def load_trace_summary_records(output_root: Path) -> list[dict[str, Any]]:
    """Load public dataset-level trace summaries for interactive comparison."""
    visual_root = output_root / "visualization_output"
    records: list[dict[str, Any]] = []
    if not visual_root.is_dir():
        return records

    for path in sorted(visual_root.rglob("dataset_trace_summary.json")):
        data = _read_json(path)
        if not data:
            continue
        relative = path.relative_to(visual_root)
        if len(relative.parts) < 4:
            continue
        model = str(data.get("model") or relative.parts[0])
        config = str(data.get("config") or relative.parts[1])
        dataset = str(data.get("dataset") or relative.parts[2])
        block_tau = data.get("block_local_commit_order_tau")
        block_tau_overall = (
            block_tau.get("overall")
            if isinstance(block_tau, dict)
            and isinstance(block_tau.get("overall"), dict)
            else {}
        )
        stable_per_forward = data.get("mean_final_stable_tokens_per_forward")
        if isinstance(stable_per_forward, dict):
            stable_per_forward = stable_per_forward.get("mean")
        metrics = {
            "block_local_tau": block_tau_overall.get("mean"),
            "accepted_tokens_per_forward": data.get("accepted_tokens_per_forward"),
            "final_stable_tokens_per_forward": stable_per_forward,
            "accepted_tps": data.get("accepted_tps"),
        }
        records.append(
            {
                "run": f"{model}/{config}",
                "model": model,
                "config": config,
                "dataset": dataset,
                "metrics": {
                    name: float(value)
                    for name, value in metrics.items()
                    if _is_number(value)
                },
                "path": path,
            }
        )
    return records


@st.cache_data(show_spinner=False, ttl=30)
def load_profiling_assets(output_root: Path) -> list[dict[str, Any]]:
    """Discover public profiling figures without duplicating plot logic."""
    visual_root = output_root / "visualization_output"
    if not visual_root.is_dir():
        return []

    assets: list[dict[str, Any]] = []
    for path in sorted(visual_root.rglob("*profiling*.png")):
        relative = path.relative_to(visual_root)
        parts = relative.parts
        name = path.stem
        kind = (
            "Stage composition"
            if "stage" in name
            else "Step profiling"
            if "step" in name
            else "Profiling summary"
        )
        if parts[0] == "profiling_comparison":
            dataset = name
            for prefix in (
                "profiling_step_comparison_",
                "profiling_stage_comparison_",
            ):
                if dataset.startswith(prefix):
                    dataset = dataset[len(prefix):]
                    break
            if name == "profiling_totals_comparison":
                dataset = "all datasets"
            assets.append(
                {
                    "scope": "Cross-model comparison",
                    "model": "all selected models",
                    "dataset": dataset,
                    "kind": kind,
                    "name": name,
                    "path": path,
                }
            )
            continue

        if len(parts) < 3:
            continue
        if len(parts) >= 4:
            model_name = f"{parts[0]}/{parts[1]}"
            dataset_name = parts[2]
        else:
            model_name = parts[0]
            dataset_name = parts[1]
        assets.append(
            {
                "scope": "Single model",
                "model": model_name,
                "dataset": dataset_name,
                "kind": kind,
                "name": name,
                "path": path,
            }
        )
    return assets


@st.cache_data(show_spinner=False, ttl=30)
def load_profiling_comparison_records(output_root: Path) -> list[dict[str, Any]]:
    """Load profiling aggregates for interactive comparisons."""
    csv_path = (
        output_root
        / "visualization_output"
        / "profiling_comparison"
        / "profiling_comparison.csv"
    )
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    numeric_fields = (
        "profiled_samples",
        "step_count",
        "time_seconds",
        "compute_tflops",
        "accepted_tokens",
        "time_per_accepted_token",
        "accepted_token_tps",
        "compute_per_accepted_token",
    )
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                model = str(raw.get("model") or "")
                config = str(raw.get("config") or "")
                dataset = str(raw.get("dataset") or "")
                if not model or not config or not dataset:
                    continue
                metrics: dict[str, float] = {}
                for field in numeric_fields:
                    value = raw.get(field)
                    if value not in {None, ""}:
                        try:
                            metrics[field] = float(value)
                        except ValueError:
                            pass
                steps = metrics.get("step_count")
                accepted = metrics.get("accepted_tokens")
                if steps and accepted is not None:
                    metrics["accepted_tokens_per_forward"] = accepted / steps
                key = (model, config, dataset)
                seen.add(key)
                records.append(
                    {
                        "run": str(raw.get("label") or f"{model}/{config}"),
                        "model": model,
                        "config": config,
                        "dataset": dataset,
                        "status": str(raw.get("measurement_status") or "unknown"),
                        "metrics": metrics,
                    }
                )

    profiling_root = output_root / "model_profiling"
    if profiling_root.is_dir():
        for path in profiling_root.rglob("oom_info.json"):
            relative = path.relative_to(profiling_root).parts
            if len(relative) < 4:
                continue
            model, config, dataset = relative[:3]
            key = (model, config, dataset)
            if key in seen:
                continue
            records.append(
                {
                    "run": f"{model}/{config}",
                    "model": model,
                    "config": config,
                    "dataset": dataset,
                    "status": "oom",
                    "metrics": {},
                }
            )
    return records
