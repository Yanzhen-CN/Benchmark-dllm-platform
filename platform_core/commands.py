from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .paths import PlatformPaths


@dataclass(frozen=True)
class RunSelection:
    models: tuple[str, ...]
    datasets: tuple[str, ...]
    matrix: Path
    stage: str = "all"
    variants: tuple[str, ...] = ()
    hellobench_lengths: tuple[str, ...] = ()
    real_data: bool = True
    n_samples: int | None = None
    enable_reasoning: bool = False
    measure_compute: bool = False
    dry_run: bool = True


def build_run_command(paths: PlatformPaths, selection: RunSelection) -> list[str]:
    if not selection.models:
        raise ValueError("Select at least one model.")
    if not selection.datasets:
        raise ValueError("Select at least one dataset.")
    command = [
        sys.executable,
        str(paths.launcher),
        "--matrix",
        str(selection.matrix),
        "--model",
        *selection.models,
        "--dataset",
        *selection.datasets,
        "--stage",
        selection.stage,
        "--output-root",
        str(paths.output_root),
        "--real-data" if selection.real_data else "--demo",
    ]
    if selection.variants:
        command.extend(["-v", *selection.variants])
    if selection.hellobench_lengths:
        command.extend(["--hellobench-length", *selection.hellobench_lengths])
    if selection.n_samples is not None:
        command.extend(["--n-samples", str(selection.n_samples)])
    if selection.enable_reasoning:
        command.append("--enable-reasoning")
    if selection.measure_compute:
        command.append("--measure-compute")
    if selection.dry_run:
        command.append("--dry-run")
    return command


def command_text(command: list[str]) -> str:
    return subprocess.list2cmdline(command)
