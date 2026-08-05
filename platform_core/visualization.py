from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from .paths import PlatformPaths


MATRIX_DATASETS = (
    "sudoku9_thinking",
    "sudoku4_thinking",
    "sudoku9_1shot",
    "sudoku4_1shot",
    "structeval_t",
    "hellobench",
    "sudoku9",
    "sudoku4",
    "gsm8k",
    "mbpp",
    "ruler",
)


def child_directories(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(item.name for item in path.iterdir() if item.is_dir())


def sample_ids(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(
        item.stem
        for item in path.glob("*.json")
        if not item.name.startswith("_") and item.name != "oom_info.json"
    )


def _dataset_arguments(dataset: str) -> list[str]:
    if dataset in MATRIX_DATASETS:
        return ["-d", dataset]
    for base in MATRIX_DATASETS:
        prefix = f"{base}_"
        if dataset.startswith(prefix):
            return ["-d", base, "--output-suffix", dataset[len(prefix) :]]
    return ["-d", dataset]


def trace_command(
    paths: PlatformPaths,
    *,
    model: str,
    variant: str,
    dataset: str,
    sample: str,
) -> list[str]:
    root = paths.benchmark_root
    root_python = root / ".venvs" / "root" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    return [
        str(root_python if root_python.exists() else Path(sys.executable)),
        str(root / "run_visualization.py"),
        "--matrix",
        str(root / "configs" / "experiments" / "full_matrix.yaml"),
        "-m",
        model,
        *_dataset_arguments(dataset),
        "-v",
        variant,
        "--scope",
        "sample",
        "--sample-ids",
        sample,
        "--no-report",
    ]


def launch_visualization(
    paths: PlatformPaths,
    command: list[str],
) -> tuple[subprocess.Popen[str], Path]:
    state_dir = paths.platform_root / ".platform_state"
    state_dir.mkdir(exist_ok=True)
    log_path = state_dir / "trace_visualization.log"
    handle = log_path.open("w", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        command,
        cwd=paths.benchmark_root,
        env=environment,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    handle.close()
    return process, log_path
