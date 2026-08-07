from __future__ import annotations

import os
from pathlib import Path
import json
import re
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


def has_sudoku_answer_trace(path: Path, dataset: str) -> bool:
    """Return whether a saved trace visibly forms one complete Sudoku answer."""

    size = 4 if dataset.startswith("sudoku4") else 9
    pattern = re.compile(rf"(?<![0-9])[1-{size}]{{{size * size}}}(?![0-9])")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return False
    return any(
        pattern.search(str(step.get("decoded_text") or "")) is not None
        for step in payload.get("trace", [])
        if isinstance(step, dict)
    )


def comparable_sudoku_samples(
    model_output_root: Path,
    runs: list[str],
    dataset: str,
) -> list[str]:
    """Find common sample IDs whose traces form an answer in every run."""

    sample_sets = []
    for run in runs:
        model, separator, variant = run.partition("/")
        if not separator:
            return []
        run_root = model_output_root / model / variant / dataset
        sample_sets.append(set(sample_ids(run_root)))
    if not sample_sets:
        return []
    common = set.intersection(*sample_sets)
    return [
        sample_id
        for sample_id in sorted(common)
        if all(
            has_sudoku_answer_trace(
                model_output_root
                / run.partition("/")[0]
                / run.partition("/")[2]
                / dataset
                / f"{sample_id}.json",
                dataset,
            )
            for run in runs
        )
    ]


def _dataset_arguments(dataset: str) -> list[str]:
    if dataset in MATRIX_DATASETS:
        return ["-d", dataset]
    for base in MATRIX_DATASETS:
        prefix = f"{base}_"
        if dataset.startswith(prefix):
            return ["-d", base, "--output-suffix", dataset[len(prefix) :]]
    return ["-d", dataset]


def _matrix_for_model(root: Path, model: str) -> Path:
    if model == "llada2_1":
        return root / "configs" / "experiments" / "llada2_1_sudoku.yaml"
    return root / "configs" / "experiments" / "full_matrix.yaml"


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
        str(_matrix_for_model(root, model)),
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


def trace_batch_command(
    paths: PlatformPaths,
    *,
    runs: list[str],
    dataset: str,
    sample: str,
) -> list[list[str]]:
    if not runs:
        raise ValueError("a Sudoku trace batch requires at least one run")
    commands: list[list[str]] = []
    for run in runs:
        model, separator, variant = run.partition("/")
        if not separator or not model or not variant:
            raise ValueError(f"invalid run {run!r}; expected MODEL/VARIANT")
        commands.append(
            trace_command(
                paths,
                model=model,
                variant=variant,
                dataset=dataset,
                sample=sample,
            )
        )
    return commands


def trace_artifacts(
    paths: PlatformPaths,
    *,
    model: str,
    variant: str,
    dataset: str,
    sample: str,
) -> dict[str, Path]:
    root = (
        paths.output_root
        / "visualization_output"
        / model
        / variant
        / dataset
    )
    return {
        "accept_trace": root / f"{sample}_accept_trace.png",
        "token_trace": root / f"{sample}_token_trace.gif",
        "sudoku_trace": root / f"{sample}_sudoku_context_trace.gif",
    }


def platform_chart_command(
    paths: PlatformPaths,
    *,
    section: str,
    key: str,
    spec: dict,
) -> tuple[list[str], Path]:
    safe_section = re.sub(r"[^A-Za-z0-9_.-]+", "_", section).strip("_")
    safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_")
    output_path = (
        paths.output_root
        / "visualization_output"
        / "platform"
        / safe_section
        / f"{safe_key}.png"
    )
    state_dir = paths.platform_root / ".platform_state" / "chart_specs"
    state_dir.mkdir(parents=True, exist_ok=True)
    spec_path = state_dir / f"{safe_section}__{safe_key}.json"
    spec_path.write_text(
        json.dumps({**spec, "output_path": str(output_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    root = paths.benchmark_root
    root_python = root / ".venvs" / "root" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    command = [
        str(root_python if root_python.exists() else Path(sys.executable)),
        str(root / "run_visualization.py"),
        "--preset",
        "platform-chart",
        "--chart-spec",
        str(spec_path),
        "--no-report",
    ]
    return command, output_path


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


def run_visualization_command(
    paths: PlatformPaths,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=paths.benchmark_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
