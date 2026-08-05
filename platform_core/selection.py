from __future__ import annotations

from typing import Any, Iterable

import streamlit as st


SUDOKU_ORDER = {
    "sudoku4": 0,
    "sudoku4_1shot": 1,
    "sudoku4_thinking": 2,
    "sudoku9": 3,
    "sudoku9_1shot": 4,
    "sudoku9_thinking": 5,
}
HELLOBENCH_ORDER = {"hellobench_2k": 0, "hellobench_4k": 1}


def dataset_label(name: str) -> str:
    return {
        "hellobench_2k": "2k",
        "hellobench_4k": "4k",
        "sudoku4": "4x4 · Direct",
        "sudoku4_1shot": "4x4 · 1-shot",
        "sudoku4_thinking": "4x4 · Thinking",
        "sudoku9": "9x9 · Direct",
        "sudoku9_1shot": "9x9 · 1-shot",
        "sudoku9_thinking": "9x9 · Thinking",
    }.get(name, name)


def _split_datasets(
    options: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    names = sorted(set(options))
    hellobench = sorted(
        (name for name in names if name.startswith("hellobench_")),
        key=lambda name: (HELLOBENCH_ORDER.get(name, 100), name),
    )
    sudoku = sorted(
        (name for name in names if name.startswith("sudoku")),
        key=lambda name: (SUDOKU_ORDER.get(name, 100), name),
    )
    children = set(hellobench) | set(sudoku)
    ordinary = [name for name in names if name not in children]
    return ordinary, hellobench, sudoku


def _default_hellobench(children: list[str], defaults: set[str]) -> list[str]:
    selected = [name for name in children if name in defaults]
    if selected:
        return selected
    return ["hellobench_2k"] if "hellobench_2k" in children else children[:1]


def _default_sudoku(children: list[str], defaults: set[str]) -> list[str]:
    selected = [name for name in children if name in defaults]
    if selected:
        visible_defaults = [name for name in selected if name != "sudoku9_1shot"]
        return visible_defaults or selected[:1]
    if "sudoku4_1shot" in children:
        return ["sudoku4_1shot"]
    one_shot = [name for name in children if name.endswith("_1shot")]
    return one_shot[:1] or children[:1]


def select_dataset_subsets(
    dataset_options: Iterable[str],
    *,
    default_datasets: Iterable[str] = (),
    key_prefix: str,
) -> list[str]:
    ordinary, hellobench, sudoku = _split_datasets(dataset_options)
    defaults = set(default_datasets)
    parent_options = [
        *ordinary,
        *(["HelloBench"] if hellobench else []),
        *(["Sudoku"] if sudoku else []),
    ]
    default_parents = [name for name in ordinary if name in defaults]
    if any(name in defaults for name in hellobench):
        default_parents.append("HelloBench")
    if any(name in defaults for name in sudoku):
        default_parents.append("Sudoku")

    selected_parents = st.multiselect(
        "数据集",
        parent_options,
        default=default_parents,
        key=f"{key_prefix}_dataset_groups",
    )
    selected = [name for name in ordinary if name in selected_parents]
    if "HelloBench" in selected_parents:
        selected.extend(
            st.multiselect(
                "HelloBench 长度",
                hellobench,
                default=_default_hellobench(hellobench, defaults),
                format_func=dataset_label,
                key=f"{key_prefix}_hellobench_subsets",
            )
        )
    if "Sudoku" in selected_parents:
        selected.extend(
            st.multiselect(
                "Sudoku 子集",
                sudoku,
                default=_default_sudoku(sudoku, defaults),
                format_func=dataset_label,
                key=f"{key_prefix}_sudoku_subsets",
                help="每个子集使用独立的 prompt、预算和评分结果。",
            )
        )
    return selected


def select_run_datasets(
    dataset_options: Iterable[str],
    *,
    key_prefix: str,
) -> tuple[list[str], list[str]]:
    names = sorted(set(dataset_options))
    sudoku = sorted(
        (name for name in names if name.startswith("sudoku")),
        key=lambda name: (SUDOKU_ORDER.get(name, 100), name),
    )
    has_hellobench = "hellobench" in names
    ordinary = [
        name
        for name in names
        if name != "hellobench" and not name.startswith("sudoku")
    ]
    parent_options = [
        *ordinary,
        *(["HelloBench"] if has_hellobench else []),
        *(["Sudoku"] if sudoku else []),
    ]
    selected_parents = st.multiselect(
        "数据集",
        parent_options,
        default=[],
        key=f"{key_prefix}_dataset_groups",
    )
    selected = [name for name in ordinary if name in selected_parents]
    lengths: list[str] = []
    if "HelloBench" in selected_parents:
        selected.append("hellobench")
        lengths = st.multiselect(
            "HelloBench 长度",
            ["2k", "4k"],
            default=["2k"],
            key=f"{key_prefix}_hellobench_lengths",
            help="2k 和 4k 共用 HelloBench 配置；默认只运行 2k。",
        )
    if "Sudoku" in selected_parents:
        selected.extend(
            st.multiselect(
                "Sudoku 子集",
                sudoku,
                default=_default_sudoku(sudoku, set()),
                format_func=dataset_label,
                key=f"{key_prefix}_sudoku_subsets",
                help="默认选择 4x4 · 1-shot。",
            )
        )
    return selected, lengths


def select_single_dataset(
    dataset_options: Iterable[str],
    *,
    key_prefix: str,
    default_dataset: str | None = None,
) -> str | None:
    ordinary, hellobench, sudoku = _split_datasets(dataset_options)
    if not ordinary and not hellobench and not sudoku:
        return None
    parent_options = [
        *ordinary,
        *(["HelloBench"] if hellobench else []),
        *(["Sudoku"] if sudoku else []),
    ]
    default_parent = (
        "HelloBench"
        if default_dataset in hellobench
        else "Sudoku"
        if default_dataset in sudoku
        else default_dataset
    )
    index = parent_options.index(default_parent) if default_parent in parent_options else 0
    parent = st.selectbox(
        "数据集",
        parent_options,
        index=index,
        key=f"{key_prefix}_dataset_group",
    )
    if parent == "HelloBench":
        child_index = hellobench.index(default_dataset) if default_dataset in hellobench else 0
        return st.selectbox(
            "HelloBench 长度",
            hellobench,
            index=child_index,
            format_func=dataset_label,
            key=f"{key_prefix}_hellobench_subset",
        )
    if parent == "Sudoku":
        default_children = _default_sudoku(
            sudoku,
            {default_dataset} if default_dataset else set(),
        )
        child = default_children[0]
        return st.selectbox(
            "Sudoku 子集",
            sudoku,
            index=sudoku.index(child),
            format_func=dataset_label,
            key=f"{key_prefix}_sudoku_subset",
        )
    return parent


def select_model_variants(
    records: list[dict[str, Any]],
    *,
    default_runs: Iterable[str],
    key_prefix: str,
) -> list[str]:
    default_run_set = set(default_runs)
    model_options = sorted({record["model"] for record in records})
    default_models = sorted(
        {
            record["model"]
            for record in records
            if record["run"] in default_run_set
        }
    )
    selected_models = st.multiselect(
        "主模型",
        model_options,
        default=default_models or model_options[:3],
        key=f"{key_prefix}_models",
    )

    run_records: dict[str, dict[str, Any]] = {}
    for record in records:
        if record["model"] in selected_models:
            run_records.setdefault(record["run"], record)
    run_options = sorted(
        run_records,
        key=lambda run: (
            run_records[run]["model"],
            run_records[run]["config"],
            run,
        ),
    )
    selected_defaults = [run for run in default_runs if run in run_options]
    if not selected_defaults:
        first_by_model: dict[str, str] = {}
        for run in run_options:
            first_by_model.setdefault(run_records[run]["model"], run)
        selected_defaults = list(first_by_model.values())

    def run_label(run: str) -> str:
        record = run_records[run]
        model = {
            "diffusiongemma": "DiffusionGemma",
            "gemma": "Gemma",
            "dreamreasoner": "DreamReasoner",
            "illada": "iLLaDA",
            "illada_vargen": "iLLaDA-VarGen",
            "llada2_1": "LLaDA2.1",
        }.get(record["model"], record["model"])
        return f"{model} / {record['config']}"

    return st.multiselect(
        "变体 / 运行",
        run_options,
        default=selected_defaults,
        format_func=run_label,
        key=f"{key_prefix}_runs",
    )
