from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
import yaml


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def configured_profiling_records(benchmark_root: Path) -> list[dict[str, Any]]:
    """Expand the profiling matrix into pending records for platform discovery."""
    matrix_path = benchmark_root / "configs" / "experiments" / "profiling_matrix.yaml"
    matrix = _yaml_mapping(matrix_path)
    if not matrix:
        return []

    base = (matrix_path.parent / str(matrix.get("base_dir") or ".")).resolve()
    runs: list[tuple[str, str]] = []
    for entry in matrix.get("models") or []:
        if not isinstance(entry, dict) or not entry.get("config"):
            continue
        model_path = (base / str(entry["config"])).resolve()
        model_data = _yaml_mapping(model_path)
        model = str(model_data.get("model") or model_path.stem)
        variants = entry.get("variants")
        if not isinstance(variants, list):
            configs = model_data.get("configs") or {}
            variants = list(configs) if isinstance(configs, dict) else []
        runs.extend((model, str(variant)) for variant in variants)

    datasets: list[str] = []
    for entry in matrix.get("datasets") or []:
        if not isinstance(entry, dict) or not entry.get("config"):
            continue
        dataset_path = (base / str(entry["config"])).resolve()
        dataset_data = _yaml_mapping(dataset_path)
        datasets.append(str(dataset_data.get("dataset") or dataset_path.stem))

    return [
        {
            "run": f"{model}/{config}",
            "model": model,
            "config": config,
            "dataset": dataset,
            "sample": None,
            "status": "pending",
            "metrics": {},
            "steps": [],
            "stages": [],
        }
        for model, config in runs
        for dataset in datasets
    ]


def configured_profiling_models(benchmark_root: Path) -> list[str]:
    return sorted(
        {record["model"] for record in configured_profiling_records(benchmark_root)}
    )


def _merge_configured_records(
    records: list[dict[str, Any]], benchmark_root: Path | None
) -> list[dict[str, Any]]:
    if benchmark_root is None:
        return records
    observed = {(record["run"], record["dataset"]) for record in records}
    records.extend(
        record
        for record in configured_profiling_records(benchmark_root)
        if (record["run"], record["dataset"]) not in observed
    )
    return sorted(
        records,
        key=lambda record: (
            record["model"],
            record["config"],
            record["dataset"],
            record.get("sample") or "",
        ),
    )


@st.cache_resource(show_spinner=False, ttl=30)
def load_profiling_detail_records(
    output_root: Path, benchmark_root: Path | None = None
) -> list[dict[str, Any]]:
    profiling_root = output_root / "model_profiling"
    records: list[dict[str, Any]] = []
    if not profiling_root.exists():
        return _merge_configured_records(records, benchmark_root)

    for path in profiling_root.glob("*/*/*/*.json"):
        if path.name == "_meta.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        relative = path.relative_to(profiling_root)
        model, config, dataset = relative.parts[:3]
        if path.name == "oom_info.json":
            records.append(
                {
                    "run": f"{model}/{config}",
                    "model": model,
                    "config": config,
                    "dataset": dataset,
                    "sample": data.get("sample_id"),
                    "status": "oom",
                    "metrics": {},
                    "steps": [],
                    "stages": [],
                    "failure_stage": data.get("failure_stage"),
                    "error_type": data.get("error_type") or data.get("error_class"),
                    "error_message": data.get("error_message"),
                    "gpu": data.get("gpu"),
                }
            )
            continue
        if data.get("status") != "success":
            continue
        steps = data.get("step_profiles")
        if not isinstance(steps, list):
            steps = []
        extra = data.get("extra")
        stages = extra.get("stage_profiles") if isinstance(extra, dict) else []
        if not isinstance(stages, list):
            stages = []

        timing = data.get("timing")
        elapsed = (
            _number(timing.get("wall_clock_seconds"))
            if isinstance(timing, dict)
            else None
        )
        compute = _number(data.get("compute_tflops"))
        if compute is None and steps:
            step_compute = [_number(step.get("compute_tflops")) for step in steps]
            if all(value is not None for value in step_compute):
                compute = sum(value or 0.0 for value in step_compute)

        accepted_values = [
            _number(step.get("accepted_tokens"))
            for step in steps
            if isinstance(step, dict)
        ]
        accepted = (
            sum(value or 0.0 for value in accepted_values)
            if accepted_values and all(value is not None for value in accepted_values)
            else None
        )
        step_count = len(steps) or None
        metrics = {
            "accepted_tokens": accepted,
            "accepted_tokens_per_second": (
                accepted / elapsed
                if accepted is not None and elapsed and elapsed > 0
                else None
            ),
            "compute_tflops": compute,
            "compute_per_second": (
                compute / elapsed if compute is not None and elapsed and elapsed > 0 else None
            ),
            "compute_per_accepted_token": (
                compute / accepted
                if compute is not None and accepted and accepted > 0
                else None
            ),
            "step_count": float(step_count) if step_count is not None else None,
            "accepted_tokens_per_forward": (
                accepted / step_count
                if accepted is not None and step_count
                else None
            ),
        }
        records.append(
            {
                "run": f"{model}/{config}",
                "model": model,
                "config": config,
                "dataset": dataset,
                "sample": path.stem,
                "status": "success",
                "metrics": {
                    key: value for key, value in metrics.items() if value is not None
                },
                "steps": steps,
                "stages": stages,
            }
        )
    return _merge_configured_records(records, benchmark_root)
