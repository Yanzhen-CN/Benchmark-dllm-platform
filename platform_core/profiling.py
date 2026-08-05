from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def load_profiling_detail_records(output_root: Path) -> list[dict[str, Any]]:
    profiling_root = output_root / "model_profiling"
    records: list[dict[str, Any]] = []
    if not profiling_root.exists():
        return records

    for path in profiling_root.glob("*/*/*/*.json"):
        if path.name in {"_meta.json", "oom_info.json"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("status") != "success":
            continue

        relative = path.relative_to(profiling_root)
        model, config, dataset = relative.parts[:3]
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
                "metrics": {
                    key: value for key, value in metrics.items() if value is not None
                },
                "steps": steps,
                "stages": stages,
            }
        )
    return records
