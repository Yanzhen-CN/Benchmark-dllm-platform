from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_ROOT = PLATFORM_ROOT.parent / "Benchmark-dllm"


@dataclass(frozen=True)
class PlatformPaths:
    benchmark_root: Path
    output_root: Path
    platform_root: Path = PLATFORM_ROOT

    @classmethod
    def from_values(
        cls,
        benchmark_root: str | Path | None = None,
        output_root: str | Path | None = None,
    ) -> "PlatformPaths":
        root = Path(
            benchmark_root
            or os.environ.get("DLLM_BENCH_ROOT", DEFAULT_BENCHMARK_ROOT)
        ).expanduser().resolve()
        output = Path(
            output_root
            or os.environ.get("DLLM_BENCH_OUTPUT_ROOT", root / "output")
        ).expanduser().resolve()
        return cls(benchmark_root=root, output_root=output)

    @property
    def models_dir(self) -> Path:
        return self.benchmark_root / "configs" / "models"

    @property
    def datasets_dir(self) -> Path:
        return self.benchmark_root / "configs" / "datasets"

    @property
    def experiments_dir(self) -> Path:
        return self.benchmark_root / "configs" / "experiments"

    @property
    def launcher(self) -> Path:
        return self.benchmark_root / "run_bench.py"

    @property
    def state_dir(self) -> Path:
        return self.platform_root / ".state" / "runs"

    def is_ready(self) -> bool:
        return self.launcher.is_file() and self.models_dir.is_dir()

