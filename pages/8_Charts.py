from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import streamlit as st

from platform_core.maintenance import (
    empty_trash,
    list_trash_entries,
    move_output_paths_to_trash,
    restore_trash_entry,
)
from platform_core.ui import zoomable_image


st.set_page_config(page_title="Charts", page_icon="▦", layout="wide")
st.markdown(
    """
    <style>
    .st-key-clear_visualizations button {background:#b42318!important;color:white!important;border-color:#b42318!important}
    .st-key-open_empty_chart_trash button {background:#b42318!important;color:white!important;border-color:#b42318!important}
    .viz-card {border:1px solid #d9d5cb;border-radius:14px;padding:14px 16px;background:#fffdf8;margin:8px 0 18px}
    .viz-path {font-family:monospace;font-size:.78rem;color:#655f55;overflow-wrap:anywhere}
    [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {overflow-x:hidden!important;max-width:100%!important}
    .viz-scroll {display:block;width:100%;max-width:100%;min-width:0;overflow-x:auto;box-sizing:border-box}
    .viz-kicker {font-size:.76rem;letter-spacing:.12em;text-transform:uppercase;color:#167665;font-weight:700;margin-bottom:.35rem}
    .viz-note {color:#655f55;font-size:.9rem;line-height:1.55;margin:.15rem 0 .75rem}
    .st-key-generate_visualization button {min-height:2.75rem;font-weight:700}
    </style>
    """,
    unsafe_allow_html=True,
)


def benchmark_root() -> Path:
    configured = os.environ.get("BENCHMARK_DLLM_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for key, value in st.session_state.items():
        if "benchmark" not in str(key).lower() or not isinstance(value, (str, Path)):
            continue
        candidate = Path(value).expanduser()
        if (candidate / "run_visualization.py").exists():
            return candidate.resolve()
    return (Path(__file__).resolve().parents[2] / "Benchmark-dllm").resolve()


ROOT = benchmark_root()
OUTPUT = ROOT / "output"
VISUALS = OUTPUT / "visualization_output"
PAPER = OUTPUT / "report" / "paper_assets"
MATRIX = ROOT / "configs" / "experiments" / "full_matrix.yaml"
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


def dirs(path: Path) -> list[str]:
    return sorted(item.name for item in path.iterdir() if item.is_dir()) if path.exists() else []


def datasets(model: str, variant: str) -> list[str]:
    return dirs(OUTPUT / "model_output" / model / variant)


def samples(model: str, variant: str, dataset: str) -> list[str]:
    source = OUTPUT / "model_output" / model / variant / dataset
    if not source.exists():
        return []
    return sorted(
        path.stem
        for path in source.glob("*.json")
        if not path.name.startswith("_") and path.name != "oom_info.json"
    )


def dataset_arguments(dataset: str) -> list[str]:
    if dataset in MATRIX_DATASETS:
        return ["-d", dataset]
    for base in MATRIX_DATASETS:
        prefix = f"{base}_"
        if dataset.startswith(prefix):
            return ["-d", base, "--output-suffix", dataset[len(prefix):]]
    return ["-d", dataset]


def command_for(preset: str) -> list[str]:
    root_python = (
        ROOT / ".venvs" / "root" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    command = [
        str(root_python if root_python.exists() else Path(sys.executable)),
        str(ROOT / "run_visualization.py"),
    ]
    if preset == "Report overview":
        selected = st.session_state.get(
            "report_models", ["dreamreasoner", "illada_vargen"]
        )
        chosen_datasets = st.session_state.get(
            "report_datasets", ["mbpp", "gsm8k", "structeval_t"]
        )
        return [
            *command,
            "--preset",
            "report-assets",
            "-m",
            *selected,
            "-d",
            *chosen_datasets,
        ]
    if preset == "Profiling comparison":
        selected = st.session_state.get(
            "profiling_models",
            ["illada", "illada_vargen", "dreamreasoner", "diffusiongemma"],
        )
        chosen_datasets = st.session_state.get(
            "profiling_datasets", ["mbpp", "gsm8k", "structeval_t"]
        )
        return [
            *command,
            "--preset",
            "profiling-comparison",
            "-m",
            *selected,
            "-d",
            *chosen_datasets,
        ]
    if preset == "DiffusionGemma forward comparison":
        return [
            *command,
            "--matrix",
            str(MATRIX),
            "-m",
            "diffusiongemma",
            "-d",
            *st.session_state.get("dg_datasets", ["mbpp", "gsm8k", "structeval_t"]),
            "-v",
            *st.session_state.get(
                "dg_variants", ["official", "SC2", "SC05", "SC0", "EB05", "Lg2", "Lg05"]
            ),
            "--scope",
            "comparison",
            "--figure",
            "forward",
            "--no-report",
        ]
    model = st.session_state.get("trace_model", "diffusiongemma")
    variant = st.session_state.get("trace_variant", "official")
    dataset = st.session_state.get("trace_dataset", "sudoku9_1shot_l128")
    sample_id = st.session_state.get("trace_sample")
    return [
        *command,
        "--matrix",
        str(MATRIX),
        "-m",
        model,
        *dataset_arguments(dataset),
        "-v",
        variant,
        "--scope",
        "sample",
        "--sample-ids",
        sample_id or "",
        "--no-report",
    ]


def launch(command: list[str]) -> None:
    state_dir = Path(__file__).resolve().parents[1] / ".platform_state"
    state_dir.mkdir(exist_ok=True)
    log_path = state_dir / "visualization.log"
    handle = log_path.open("w", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    handle.close()
    st.session_state["visualization_process"] = process
    st.session_state["visualization_log"] = str(log_path)
    st.session_state["visualization_command"] = command


def show_process() -> None:
    process = st.session_state.get("visualization_process")
    log_path = Path(st.session_state.get("visualization_log", ""))
    if process is None:
        return
    return_code = process.poll()
    if return_code is None:
        st.info("Visualization is running. Refresh this panel to update the log.")
    elif return_code == 0:
        st.success("Visualization finished. The new files are available in the library.")
    else:
        st.error(f"Visualization stopped with exit code {return_code}.")
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        st.code("\n".join(lines[-80:]) or "Waiting for output...", language="text")
    if st.button("Refresh status", key="refresh_visualization"):
        st.rerun()


def media_files() -> list[Path]:
    values = []
    for root in (VISUALS, PAPER):
        if root.exists():
            values.extend(
                path for path in root.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}
            )
    return sorted(values, key=lambda path: path.stat().st_mtime, reverse=True)


def trashed_media_files(
    entries: list[dict[str, str]],
) -> list[tuple[dict[str, str], Path, Path]]:
    values: list[tuple[dict[str, str], Path, Path]] = []
    for entry in entries:
        payload = OUTPUT / ".trash" / entry["id"] / "payload"
        original = OUTPUT / entry["original_relative_path"]
        if payload.is_file():
            candidates = [payload]
        elif payload.is_dir():
            candidates = [path for path in payload.rglob("*") if path.is_file()]
        else:
            continue
        for path in candidates:
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif"}:
                continue
            original_path = original
            if payload.is_dir():
                original_path = original / path.relative_to(payload)
            values.append((entry, path, original_path))
    return values


def asset_task(path: Path) -> str:
    if path.is_relative_to(PAPER):
        return "报告"
    relative = path.relative_to(VISUALS).as_posix().lower()
    if "profiling" in relative:
        return "Profiling"
    if "sudoku" in relative or "trace" in relative or path.suffix.lower() == ".gif":
        return "Trace"
    return "Full Matrix"


def asset_dimensions(path: Path) -> tuple[str, str, str]:
    """Map every public or model visual into model / variant / dataset filters."""
    if path.is_relative_to(PAPER):
        return "Report", "paper_assets", "overview"
    parts = path.relative_to(VISUALS).parts
    if not parts:
        return "Other", "other", "other"
    if parts[0] == "profiling_comparison":
        filename = path.stem
        dataset = next(
            (
                name
                for name in ("mbpp", "gsm8k", "structeval_t")
                if filename.endswith(f"_{name}")
            ),
            "all datasets",
        )
        return "跨模型汇总", "comparison", dataset
    model = parts[0]
    variant = parts[1] if len(parts) > 1 else "overview"
    if variant == "model_comparison":
        dataset = parts[2] if len(parts) > 3 else "all datasets"
    else:
        dataset = parts[2] if len(parts) > 2 else "overview"
    return model, variant, dataset


def render_media(path: Path) -> None:
    zoomable_image(path, caption=path.name)


@st.dialog("Move to Recycle Bin")
def confirm_move_asset(path: Path) -> None:
    st.warning(f"Move {path.name} to the Recycle Bin?")
    cancel_column, confirm_column = st.columns(2)
    with cancel_column:
        if st.button("Cancel", use_container_width=True, key="cancel_move_asset"):
            st.rerun()
    with confirm_column:
        if st.button(
            "Confirm",
            type="primary",
            use_container_width=True,
            key="confirm_move_asset",
        ):
            move_output_paths_to_trash(OUTPUT, [path])
            st.rerun()


@st.dialog("Move all to Recycle Bin")
def confirm_move_all_assets() -> None:
    files = media_files()
    st.warning(
        f"Move all {len(files)} generated charts and GIFs to the Recycle Bin? "
        "Model outputs, scores, and profiling JSON are kept."
    )
    cancel_column, confirm_column = st.columns(2)
    with cancel_column:
        if st.button("Cancel", use_container_width=True, key="cancel_move_all_assets"):
            st.rerun()
    with confirm_column:
        if st.button(
            "Confirm",
            type="primary",
            use_container_width=True,
            key="confirm_move_all_assets",
            disabled=not files,
        ):
            move_output_paths_to_trash(OUTPUT, files)
            st.rerun()


@st.dialog("Permanently delete item")
def confirm_delete_trash_entry(entry: dict[str, str]) -> None:
    st.warning(
        f"Permanently delete {entry['original_relative_path']}? "
        "This item cannot be restored."
    )
    cancel_column, confirm_column = st.columns(2)
    with cancel_column:
        if st.button("Cancel", use_container_width=True, key="cancel_delete_trash_entry"):
            st.rerun()
    with confirm_column:
        if st.button(
            "Confirm",
            type="primary",
            use_container_width=True,
            key="confirm_delete_trash_entry",
        ):
            empty_trash(OUTPUT, [entry["id"]])
            st.rerun()


@st.dialog("Clear Recycle Bin")
def confirm_empty_chart_trash(entries: list[dict[str, str]]) -> None:
    st.warning(
        f"Permanently delete all {len(entries)} items in the Recycle Bin? "
        "This cannot be undone."
    )
    cancel_column, confirm_column = st.columns(2)
    with cancel_column:
        if st.button("Cancel", use_container_width=True, key="cancel_empty_chart_trash"):
            st.rerun()
    with confirm_column:
        if st.button(
            "Confirm",
            type="primary",
            use_container_width=True,
            key="confirm_empty_chart_trash",
            disabled=not entries,
        ):
            empty_trash(OUTPUT, [entry["id"] for entry in entries])
            st.rerun()


st.title("Charts")

generate_tab, library_tab, trash_tab = st.tabs(
    ["Generate", "Library", "Recycle Bin"]
)

with generate_tab:
    descriptions = {
        "Sudoku sample trace": "Render one curated Sudoku trajectory as an accept trace and animation.",
        "DiffusionGemma forward comparison": "Compare forward-pass efficiency across selected DG variants and datasets.",
        "Profiling comparison": "Compare measured step cost and stage composition across model implementations.",
        "Report overview": "Rebuild the two compact P1/P2/P4/P8 figures used by the results report.",
    }
    with st.container(border=True):
        st.markdown('<div class="viz-kicker">Figure builder</div>', unsafe_allow_html=True)
        preset = st.selectbox(
            "Visualization",
            [
                "Sudoku sample trace",
                "DiffusionGemma forward comparison",
                "Profiling comparison",
                "Report overview",
            ],
        )
        st.markdown(
            f'<div class="viz-note">{descriptions[preset]}</div>',
            unsafe_allow_html=True,
        )
        if preset == "Profiling comparison":
            available = dirs(OUTPUT / "model_profiling")
            defaults = [name for name in ["illada", "illada_vargen", "dreamreasoner", "diffusiongemma"] if name in available]
            model_column, dataset_column = st.columns(2)
            with model_column:
                st.multiselect("Models", available, default=defaults, key="profiling_models")
            with dataset_column:
                st.multiselect(
                    "Datasets",
                    ["mbpp", "gsm8k", "structeval_t"],
                    default=["mbpp", "gsm8k", "structeval_t"],
                    key="profiling_datasets",
                )
        elif preset == "DiffusionGemma forward comparison":
            available_variants = dirs(OUTPUT / "model_output" / "diffusiongemma")
            default_variants = [name for name in ["official", "SC2", "SC05", "SC0", "EB05", "Lg2", "Lg05"] if name in available_variants]
            variant_column, dataset_column = st.columns(2)
            with variant_column:
                st.multiselect("Variants", available_variants, default=default_variants, key="dg_variants")
            with dataset_column:
                st.multiselect(
                    "Datasets",
                    ["mbpp", "gsm8k", "structeval_t", "sudoku4", "sudoku9"],
                    default=["mbpp", "gsm8k", "structeval_t"],
                    key="dg_datasets",
                )
        elif preset == "Sudoku sample trace":
            model_options = [name for name in dirs(OUTPUT / "model_output") if any(part.startswith("sudoku") for variant in dirs(OUTPUT / "model_output" / name) for part in datasets(name, variant))]
            model_column, variant_column = st.columns(2)
            with model_column:
                model = st.selectbox("Model", model_options, index=model_options.index("diffusiongemma") if "diffusiongemma" in model_options else 0, key="trace_model")
            variant_options = [name for name in dirs(OUTPUT / "model_output" / model) if any(part.startswith("sudoku") for part in datasets(model, name))]
            with variant_column:
                variant = st.selectbox(
                    "Variant",
                    variant_options,
                    index=variant_options.index("official") if "official" in variant_options else 0,
                    key="trace_variant",
                )
            dataset_options = [name for name in datasets(model, variant) if name.startswith("sudoku")]
            preferred = "sudoku9_1shot_l128"
            dataset_column, sample_column = st.columns(2)
            with dataset_column:
                dataset = st.selectbox("Dataset", dataset_options, index=dataset_options.index(preferred) if preferred in dataset_options else 0, key="trace_dataset")
            sample_options = samples(model, variant, dataset)
            preferred_sample = "sudoku-test-0758"
            with sample_column:
                st.selectbox("Sample", sample_options, index=sample_options.index(preferred_sample) if preferred_sample in sample_options else 0, key="trace_sample")
        else:
            score_models = dirs(OUTPUT / "score_output")
            report_defaults = [name for name in ["dreamreasoner", "illada_vargen"] if name in score_models]
            model_column, dataset_column = st.columns(2)
            with model_column:
                st.multiselect("Models", score_models, default=report_defaults, key="report_models")
            with dataset_column:
                st.multiselect(
                    "Datasets",
                    ["mbpp", "gsm8k", "structeval_t"],
                    default=["mbpp", "gsm8k", "structeval_t"],
                    key="report_datasets",
                )

    command = command_for(preset)
    active = st.session_state.get("visualization_process")
    is_running = active is not None and active.poll() is None
    action_column, detail_column = st.columns([1, 2.4], vertical_alignment="center")
    with action_column:
        if st.button(
            "Generate visualization",
            type="primary",
            disabled=is_running or "" in command,
            use_container_width=True,
            key="generate_visualization",
        ):
            launch(command)
            st.rerun()
    with detail_column:
        st.caption("Uses saved model outputs; no model weights are loaded.")
    with st.expander("Command and workspace", expanded=False):
        st.caption(f"Benchmark root: {ROOT}")
        st.code(subprocess.list2cmdline(command), language="text", wrap_lines=True)
    show_process()

with library_tab:
    files = media_files()
    left, right = st.columns([1, 3])
    with left:
        st.metric("Generated files", len(files))
    with right:
        if st.button(
            "Move all to Recycle Bin",
            use_container_width=True,
            key="clear_visualizations",
            disabled=not files,
        ):
            confirm_move_all_assets()
    if not files:
        st.info("No visualizations yet. Choose a target in Generate.")
    else:
        catalog = [(path, asset_task(path), *asset_dimensions(path)) for path in files]
        task_options = sorted({task for _, task, _, _, _ in catalog})
        task_column, model_column, variant_column, dataset_column = st.columns(4)
        with task_column:
            selected_task = st.selectbox(
                "任务",
                ["全部任务", *task_options],
                key="library_task",
            )
        model_options = sorted(
            {
                model
                for _, task, model, _, _ in catalog
                if selected_task == "全部任务" or task == selected_task
            }
        )
        with model_column:
            selected_model = st.selectbox(
                "模型",
                ["全部模型", *model_options],
                key="library_model",
            )
        visible_variants = sorted(
            {
                variant
                for _, task, model, variant, _ in catalog
                if (selected_task == "全部任务" or task == selected_task)
                and (selected_model == "全部模型" or model == selected_model)
            }
        )
        with variant_column:
            selected_variant = st.selectbox(
                "变体",
                ["全部变体", *visible_variants],
                key="library_variant",
            )
        visible_datasets = sorted(
            {
                dataset
                for _, task, model, variant, dataset in catalog
                if (selected_task == "全部任务" or task == selected_task)
                and (selected_model == "全部模型" or model == selected_model)
                and (
                    selected_variant == "全部变体"
                    or variant == selected_variant
                )
            }
        )
        with dataset_column:
            selected_dataset = st.selectbox(
                "数据集",
                ["全部数据集", *visible_datasets],
                key="library_dataset",
            )
        kinds = sorted({path.suffix.lower().lstrip(".") for path in files})
        type_column, search_column = st.columns([1, 2])
        with type_column:
            selected_kinds = st.multiselect("File type", kinds, default=kinds)
        with search_column:
            query = st.text_input(
                "Search",
                placeholder="Sample ID or filename",
            ).strip().lower()
        filtered = [
            path for path, task, model, variant, dataset in catalog
            if (selected_task == "全部任务" or task == selected_task)
            and (selected_model == "全部模型" or model == selected_model)
            and (selected_variant == "全部变体" or variant == selected_variant)
            and (selected_dataset == "全部数据集" or dataset == selected_dataset)
            if path.suffix.lower().lstrip(".") in selected_kinds
            and (not query or query in str(path.relative_to(OUTPUT)).lower())
        ]
        if len(filtered) > 1:
            limit = st.slider("Files shown", 1, len(filtered), min(12, len(filtered)))
        else:
            limit = len(filtered)
        for path in filtered[:limit]:
            relative = path.relative_to(OUTPUT)
            model, variant, dataset = asset_dimensions(path)
            label = f"{model} · {variant} · {dataset} · {path.name}"
            with st.expander(label, expanded=limit <= 3):
                st.markdown(f'<div class="viz-path">{relative}</div>', unsafe_allow_html=True)
                render_media(path)
                if st.button(
                    "Move to Recycle Bin",
                    icon=":material/delete:",
                    key=f"delete_{relative}",
                ):
                    confirm_move_asset(path)

with trash_tab:
    trash_entries = list_trash_entries(
        OUTPUT,
        prefixes=("visualization_output", "report/paper_assets"),
    )
    trash_assets = trashed_media_files(trash_entries)
    count_column, action_column = st.columns([3, 1], vertical_alignment="center")
    with count_column:
        st.metric("Items", len(trash_entries))
        st.caption(f"{len(trash_assets)} chart and GIF files can be previewed.")
    with action_column:
        if st.button(
            "Clear all",
            use_container_width=True,
            type="primary",
            key="open_empty_chart_trash",
            disabled=not trash_entries,
        ):
            confirm_empty_chart_trash(trash_entries)

    if not trash_entries:
        st.info("Recycle Bin is empty.")
    else:
        trash_catalog = [
            (entry, payload, original, asset_task(original), *asset_dimensions(original))
            for entry, payload, original in trash_assets
        ]
        task_options = sorted({task for _, _, _, task, _, _, _ in trash_catalog})
        task_column, model_column, variant_column, dataset_column = st.columns(4)
        with task_column:
            selected_task = st.selectbox(
                "任务",
                ["全部任务", *task_options],
                key="trash_task",
            )
        model_options = sorted(
            {
                model
                for _, _, _, task, model, _, _ in trash_catalog
                if selected_task == "全部任务" or task == selected_task
            }
        )
        with model_column:
            selected_model = st.selectbox(
                "模型",
                ["全部模型", *model_options],
                key="trash_model",
            )
        variant_options = sorted(
            {
                variant
                for _, _, _, task, model, variant, _ in trash_catalog
                if (selected_task == "全部任务" or task == selected_task)
                and (selected_model == "全部模型" or model == selected_model)
            }
        )
        with variant_column:
            selected_variant = st.selectbox(
                "变体",
                ["全部变体", *variant_options],
                key="trash_variant",
            )
        dataset_options = sorted(
            {
                dataset
                for _, _, _, task, model, variant, dataset in trash_catalog
                if (selected_task == "全部任务" or task == selected_task)
                and (selected_model == "全部模型" or model == selected_model)
                and (selected_variant == "全部变体" or variant == selected_variant)
            }
        )
        with dataset_column:
            selected_dataset = st.selectbox(
                "数据集",
                ["全部数据集", *dataset_options],
                key="trash_dataset",
            )

        kinds = sorted({payload.suffix.lower().lstrip(".") for _, payload, _ in trash_assets})
        type_column, search_column = st.columns([1, 2])
        with type_column:
            selected_kinds = st.multiselect(
                "File type",
                kinds,
                default=kinds,
                key="trash_file_types",
            )
        with search_column:
            query = st.text_input(
                "Search",
                placeholder="Original path or filename",
                key="trash_search",
            ).strip().lower()
        visible_assets = [
            (entry, payload, original)
            for entry, payload, original, task, model, variant, dataset in trash_catalog
            if (selected_task == "全部任务" or task == selected_task)
            and (selected_model == "全部模型" or model == selected_model)
            and (selected_variant == "全部变体" or variant == selected_variant)
            and (selected_dataset == "全部数据集" or dataset == selected_dataset)
            and payload.suffix.lower().lstrip(".") in selected_kinds
            and (not query or query in str(original.relative_to(OUTPUT)).lower())
        ]
        if not trash_assets:
            st.info("The recycled items do not contain previewable charts or GIFs.")
        elif not visible_assets:
            st.info("No recycled items match the current filters.")
        if len(visible_assets) > 1:
            limit = st.slider(
                "Files shown",
                1,
                len(visible_assets),
                min(12, len(visible_assets)),
                key="trash_files_shown",
            )
        else:
            limit = len(visible_assets)

        for entry, payload, original in visible_assets[:limit]:
            model, variant, dataset = asset_dimensions(original)
            label = f"{model} · {variant} · {dataset} · {original.name}"
            asset_key = f"{entry['id']}::{original.relative_to(OUTPUT).as_posix()}"
            with st.expander(
                label,
                expanded=limit <= 3,
            ):
                st.markdown(
                    f'<div class="viz-path">{original.relative_to(OUTPUT)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"Deleted: {entry['deleted_at']}")
                render_media(payload)
                restore_column, delete_column = st.columns(2)
                with restore_column:
                    if st.button(
                        "Restore",
                        key=f"restore_chart_{asset_key}",
                        use_container_width=True,
                    ):
                        try:
                            restored = restore_trash_entry(OUTPUT, entry["id"])
                        except FileExistsError:
                            st.error("A file already exists at the original path. It was not overwritten.")
                        else:
                            st.success(f"Restored: {restored.relative_to(OUTPUT)}")
                            st.rerun()
                with delete_column:
                    if st.button(
                        "Delete permanently",
                        key=f"purge_chart_{asset_key}",
                        use_container_width=True,
                    ):
                        confirm_delete_trash_entry(entry)
