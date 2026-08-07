# Platform operations

The platform is a lightweight controller and result browser for Benchmark-dllm.
It discovers models and datasets from the benchmark configuration, reads public
score and visualization outputs, and submits work through the benchmark's
existing runner. It never loads a model inside the Streamlit environment.

## Local network service

    python start.py

The default service listens on `0.0.0.0:8501`. This device can use
`http://127.0.0.1:8501`; another device on the same trusted Wi-Fi or Ethernet
network should use the LAN address printed by `start.py`.

## Custom host or port

Set `DLLM_PLATFORM_HOST` or `DLLM_PLATFORM_PORT` before starting the platform
to override the defaults. Do not expose this unauthenticated service directly
to the public internet.

Linux:

    DLLM_PLATFORM_HOST=0.0.0.0 DLLM_PLATFORM_PORT=8501 python start.py

PowerShell:

    $env:DLLM_PLATFORM_HOST = "0.0.0.0"
    $env:DLLM_PLATFORM_PORT = "8501"
    python start.py


## Execution boundary

Dry-run works without model environments. A real run is enabled only when the
selected model launcher and .venvs/<model> Python executable both exist.
Environment setup remains owned by Benchmark-dllm's setup_venv.py.

## Result boundary

Score pages read score_output. Performance pages read the same score summaries
and expose TPS-first profiling figures from visualization_output. Trace pages
remain dedicated to token acceptance, revision, and sample-level generation
artifacts.
