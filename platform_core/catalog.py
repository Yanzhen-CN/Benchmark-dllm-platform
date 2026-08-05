from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .paths import PlatformPaths


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return value


@dataclass(frozen=True)
class ModelSpec:
    name: str
    variants: tuple[str, ...]
    max_context_tokens: int | None
    path: Path


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    primary_metric: str
    sample_size: int | None
    path: Path
    group: str = "Core"
    mode: str = "Direct"
    max_new_tokens: int | None = None
    optional: bool = False


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    path: Path


def _dataset_spec(
    config_path: Path,
    matrix_entry: dict[str, Any] | None = None,
) -> DatasetSpec:
    data = _load_yaml(config_path)
    entry = matrix_entry or {}
    name = str(data.get("dataset") or config_path.stem)
    size = entry.get("n_samples", data.get("sample_size"))
    budget = entry.get("max_new_tokens", data.get("max_new_tokens"))
    mode = (
        "2k / 4k"
        if name == "hellobench"
        else "Thinking"
        if name.endswith("_thinking")
        else "1-shot"
        if "_1shot" in name
        else "Direct"
    )
    return DatasetSpec(
        name=name,
        primary_metric=str(data.get("primary_metric") or "N/A"),
        sample_size=int(size) if size is not None else None,
        path=config_path,
        group=(
            "Sudoku"
            if name.startswith("sudoku")
            else "HelloBench"
            if name == "hellobench"
            else "Core"
        ),
        mode=mode,
        max_new_tokens=int(budget) if budget is not None else None,
        optional=bool(entry.get("optional", False)),
    )


def discover_models(paths: PlatformPaths) -> list[ModelSpec]:
    models: list[ModelSpec] = []
    if not paths.models_dir.is_dir():
        return models
    for config_path in sorted(paths.models_dir.glob("*.yaml")):
        data = _load_yaml(config_path)
        configs = data.get("configs") or {}
        variants = tuple(str(name) for name in configs) if isinstance(configs, dict) else ()
        context = data.get("max_context_tokens")
        models.append(
            ModelSpec(
                name=str(data.get("model") or config_path.stem),
                variants=variants,
                max_context_tokens=int(context) if context is not None else None,
                path=config_path,
            )
        )
    return models


def discover_datasets(paths: PlatformPaths) -> list[DatasetSpec]:
    if not paths.datasets_dir.is_dir():
        return []
    return [_dataset_spec(path) for path in sorted(paths.datasets_dir.glob("*.yaml"))]


def discover_experiment_datasets(
    paths: PlatformPaths,
    experiment_path: str | Path,
) -> list[DatasetSpec]:
    matrix_path = Path(experiment_path).resolve()
    matrix = _load_yaml(matrix_path)
    base = (matrix_path.parent / str(matrix.get("base_dir") or ".")).resolve()
    datasets: list[DatasetSpec] = []
    for raw_entry in matrix.get("datasets") or []:
        entry = raw_entry if isinstance(raw_entry, dict) else {"config": raw_entry}
        config_ref = entry.get("config")
        if not config_ref:
            continue
        config_path = Path(str(config_ref))
        if not config_path.is_absolute():
            config_path = (base / config_path).resolve()
        if config_path.is_file():
            datasets.append(_dataset_spec(config_path, entry))
    return datasets


def discover_experiments(paths: PlatformPaths) -> list[ExperimentSpec]:
    if not paths.experiments_dir.is_dir():
        return []
    return [
        ExperimentSpec(name=path.stem, path=path)
        for path in sorted(paths.experiments_dir.glob("*.yaml"))
    ]
