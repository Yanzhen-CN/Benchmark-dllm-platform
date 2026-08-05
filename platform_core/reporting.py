from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .paths import PlatformPaths


@dataclass(frozen=True)
class MarkdownSection:
    number: str
    title: str
    body: str


@dataclass(frozen=True)
class VisualAsset:
    category: str
    model: str
    dataset: str
    name: str
    path: Path


def locate_document(paths: PlatformPaths, kind: str) -> Path | None:
    env_name = "DLLM_BENCH_REPORT" if kind == "results" else "DLLM_BENCH_DESIGN"
    filename = (
        "dLLM_benchmark_测试结果.md"
        if kind == "results"
        else "dLLM_benchmark_设计文档.md"
    )
    candidates = [
        Path(os.environ[env_name]).expanduser()
        if os.environ.get(env_name)
        else None,
        paths.platform_root / "docs" / filename,
        paths.benchmark_root.parents[2] / filename,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    return None


def read_markdown(path: Path) -> tuple[str, str, list[MarkdownSection]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = lines[0].removeprefix("# ").strip() if lines else path.stem
    matches = list(re.finditer(r"(?m)^##\s+([^\n]+)$", text))
    preface_start = text.find("\n") + 1 if "\n" in text else len(text)
    preface_end = matches[0].start() if matches else len(text)
    preface = text[preface_start:preface_end].strip()
    sections: list[MarkdownSection] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        number_match = re.match(r"(\d+(?:\.\d+)*)[.\s]*(.*)", heading)
        number = number_match.group(1) if number_match else ""
        clean_title = number_match.group(2).strip() if number_match else heading
        sections.append(MarkdownSection(number=number, title=clean_title, body=body))
    return title, preface, sections


def section_group(section: MarkdownSection) -> str:
    major = int(section.number.split(".")[0]) if section.number else 99
    if major <= 3:
        return "核心结果"
    if major <= 6:
        return "效率与消融"
    if major <= 9:
        return "Sudoku 与 Profiling"
    return "结论与附录"


def _visual_category(relative: Path) -> str:
    value = relative.as_posix().lower()
    if "profiling" in value:
        return "Profiling"
    if "sudoku" in value or "trace" in value or value.endswith(".gif"):
        return "Sudoku 与 Trace"
    if ("diffusiongemma" in value and "model_comparison" in value) or any(
        token in value for token in ("entropy", "logit", "sc_", "sc0", "sc05", "sc2", "ablation")
    ):
        return "DG 消融"
    if any(token in value for token in ("parallel", "p1248", "block", "forward")):
        return "并行度与 Forward"
    if any(token in value for token in ("energy", "power", "speed", "resource")):
        return "资源效率"
    return "其他图表"


def discover_visuals(paths: PlatformPaths) -> list[VisualAsset]:
    roots = (
        paths.output_root / "visualization_output",
        paths.output_root / "report" / "paper_assets",
    )
    assets: list[VisualAsset] = []
    for visual_root in roots:
        if not visual_root.is_dir():
            continue
        for path in sorted(visual_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".png", ".gif"}:
                continue
            relative = path.relative_to(visual_root)
            parts = relative.parts
            model = parts[0] if visual_root.name == "visualization_output" and parts else "report"
            dataset = parts[1] if visual_root.name == "visualization_output" and len(parts) > 1 else "paper_assets"
            if dataset == "model_comparison":
                dataset = parts[2] if len(parts) > 3 else "跨数据集"
            elif model == "profiling_comparison":
                model = "跨模型汇总"
                dataset = next(
                    (
                        name
                        for name in ("gsm8k", "mbpp", "structeval_t")
                        if path.stem.endswith(f"_{name}")
                    ),
                    "all datasets",
                )
            elif visual_root.name == "visualization_output" and len(parts) >= 4:
                model = f"{parts[0]}/{parts[1]}"
                dataset = parts[2]
            assets.append(
                VisualAsset(
                    category=_visual_category(relative),
                    model=model,
                    dataset=dataset,
                    name=path.name,
                    path=path,
                )
            )
    return assets
