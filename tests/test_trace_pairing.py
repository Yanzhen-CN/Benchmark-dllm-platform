from __future__ import annotations

from platform_core.visualization import (
    common_trace_datasets,
    common_trace_samples,
)


def _sample(root, run: str, dataset: str, sample: str) -> None:
    model, variant = run.split("/", 1)
    path = root / model / variant / dataset / f"{sample}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")


def test_trace_pairing_keeps_only_common_dataset_and_sample(tmp_path):
    _sample(tmp_path, "llada2_1/qmode", "sudoku4_1shot", "shared")
    _sample(tmp_path, "llada2_1/qmode", "sudoku4_1shot", "llada-only")
    _sample(tmp_path, "diffusiongemma/official", "sudoku4_1shot", "shared")
    _sample(tmp_path, "diffusiongemma/official", "gsm8k", "dg-only")
    runs = ["llada2_1/qmode", "diffusiongemma/official"]

    assert common_trace_datasets(tmp_path, runs) == ["sudoku4_1shot"]
    assert common_trace_samples(tmp_path, runs, "sudoku4_1shot") == ["shared"]
