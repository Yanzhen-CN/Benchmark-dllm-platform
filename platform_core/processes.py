from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import PlatformPaths


def start_run(paths: PlatformPaths, command: list[str]) -> dict[str, Any]:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = paths.state_dir / f"{run_id}.log"
    metadata_path = paths.state_dir / f"{run_id}.json"
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=paths.benchmark_root,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
    metadata = {
        "run_id": run_id,
        "pid": process.pid,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "log_path": str(log_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def recent_runs(paths: PlatformPaths, limit: int = 12) -> list[dict[str, Any]]:
    if not paths.state_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for metadata_path in sorted(paths.state_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            records.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def read_log(record: dict[str, Any], max_chars: int = 12000) -> str:
    path = Path(str(record.get("log_path", "")))
    if not path.is_file():
        return "Log file is not available."
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]

