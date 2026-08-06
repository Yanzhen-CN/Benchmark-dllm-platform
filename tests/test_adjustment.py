from __future__ import annotations

import pytest

from platform_core.adjustment import adjustment_rows


def _record(run: str, *, score: float, seconds: float, watts: float):
    return {
        "run": run,
        "dataset": "gsm8k",
        "primary_score": score,
        "performance_metrics": {"time_per_sample": seconds, "eps": watts},
    }


def test_adjustment_is_directional_and_labels_ratios_explicitly():
    rows, missing = adjustment_rows(
        [
            _record("base", score=0.6, seconds=20.0, watts=400.0),
            _record("target", score=0.5, seconds=10.0, watts=200.0),
        ],
        base_run="base",
        target_run="target",
        selected_datasets=["gsm8k"],
        beta=0.5,
        gamma=0.5,
    )

    assert missing == []
    assert rows[0]["目标速度 / 基线速度"] == pytest.approx(2.0)
    assert rows[0]["基线功率 / 目标功率"] == pytest.approx(2.0)
    assert rows[0]["资源修正"] == pytest.approx(0.25)
    assert rows[0]["目标折算指数"] == pytest.approx(0.75)


def test_adjustment_reports_missing_pair_data():
    rows, missing = adjustment_rows(
        [_record("base", score=0.6, seconds=20.0, watts=400.0)],
        base_run="base",
        target_run="target",
        selected_datasets=["gsm8k"],
        beta=0.5,
        gamma=0.5,
    )

    assert rows == []
    assert missing == ["gsm8k"]
