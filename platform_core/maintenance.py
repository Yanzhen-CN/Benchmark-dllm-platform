from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .paths import PlatformPaths


OUTPUT_STAGES = (
    "model_output",
    "score_output",
    "visualization_output",
    "model_profiling",
)
TRASH_DIRNAME = ".trash"


def output_stages(paths: PlatformPaths) -> list[str]:
    return [name for name in OUTPUT_STAGES if (paths.output_root / name).is_dir()]


def output_runs(paths: PlatformPaths, stage: str) -> list[str]:
    root = _stage_root(paths, stage)
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def output_children(paths: PlatformPaths, stage: str, run: str) -> list[str]:
    root = _target(paths, stage, run)
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def output_target(
    paths: PlatformPaths,
    stage: str,
    run: str,
    child: str | None = None,
) -> Path:
    parts = (run,) if child is None else (run, child)
    return _target(paths, stage, *parts)


def count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.is_dir() else 0


def delete_output_target(
    paths: PlatformPaths,
    stage: str,
    run: str,
    child: str | None = None,
) -> Path:
    parts = (run,) if child is None else (run, child)
    target = _target(paths, stage, *parts)
    move_output_paths_to_trash(paths.output_root, [target])
    return target


def delete_output_files(paths: PlatformPaths, files: list[Path]) -> int:
    output_root = paths.output_root.resolve()
    parents: set[Path] = set()
    for path in files:
        target = path.resolve()
        if output_root not in target.parents or not target.is_file():
            continue
        parents.add(target.parent)
    removed = move_output_paths_to_trash(output_root, files)
    for parent in sorted(parents, key=lambda item: len(item.parts), reverse=True):
        current = parent
        while current != output_root and output_root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
    return removed


def clear_all_outputs(paths: PlatformPaths) -> int:
    targets = [paths.output_root / stage for stage in OUTPUT_STAGES]
    return move_output_paths_to_trash(paths.output_root, targets)


def move_output_paths_to_trash(output_root: Path, targets: list[Path]) -> int:
    """Move output files or directories into a recoverable, path-aware trash store."""
    root = output_root.resolve()
    trash_root = root / TRASH_DIRNAME
    moved = 0
    seen: set[Path] = set()
    for candidate in targets:
        target = candidate.resolve()
        if target in seen or not target.exists() or root not in target.parents:
            continue
        seen.add(target)
        relative = target.relative_to(root)
        entry_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        entry_dir = trash_root / entry_id
        entry_dir.mkdir(parents=True, exist_ok=False)
        payload = entry_dir / (
            f"payload{target.suffix.lower()}" if target.is_file() else "payload"
        )
        manifest = {
            "id": entry_id,
            "original_relative_path": relative.as_posix(),
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "kind": "directory" if target.is_dir() else "file",
            "payload_name": payload.name,
        }
        try:
            shutil.move(str(target), str(payload))
            (entry_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            if payload.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(payload), str(target))
            shutil.rmtree(entry_dir, ignore_errors=True)
            raise
        moved += 1
    return moved


def permanently_delete_output_paths(output_root: Path, targets: list[Path]) -> int:
    """Permanently remove selected paths while keeping deletion inside output_root."""
    root = output_root.resolve()
    removed = 0
    parents: set[Path] = set()
    seen: set[Path] = set()
    for candidate in targets:
        target = candidate.resolve()
        if target in seen or target == root or root not in target.parents:
            continue
        seen.add(target)
        if not target.exists():
            continue
        parents.add(target.parent)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed += 1
    for parent in sorted(parents, key=lambda item: len(item.parts), reverse=True):
        current = parent
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
    return removed


def list_trash_entries(
    output_root: Path,
    *,
    prefixes: tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    root = output_root.resolve()
    trash_root = root / TRASH_DIRNAME
    entries: list[dict[str, str]] = []
    if not trash_root.is_dir():
        return entries
    for entry_dir in trash_root.iterdir():
        manifest_path = entry_dir / "manifest.json"
        if not entry_dir.is_dir() or not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        payload = _trash_payload(entry_dir, manifest)
        if not payload.exists():
            continue
        relative = str(manifest.get("original_relative_path", ""))
        if prefixes and not any(
            relative == prefix or relative.startswith(f"{prefix}/")
            for prefix in prefixes
        ):
            continue
        entries.append(
            {
                "id": str(manifest.get("id", entry_dir.name)),
                "original_relative_path": relative,
                "deleted_at": str(manifest.get("deleted_at", "")),
                "kind": str(manifest.get("kind", "file")),
                "payload_name": payload.name,
            }
        )
    return sorted(entries, key=lambda item: item["deleted_at"], reverse=True)


def restore_trash_entry(output_root: Path, entry_id: str) -> Path:
    root = output_root.resolve()
    trash_root = (root / TRASH_DIRNAME).resolve()
    entry_dir = (trash_root / entry_id).resolve()
    if trash_root not in entry_dir.parents:
        raise ValueError("Trash entry must stay inside the recycle bin.")
    manifest_path = entry_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = _trash_payload(entry_dir, manifest)
    target = (root / str(manifest["original_relative_path"])).resolve()
    if root not in target.parents:
        raise ValueError("Restore target must stay inside the output directory.")
    if target.exists():
        raise FileExistsError(f"Restore target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(payload), str(target))
    shutil.rmtree(entry_dir)
    try:
        trash_root.rmdir()
    except OSError:
        pass
    return target


def empty_trash(output_root: Path, entry_ids: list[str] | None = None) -> int:
    entries = list_trash_entries(output_root)
    trash_root = output_root.resolve() / TRASH_DIRNAME
    if entry_ids is None and trash_root.is_dir():
        shutil.rmtree(trash_root)
        return len(entries)
    allowed = set(entry_ids or [])
    removed = 0
    for entry in entries:
        if entry["id"] not in allowed:
            continue
        entry_dir = (trash_root / entry["id"]).resolve()
        if trash_root.resolve() in entry_dir.parents and entry_dir.is_dir():
            shutil.rmtree(entry_dir)
            removed += 1
    try:
        trash_root.rmdir()
    except OSError:
        pass
    return removed


def clear_run_history(paths: PlatformPaths) -> int:
    if not paths.state_dir.is_dir():
        return 0
    removed = 0
    for path in paths.state_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {".json", ".log"}:
            path.unlink()
            removed += 1
    return removed


def _stage_root(paths: PlatformPaths, stage: str) -> Path:
    if stage not in OUTPUT_STAGES:
        raise ValueError(f"Unsupported output stage: {stage}")
    return (paths.output_root / stage).resolve()


def _trash_payload(entry_dir: Path, manifest: dict | None = None) -> Path:
    payload_name = str((manifest or {}).get("payload_name") or "payload")
    preferred = entry_dir / payload_name
    if preferred.exists():
        return preferred
    candidates = sorted(entry_dir.glob("payload*"))
    return candidates[0] if candidates else preferred


def _target(paths: PlatformPaths, stage: str, *parts: str) -> Path:
    root = _stage_root(paths, stage)
    target = root.joinpath(*parts).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Output target must stay inside a stage directory.")
    return target
