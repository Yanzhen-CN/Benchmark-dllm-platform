from __future__ import annotations

from typing import Any


def average_power(record: dict[str, Any]) -> float | None:
    metrics = record["performance_metrics"]
    if metrics.get("eps") is not None:
        return float(metrics["eps"])
    energy = metrics.get("energy_per_sample")
    elapsed = metrics.get("time_per_sample")
    if energy is not None and elapsed:
        return float(energy) / float(elapsed)
    total_energy = metrics.get("total_energy_joules")
    total_time = metrics.get("total_time_seconds")
    if total_energy is not None and total_time:
        return float(total_energy) / float(total_time)
    return None


def adjustment_rows(
    records: list[dict[str, Any]],
    *,
    base_run: str,
    target_run: str,
    selected_datasets: list[str],
    beta: float,
    gamma: float,
) -> tuple[list[dict[str, float | str]], list[str]]:
    """Build a directional resource-adjustment sensitivity table.

    ``base_run`` is held fixed. ``target_run`` receives the diagnostic
    adjustment. Beta and gamma are fractions in ``[0, 1]``.
    """
    lookup = {(record["run"], record["dataset"]): record for record in records}
    rows: list[dict[str, float | str]] = []
    missing: list[str] = []
    for dataset_name in selected_datasets:
        base = lookup.get((base_run, dataset_name))
        target = lookup.get((target_run, dataset_name))
        if base is None or target is None:
            missing.append(dataset_name)
            continue
        base_time = base["performance_metrics"].get("time_per_sample")
        target_time = target["performance_metrics"].get("time_per_sample")
        base_power = average_power(base)
        target_power = average_power(target)
        if not all((base_time, target_time, base_power, target_power)):
            missing.append(dataset_name)
            continue

        target_speed_over_base = float(base_time) / float(target_time)
        base_power_over_target = float(base_power) / float(target_power)
        speed_delta = 1.0 - float(target_time) / float(base_time)
        power_delta = 1.0 - float(target_power) / float(base_power)
        resource_delta = beta * ((1.0 - gamma) * speed_delta + gamma * power_delta)
        rows.append(
            {
                "数据集": dataset_name,
                "基线原始分数": float(base["primary_score"]),
                "目标原始分数": float(target["primary_score"]),
                "目标速度 / 基线速度": target_speed_over_base,
                "基线功率 / 目标功率": base_power_over_target,
                "速度修正项": speed_delta,
                "功率修正项": power_delta,
                "资源修正": resource_delta,
                "目标折算指数": float(target["primary_score"]) + resource_delta,
            }
        )
    return rows, missing
