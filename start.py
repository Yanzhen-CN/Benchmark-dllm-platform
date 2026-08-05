from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = (
    VENV / "Scripts" / "python.exe"
    if os.name == "nt"
    else VENV / "bin" / "python"
)
STATE_DIR = ROOT / ".state"
PID_FILE = STATE_DIR / "platform.pid"


def _run(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def ensure_platform_runtime() -> None:
    if not VENV_PYTHON.is_file():
        print("Initializing the lightweight platform environment...")
        _run([sys.executable, "-m", "venv", str(VENV)])

    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import streamlit, yaml, plotly"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if check.returncode != 0:
        print("Installing platform UI dependencies...")
        _run(
            [
                str(VENV_PYTHON),
                "-m",
                "pip",
                "install",
                "streamlit>=1.40",
                "PyYAML>=6.0",
                "plotly>=6.0",
            ]
        )


def stop_previous_platform() -> None:
    try:
        previous_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    if previous_pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(previous_pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        try:
            os.killpg(previous_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    PID_FILE.unlink(missing_ok=True)


def remember_platform(pid: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{pid}\n", encoding="utf-8")


def forget_platform(pid: int) -> None:
    try:
        recorded_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    if recorded_pid == pid:
        PID_FILE.unlink(missing_ok=True)


def main() -> int:
    stop_previous_platform()
    ensure_platform_runtime()
    host = os.environ.get("DLLM_PLATFORM_HOST", "127.0.0.1")
    port = os.environ.get("DLLM_PLATFORM_PORT", "8501")
    command = [
        str(VENV_PYTHON),
        "-m",
        "streamlit",
        "run",
        str(ROOT / "app.py"),
        f"--server.address={host}",
        f"--server.port={port}",
        *sys.argv[1:],
    ]
    display_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
    print(f"Benchmark-dllm Platform: http://{display_host}:{port}")
    if host == "0.0.0.0":
        print("Remote mode enabled; protect this port with your server firewall or proxy authentication.")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        start_new_session=os.name != "nt",
    )
    remember_platform(process.pid)
    try:
        return process.wait()
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
        return 130
    finally:
        forget_platform(process.pid)


if __name__ == "__main__":
    raise SystemExit(main())
