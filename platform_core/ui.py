from __future__ import annotations

import base64
import hashlib
import html
import os
import subprocess
from pathlib import Path

import streamlit as st

from .paths import PLATFORM_ROOT, PlatformPaths
from .i18n import tr


def configure_page(title: str, icon: str = "▦") -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.iframe(
        """
        <script>
        (() => {
          const host = window.parent;
          const copyMarker = "__benchmarkCopyShortcutGuardV2";
          if (!host[copyMarker]) {
            const guardCopyShortcut = (event) => {
              const isCopy = (event.ctrlKey || event.metaKey)
                && String(event.key).toLowerCase() === "c";
              if (isCopy) event.stopImmediatePropagation();
            };
            ["keydown", "keypress", "keyup"].forEach((eventName) => {
              host.addEventListener(eventName, guardCopyShortcut, true);
            });
            host[copyMarker] = true;
          }

          const plotlyToolsMarker = "__benchmarkPlotlyToolsV2";
          if (!host[plotlyToolsMarker]) {
            const installButtons = () => {
              host.document.querySelectorAll(".js-plotly-plot").forEach((plot) => {
                const modebar = plot.querySelector(".modebar");
                if (!modebar) return;
                const buttonGroup = modebar.querySelector(".modebar-group") || modebar;
                const nativeDownload = Array.from(
                  modebar.querySelectorAll(".modebar-btn")
                ).find((button) => {
                  const title = String(button.getAttribute("data-title") || "").toLowerCase();
                  const action = String(button.getAttribute("data-attr") || "").toLowerCase();
                  return action === "download" || title.includes("download plot");
                });
                if (nativeDownload && !nativeDownload.classList.contains("benchmark-download-png")) {
                  nativeDownload.classList.add("benchmark-download-png");
                  nativeDownload.setAttribute("data-title", "下载 PNG");
                  nativeDownload.setAttribute("aria-label", "下载 PNG");
                  nativeDownload.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 19h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
                }
                if (!modebar.querySelector(".benchmark-fullscreen")) {
                  const button = host.document.createElement("a");
                  button.className = "modebar-btn benchmark-fullscreen";
                  button.setAttribute("data-title", "全屏查看");
                  button.setAttribute("role", "button");
                  button.setAttribute("aria-label", "全屏查看");
                  button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
                  button.addEventListener("click", async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const container = plot.closest('[data-testid="stPlotlyChart"]') || plot;
                    try {
                      await container.requestFullscreen();
                      setTimeout(() => host.dispatchEvent(new Event("resize")), 80);
                    } catch (error) {
                      console.warn("Plotly fullscreen failed", error);
                    }
                  });
                  buttonGroup.appendChild(button);
                }
                if (!modebar.querySelector(".benchmark-copy-png")) {
                  const copyButton = host.document.createElement("a");
                  copyButton.className = "modebar-btn benchmark-copy-png";
                  copyButton.setAttribute("data-title", "下载 PNG");
                  copyButton.setAttribute("role", "button");
                  copyButton.setAttribute("aria-label", "下载 PNG");
                  copyButton.innerHTML = '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
                  copyButton.setAttribute("data-title", "复制 PNG");
                  copyButton.setAttribute("aria-label", "复制 PNG");
                  copyButton.addEventListener("click", async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    try {
                      const plotly = host.Plotly || window.Plotly;
                      let pngBlob;
                      if (plotly && typeof plotly.toImage === "function") {
                        const dataUrl = await plotly.toImage(plot, {
                          format: "png",
                          scale: 2,
                          width: Math.max(1, Math.round(plot.clientWidth)),
                          height: Math.max(1, Math.round(plot.clientHeight))
                        });
                        pngBlob = await fetch(dataUrl).then((response) => response.blob());
                      } else {
                        const svg = plot.querySelector(".svg-container > .main-svg")
                          || plot.querySelector(".main-svg");
                        if (!svg) throw new Error("plot image unavailable");
                        const rect = svg.getBoundingClientRect();
                        const clone = svg.cloneNode(true);
                        clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
                        clone.setAttribute("width", String(rect.width));
                        clone.setAttribute("height", String(rect.height));
                        const source = new XMLSerializer().serializeToString(clone);
                        const sourceUrl = URL.createObjectURL(
                          new Blob([source], {type: "image/svg+xml;charset=utf-8"})
                        );
                        const image = new Image();
                        image.src = sourceUrl;
                        await image.decode();
                        const canvas = host.document.createElement("canvas");
                        canvas.width = Math.max(1, Math.round(rect.width * 2));
                        canvas.height = Math.max(1, Math.round(rect.height * 2));
                        const context = canvas.getContext("2d");
                        context.scale(2, 2);
                        context.fillStyle = "#ffffff";
                        context.fillRect(0, 0, rect.width, rect.height);
                        context.drawImage(image, 0, 0, rect.width, rect.height);
                        URL.revokeObjectURL(sourceUrl);
                        pngBlob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
                      }
                      if (!pngBlob) throw new Error("PNG conversion failed");
                      await host.navigator.clipboard.write([
                        new host.ClipboardItem({"image/png": pngBlob})
                      ]);
                    } catch (error) {
                      console.warn("Plotly PNG copy failed", error);
                    }
                  });
                  buttonGroup.appendChild(copyButton);
                }
              });
            };
            const observer = new MutationObserver(installButtons);
            observer.observe(host.document.body, {childList: true, subtree: true});
            host.document.addEventListener("fullscreenchange", () => {
              setTimeout(() => host.dispatchEvent(new Event("resize")), 80);
            });
            installButtons();
            host[plotlyToolsMarker] = true;
          }

          const vegaToolsMarker = "__benchmarkVegaToolsV2";
          if (!host[vegaToolsMarker]) {
            const pngBlob = async (container) => {
              const canvas = container.querySelector("canvas");
              if (canvas) {
                return await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
              }
              const svg = container.querySelector("svg");
              if (!svg) throw new Error("chart image unavailable");
              const rect = svg.getBoundingClientRect();
              const clone = svg.cloneNode(true);
              clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
              clone.setAttribute("width", String(rect.width));
              clone.setAttribute("height", String(rect.height));
              const sourceUrl = URL.createObjectURL(new Blob(
                [new XMLSerializer().serializeToString(clone)],
                {type: "image/svg+xml;charset=utf-8"}
              ));
              const image = new Image();
              image.src = sourceUrl;
              await image.decode();
              const output = host.document.createElement("canvas");
              output.width = Math.max(1, Math.round(rect.width * 2));
              output.height = Math.max(1, Math.round(rect.height * 2));
              const context = output.getContext("2d");
              context.scale(2, 2);
              context.fillStyle = "#ffffff";
              context.fillRect(0, 0, rect.width, rect.height);
              context.drawImage(image, 0, 0, rect.width, rect.height);
              URL.revokeObjectURL(sourceUrl);
              return await new Promise((resolve) => output.toBlob(resolve, "image/png"));
            };
            const iconButton = (title, icon) => {
              const button = host.document.createElement("button");
              button.type = "button";
              button.title = title;
              button.setAttribute("aria-label", title);
              button.className = "benchmark-vega-button";
              button.innerHTML = icon;
              return button;
            };
            const installVegaButtons = () => {
              host.document.querySelectorAll('[data-testid="stVegaLiteChart"]').forEach((container) => {
                const frame = container.closest('[data-testid="stFullScreenFrame"]');
                if (frame) {
                  frame.querySelectorAll('button[data-testid="stBaseButton-elementToolbar"]').forEach((button) => {
                    button.style.display = "none";
                    button.setAttribute("aria-hidden", "true");
                    button.tabIndex = -1;
                  });
                }
                if (container.querySelector(".benchmark-vega-tools")) return;
                container.style.position = "relative";
                const tools = host.document.createElement("div");
                tools.className = "benchmark-vega-tools";
                const fullscreen = iconButton(
                  "全屏查看",
                  '<svg viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>'
                );
                fullscreen.onclick = async () => {
                  try { await container.requestFullscreen(); } catch (error) {
                    console.warn("Chart fullscreen failed", error);
                  }
                };
                const copy = iconButton(
                  "复制 PNG",
                  '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>'
                );
                copy.onclick = async () => {
                  try {
                    const blob = await pngBlob(container);
                    if (!blob) throw new Error("PNG conversion failed");
                    await host.navigator.clipboard.write([
                      new host.ClipboardItem({"image/png": blob})
                    ]);
                  } catch (error) {
                    console.warn("Chart PNG copy failed", error);
                  }
                };
                const download = iconButton(
                  "下载 PNG",
                  '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 19h16"/></svg>'
                );
                download.onclick = async () => {
                  try {
                    const blob = await pngBlob(container);
                    if (!blob) throw new Error("PNG conversion failed");
                    const url = URL.createObjectURL(blob);
                    const anchor = host.document.createElement("a");
                    anchor.href = url;
                    anchor.download = "benchmark-chart.png";
                    anchor.click();
                    URL.revokeObjectURL(url);
                  } catch (error) {
                    console.warn("Chart PNG download failed", error);
                  }
                };
                tools.append(fullscreen, copy, download);
                container.appendChild(tools);
              });
            };
            const observer = new MutationObserver(installVegaButtons);
            observer.observe(host.document.body, {childList: true, subtree: true});
            installVegaButtons();
            host[vegaToolsMarker] = true;
          }
        })();
        </script>
        """,
        height=1,
        width=1,
    )
    st.markdown(
        """
        <style>
        h1, h2, h3 { font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.02em; }
        [data-testid="stMetric"] { background: #fffaf0; border: 1px solid #cddbd3; padding: 0.8rem; }
        .platform-note { border-left: 4px solid #d97706; padding: .65rem 1rem; background: #fff7e6; }
        [class*="st-key-danger_"] button {
            background: #b42318 !important;
            border-color: #8f1d14 !important;
            color: #fff !important;
        }
        [class*="st-key-danger_"] button:hover {
            background: #8f1d14 !important;
            border-color: #741911 !important;
        }
        [class*="st-key-danger_"] button:disabled {
            background: #d7a5a1 !important;
            border-color: #d7a5a1 !important;
        }
        [data-testid="stPlotlyChart"]:fullscreen {
            width: 100vw !important;
            height: 100vh !important;
            padding: 18px;
            overflow: hidden;
            background: #ffffff;
        }
        [data-testid="stPlotlyChart"]:fullscreen .js-plotly-plot,
        [data-testid="stPlotlyChart"]:fullscreen .plot-container,
        [data-testid="stPlotlyChart"]:fullscreen .svg-container {
            width: 100% !important;
            height: 100% !important;
        }
        .benchmark-fullscreen svg {
            width: 1em;
            height: 1em;
        }
        .benchmark-vega-tools {
            position: absolute;
            top: 7px;
            right: 9px;
            z-index: 20;
            display: flex;
            gap: 3px;
            opacity: 0;
            transform: translateY(-3px);
            transition: opacity .15s ease, transform .15s ease;
        }
        [data-testid="stVegaLiteChart"]:hover .benchmark-vega-tools,
        .benchmark-vega-tools:focus-within {
            opacity: 1;
            transform: translateY(0);
        }
        .benchmark-vega-button {
            display: grid;
            place-items: center;
            width: 30px;
            height: 30px;
            padding: 0;
            border: 1px solid rgba(203, 213, 225, .9);
            border-radius: 5px;
            background: rgba(255, 255, 255, .94);
            color: #334155;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(15, 23, 42, .14);
        }
        .benchmark-vega-button svg {
            width: 16px;
            height: 16px;
            fill: none;
            stroke: currentColor;
            stroke-width: 1.8;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        [data-testid="stVegaLiteChart"]:fullscreen {
            padding: 24px;
            overflow: auto;
            background: #ffffff;
        }
        [data-testid="stDeployButton"] {
            display: none !important;
        }
        /* Streamlit components render formal images and GIFs in iframes. Keep
           every visual inside the expander's visibility boundary. */
        [data-testid="stExpander"] details:not([open]) > div,
        [data-testid="stExpander"] details:not([open]) iframe,
        [data-testid="stExpander"] details:not([open]) img,
        [data-testid="stExpander"] details:not([open]) canvas,
        [data-testid="stExpander"] details:not([open]) [data-testid="stPlotlyChart"],
        [data-testid="stExpander"] details:not([open]) [data-testid="stVegaLiteChart"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            overflow: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def paths_sidebar() -> PlatformPaths:
    defaults = PlatformPaths.from_values()
    with st.sidebar.expander(tr("工作区", "Workspace"), expanded=False):
        benchmark_key = "workspace_benchmark_root"
        output_key = "workspace_output_root"
        previous_benchmark_key = "workspace_previous_benchmark_root"
        layout_version_key = "workspace_layout_version"
        current_layout_version = "embedded-platform-v1"
        if st.session_state.get(layout_version_key) != current_layout_version:
            st.session_state[benchmark_key] = str(defaults.benchmark_root)
            st.session_state[output_key] = str(defaults.output_root)
            st.session_state[previous_benchmark_key] = str(defaults.benchmark_root)
            st.session_state[layout_version_key] = current_layout_version
        else:
            st.session_state.setdefault(benchmark_key, str(defaults.benchmark_root))
            st.session_state.setdefault(output_key, str(defaults.output_root))
            st.session_state.setdefault(
                previous_benchmark_key, st.session_state[benchmark_key]
            )

        benchmark_input, benchmark_browse = st.columns([5, 1])
        benchmark_root = benchmark_input.text_input(
            tr("Benchmark-dllm 根目录", "Benchmark-dllm root"),
            key=benchmark_key,
            on_change=_sync_output_with_benchmark,
            args=(benchmark_key, output_key, previous_benchmark_key),
        )
        with benchmark_browse:
            if os.name == "nt":
                st.button(
                    tr("选择", "Choose"),
                    key="benchmark_root_native_picker",
                    icon=":material/folder_open:",
                    width="stretch",
                    on_click=_native_directory_picker,
                    args=(
                        benchmark_key,
                        tr("选择 Benchmark-dllm 根目录", "Choose Benchmark-dllm root"),
                        output_key,
                        previous_benchmark_key,
                    ),
                )
            else:
                _directory_picker(benchmark_key, key_prefix="benchmark_root")

        output_input, output_browse = st.columns([5, 1])
        output_root = output_input.text_input(tr("输出目录", "Output root"), key=output_key)
        with output_browse:
            if os.name == "nt":
                st.button(
                    tr("选择", "Choose"),
                    key="output_root_native_picker",
                    icon=":material/folder_open:",
                    width="stretch",
                    on_click=_native_directory_picker,
                    args=(
                        output_key,
                        tr("选择输出目录", "Choose output directory"),
                    ),
                )
            else:
                _directory_picker(output_key, key_prefix="output_root")
        if st.button(tr("退出平台", "Exit platform"), width="stretch", type="secondary"):
            st.warning(tr("平台服务正在退出。", "The platform is shutting down."))
            st.iframe(
                """
                <script>
                const parentDocument = window.parent.document;
                const overlay = parentDocument.createElement("div");
                overlay.style.cssText = [
                  "position:fixed",
                  "inset:0",
                  "z-index:2147483647",
                  "display:flex",
                  "align-items:center",
                  "justify-content:center",
                  "background:#f7f4ed",
                  "color:#1f2925",
                  "font:600 18px sans-serif"
                ].join(";");
                overlay.textContent = "Platform is shutting down...";
                parentDocument.body.appendChild(overlay);
                window.setTimeout(() => window.parent.location.reload(), 2200);
                </script>
                """,
                height=1,
                width=1,
            )
            _schedule_exit()
            st.stop()
    return PlatformPaths.from_values(benchmark_root, output_root)


def _set_browser_directory(browser_key: str, path: str) -> None:
    st.session_state[browser_key] = path


def _select_browser_directory(state_key: str, browser_key: str, path: str) -> None:
    st.session_state[state_key] = path
    st.session_state[browser_key] = path


def _sync_output_with_benchmark(
    benchmark_key: str,
    output_key: str,
    previous_benchmark_key: str,
) -> None:
    new_root = Path(st.session_state.get(benchmark_key, "")).expanduser().resolve()
    previous_root = Path(
        st.session_state.get(previous_benchmark_key, new_root)
    ).expanduser().resolve()
    output = Path(st.session_state.get(output_key, previous_root / "output")).expanduser().resolve()
    if output == previous_root / "output" or output in {
        PLATFORM_ROOT.resolve(),
        (PLATFORM_ROOT / "output").resolve(),
    }:
        st.session_state[output_key] = str(new_root / "output")
    st.session_state[previous_benchmark_key] = str(new_root)


def _native_directory_picker(
    state_key: str,
    title: str,
    output_key: str | None = None,
    previous_benchmark_key: str | None = None,
) -> None:
    current = Path(st.session_state.get(state_key, Path.home())).expanduser()
    start = current if current.is_dir() else current.parent
    environment = os.environ.copy()
    environment["DLLM_FOLDER_PICKER_START"] = str(start.resolve())
    environment["DLLM_FOLDER_PICKER_TITLE"] = title
    script = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $env:DLLM_FOLDER_PICKER_TITLE
$dialog.SelectedPath = $env:DLLM_FOLDER_PICKER_START
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Write($dialog.SelectedPath)
}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )
    except OSError as exc:
        st.session_state[f"{state_key}_picker_error"] = str(exc)
        return
    selected = result.stdout.strip()
    if not selected:
        return
    st.session_state[state_key] = selected
    if output_key and previous_benchmark_key:
        _sync_output_with_benchmark(
            state_key,
            output_key,
            previous_benchmark_key,
        )


def _directory_picker(state_key: str, *, key_prefix: str) -> None:
    browser_key = f"{state_key}_browser"
    current_input = Path(st.session_state.get(state_key, "")).expanduser()
    initial = current_input if current_input.is_dir() else Path.home()
    browser_path = Path(st.session_state.get(browser_key, initial)).expanduser()
    if not browser_path.is_dir():
        browser_path = initial
    browser_path = browser_path.resolve()

    with st.popover(tr("浏览", "Browse"), width="stretch"):
        st.caption(tr("当前文件夹", "Current folder"))
        st.code(str(browser_path), language=None)
        home_column, parent_column = st.columns(2)
        home_column.button(
            tr("主页", "Home"),
            key=f"{key_prefix}_home",
            width="stretch",
            on_click=_set_browser_directory,
            args=(browser_key, str(Path.home().resolve())),
        )
        parent_column.button(
            tr("上一级", "Parent"),
            key=f"{key_prefix}_parent",
            width="stretch",
            disabled=browser_path.parent == browser_path,
            on_click=_set_browser_directory,
            args=(browser_key, str(browser_path.parent)),
        )
        try:
            child_directories = sorted(
                (path for path in browser_path.iterdir() if path.is_dir()),
                key=lambda path: path.name.lower(),
            )
        except OSError as exc:
            child_directories = []
            st.warning(f"无法读取该文件夹：{exc}")
        selected_child = st.selectbox(
            tr("子文件夹", "Subfolder"),
            child_directories,
            index=None,
            placeholder=tr("选择要进入的文件夹", "Choose a folder to open"),
            format_func=lambda path: path.name,
            key=f"{key_prefix}_child",
        )
        st.button(
            tr("进入", "Open"),
            key=f"{key_prefix}_enter",
            width="stretch",
            disabled=selected_child is None,
            on_click=_set_browser_directory,
            args=(browser_key, str(selected_child) if selected_child else ""),
        )
        st.button(
            tr("选择当前文件夹", "Select current folder"),
            key=f"{key_prefix}_select",
            type="primary",
            width="stretch",
            on_click=_select_browser_directory,
            args=(state_key, browser_key, str(browser_path)),
        )


def confirm_clear(
    label: str,
    *,
    key: str,
    description: str,
    confirmation: str = "CLEAR",
) -> bool:
    with st.container(key=f"danger_{key}"):
        with st.popover(label, icon=":material/delete:", width="stretch"):
            st.warning(description)
            value = st.text_input(
                f"输入 {confirmation} 确认",
                key=f"{key}_confirmation",
            )
            with st.container(key=f"danger_{key}_confirm"):
                return st.button(
                    label,
                    key=f"{key}_button",
                    disabled=value != confirmation,
                    width="stretch",
                )


def _schedule_exit() -> None:
    from threading import Timer

    shutdown = Timer(1.5, lambda: os._exit(0))
    shutdown.daemon = True
    shutdown.start()


def require_ready(paths: PlatformPaths) -> None:
    if paths.is_ready():
        return
    st.error(
        "Benchmark-dllm root is not ready. Expected run_bench.py and configs/models under "
        f"{paths.benchmark_root}"
    )
    st.stop()


def short_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _legacy_zoomable_image(
    path: str | Path,
    *,
    caption: str = "",
    preview_width: int | str = "66.666%",
) -> None:
    """Render a compact image that opens in a page-level lightbox."""
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    mime = {
        ".gif": "image/gif",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    identity = hashlib.sha1(str(image_path.resolve()).encode("utf-8")).hexdigest()[:14]
    viewer_id = f"zoom-{identity}"
    safe_caption = html.escape(caption)
    caption_html = (
        f'<div class="zoom-caption">{safe_caption}</div>' if safe_caption else ""
    )
    preview_css = f"{preview_width}px" if isinstance(preview_width, int) else preview_width
    wheel_handler = (
        "event.preventDefault();"
        "const viewport=this.parentElement;"
        "const viewRect=viewport.getBoundingClientRect();"
        "const pointerX=event.clientX-viewRect.left;"
        "const pointerY=event.clientY-viewRect.top;"
        "const oldWidth=this.getBoundingClientRect().width;"
        "const factor=event.deltaY<0?1.16:0.862;"
        "const minimum=Math.max(180,Math.min(this.naturalWidth,viewport.clientWidth)*0.25);"
        "const maximum=Math.max(this.naturalWidth,viewport.clientWidth)*8;"
        "const newWidth=Math.min(maximum,Math.max(minimum,oldWidth*factor));"
        "const contentX=viewport.scrollLeft+pointerX;"
        "const contentY=viewport.scrollTop+pointerY;"
        "this.style.maxWidth='none';this.style.maxHeight='none';"
        "this.style.width=newWidth+'px';this.style.height='auto';this.style.margin='0';"
        "const ratio=newWidth/oldWidth;"
        "requestAnimationFrame(()=>{viewport.scrollLeft=contentX*ratio-pointerX;"
        "viewport.scrollTop=contentY*ratio-pointerY;});"
    )
    reset_handler = (
        "this.style.width='';this.style.height='';this.style.maxWidth='90vw';"
        "this.style.maxHeight='82vh';this.style.margin='auto';"
        "this.parentElement.scrollTo({left:0,top:0,behavior:'smooth'});"
    )
    st.markdown(
        f"""
        <style>
        .zoom-media {{width:{preview_css};max-width:100%;margin:.25rem 0 1rem;}}
        .zoom-thumb {{display:block;width:100%;height:auto;border:1px solid #ddd7cc;
            border-radius:10px;cursor:zoom-in;background:#fff;}}
        .zoom-caption {{font-size:.82rem;color:#625d55;margin-top:.35rem;}}
        .zoom-overlay {{display:none;position:fixed;inset:0;z-index:999999;
            align-items:center;justify-content:center;padding:3vh 3vw;}}
        .zoom-overlay:target {{display:flex;}}
        .zoom-backdrop {{position:absolute;inset:0;background:rgba(15,23,42,.82);}}
        .zoom-viewer {{position:relative;z-index:1;max-width:94vw;max-height:92vh;
            padding:18px;border-radius:14px;background:#fff;box-shadow:0 22px 80px rgba(0,0,0,.45);}}
        .zoom-toolbar {{height:24px;font-size:.8rem;color:#625d55;}}
        .zoom-viewport {{width:90vw;height:82vh;overflow:auto;background:#f7f5ef;}}
        .zoom-viewer img {{display:block;max-width:90vw;max-height:82vh;width:auto;height:auto;margin:auto;}}
        .zoom-close {{position:absolute;right:-12px;top:-14px;width:34px;height:34px;
            border-radius:50%;background:#fff;color:#1f2937;text-decoration:none;text-align:center;
            font:26px/31px sans-serif;box-shadow:0 3px 14px rgba(0,0,0,.3);}}
        @media (max-width:760px) {{.zoom-media {{width:100%;}}}}
        </style>
        <div class="zoom-media">
          <a href="#{viewer_id}" aria-label="放大查看 {safe_caption}">
            <img class="zoom-thumb" src="data:{mime};base64,{encoded}" alt="{safe_caption}" />
          </a>
          {caption_html}
        </div>
        <div id="{viewer_id}" class="zoom-overlay">
          <a class="zoom-backdrop" href="#" aria-label="关闭"></a>
          <div class="zoom-viewer">
            <a class="zoom-close" href="#" aria-label="关闭">×</a>
            <div class="zoom-toolbar">滚轮缩放 · 双击复位</div>
            <div class="zoom-viewport">
              <img src="data:{mime};base64,{encoded}" alt="{safe_caption}"
                onwheel="{wheel_handler}" ondblclick="{reset_handler}" />
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pausable_gif(path: Path, *, caption: str | None = None) -> None:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        st.error(f"无法读取动图：{exc}")
        return
    encoded = base64.b64encode(payload).decode("ascii")
    identifier = "gif_" + hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    if len(payload) >= 10 and payload[:3] == b"GIF":
        source_width = int.from_bytes(payload[6:8], "little") or 800
        source_height = int.from_bytes(payload[8:10], "little") or 480
    else:
        source_width, source_height = 800, 480
    display_height = int(source_height * min(1.0, 900.0 / source_width))
    frame_height = max(220, min(900, display_height + 82))
    safe_caption = html.escape(caption or path.name)
    st.iframe(
        f"""
        <div style="width:100%;text-align:center;font-family:Georgia,'Times New Roman',serif;">
          <div style="position:relative;display:inline-block;max-width:100%;">
            <img id="{identifier}_image" src="data:image/gif;base64,{encoded}"
                 style="display:block;max-width:100%;height:auto;border-radius:10px;" />
            <canvas id="{identifier}_canvas"
                    style="display:none;max-width:100%;height:auto;border-radius:10px;"></canvas>
          </div>
          <div style="margin-top:10px;">
            <button id="{identifier}_toggle" style="
              border:1px solid #cbd5e1;border-radius:7px;background:#fff;
              padding:6px 16px;cursor:pointer;color:#334155;font-size:13px;">
              暂停
            </button>
          </div>
          <div style="margin-top:7px;color:#64748b;font-size:12px;">{safe_caption}</div>
        </div>
        <script>
        (() => {{
          const image = document.getElementById("{identifier}_image");
          const canvas = document.getElementById("{identifier}_canvas");
          const button = document.getElementById("{identifier}_toggle");
          let paused = false;
          button.onclick = () => {{
            if (!paused) {{
              canvas.width = image.naturalWidth;
              canvas.height = image.naturalHeight;
              canvas.getContext("2d").drawImage(image, 0, 0);
              canvas.style.width = `${{image.clientWidth}}px`;
              image.style.display = "none";
              canvas.style.display = "block";
              button.textContent = "继续";
            }} else {{
              canvas.style.display = "none";
              image.style.display = "block";
              button.textContent = "暂停";
            }}
            paused = !paused;
          }};
        }})();
        </script>
        """,
        height=frame_height,
    )


def zoomable_image(
    path: str | Path,
    *,
    caption: str = "",
    preview_width: int | str = "66.666%",
    preview_height: int | None = None,
) -> None:
    """Render image controls at top right and a browser fullscreen viewer."""
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    mime = {
        ".gif": "image/gif",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    identity = hashlib.sha1(
        f"{image_path.resolve()}|{caption}".encode("utf-8")
    ).hexdigest()[:14]
    safe_caption = html.escape(caption)
    caption_html = f'<div class="caption">{safe_caption}</div>' if safe_caption else ""
    preview_css = f"{preview_width}px" if isinstance(preview_width, int) else preview_width
    preview_height_css = f"height:{preview_height}px;" if preview_height else ""
    image_size_css = (
        "height:100%;max-height:none;"
        if preview_height
        else "height:auto;max-height:420px;"
    )
    image_data = f"data:{mime};base64,{encoded}"
    copy_mime = "image/gif" if suffix == ".gif" else "image/png"
    copy_label = "复制 GIF" if suffix == ".gif" else "复制 PNG"
    download_label = "下载 GIF" if suffix == ".gif" else "下载 PNG"
    download_name = image_path.name if suffix == ".gif" else f"{image_path.stem}.png"
    document = """
    <!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;font-family:sans-serif}
    .preview{position:relative;width:__WIDTH__;max-width:100%;margin:.25rem auto .5rem;__PREVIEW_HEIGHT__}
    .preview img{display:block;width:100%;__IMAGE_SIZE__object-fit:contain;object-position:center center;
      border:1px solid rgba(120,120,120,.24);border-radius:10px;background:#fff}
    .preview-tools{position:absolute;right:9px;top:9px;display:flex;gap:3px;z-index:2;opacity:0;
      transform:translateY(-3px);transition:opacity .15s ease,transform .15s ease}
    .preview:hover .preview-tools,.preview-tools:focus-within{opacity:1;transform:translateY(0)}
    button{font:inherit}.action{display:grid;place-items:center;width:30px;height:30px;padding:0;
      border:1px solid rgba(203,213,225,.9);border-radius:5px;background:rgba(255,255,255,.94);
      color:#334155;cursor:pointer;box-shadow:0 2px 8px rgba(15,23,42,.14);backdrop-filter:blur(5px)}
    .action svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;
      stroke-linecap:round;stroke-linejoin:round}
    .action:hover{background:#fff;border-color:#94a3b8}.caption{margin-top:7px;color:#737b86;font-size:13px}
    .viewer{display:none;height:100vh;background:#111720;grid-template-rows:48px minmax(0,1fr);overflow:hidden}
    html.viewer-open,html.viewer-open body{width:100%;height:100%;overflow:hidden;background:#111720}
    html.viewer-open .preview{display:none}html.viewer-open .viewer{display:grid}
    .toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:7px 10px;
      color:#eef2f7;background:#171e28;border-bottom:1px solid #303946}
    .tools{display:flex;align-items:center;gap:7px}.tool{min-width:34px;height:32px;padding:0 10px;
      color:#eef2f7;background:#252e3a;border:1px solid #3c4858;border-radius:7px;cursor:pointer}
    .tool:hover{background:#334052}.scale{min-width:54px;text-align:center;font-size:13px;color:#c9d1dc}
    .hint{color:#9da8b7;font-size:12px;white-space:nowrap}.viewport{position:relative;overflow:hidden;
      min-width:0;min-height:0;cursor:grab;user-select:none;overscroll-behavior:contain;touch-action:none}
    .viewport.dragging{cursor:grabbing}.canvas{position:absolute;inset:0}.canvas img{display:block;
      position:absolute;left:0;top:0;max-width:none;height:auto;border-radius:6px;background:#fff;
      box-shadow:0 12px 38px rgba(0,0,0,.38);pointer-events:none;transform-origin:0 0;will-change:transform}
    @media(max-width:760px){.preview{width:100%}.hint{display:none}.preview-tools{opacity:1;transform:none}}
    </style></head><body>
    <div class="preview"><div class="preview-tools">
      <button class="action" id="fullscreen" type="button" title="全屏查看" aria-label="全屏查看">
        <svg viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>
      </button>
      <button class="action" id="copy-preview" type="button" title="__COPY_LABEL__" aria-label="__COPY_LABEL__">
        <svg viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>
      </button>
      <button class="action" id="download-preview" type="button" title="__DOWNLOAD_LABEL__" aria-label="__DOWNLOAD_LABEL__">
        <svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 19h16"/></svg>
      </button>
    </div><img id="preview-image" src="__IMAGE__" alt="__CAPTION__">
    __CAPTION_HTML__</div>
    <div class="viewer"><div class="toolbar"><div class="tools">
      <button class="tool" id="minus" type="button" title="缩小">−</button>
      <span class="scale" id="scale">100%</span>
      <button class="tool" id="plus" type="button" title="放大">+</button>
      <button class="tool" id="reset" type="button">复位</button>
      <button class="tool" id="copy-viewer" type="button">__COPY_LABEL__</button>
      <button class="tool" id="download-viewer" type="button">__DOWNLOAD_LABEL__</button>
    </div><span class="hint">滚轮缩放 · 拖动查看 · 双击复位</span>
    <button class="tool" id="close" type="button">退出全屏</button></div>
    <div class="viewport" id="viewport"><div class="canvas">
      <img id="viewer-image" src="__IMAGE__" alt="__CAPTION__">
    </div></div></div>
    <script>(()=>{
      const root=document.documentElement,viewport=document.getElementById('viewport');
      const image=document.getElementById('viewer-image'),previewImage=document.getElementById('preview-image');
      const preview=document.querySelector('.preview'),scaleText=document.getElementById('scale');
      let scale=1,fitted=1,panX=0,panY=0,dragging=false,dragX=0,dragY=0,startPanX=0,startPanY=0;
      const resizeFrame=()=>{};
      const draw=()=>{image.style.width=`${image.naturalWidth}px`;
        image.style.transform=`translate3d(${panX}px,${panY}px,0) scale(${scale})`;
        scaleText.textContent=`${Math.round(scale/fitted*100)}%`};
      const fit=()=>{if(!image.naturalWidth)return;fitted=Math.min(1,
        Math.max(120,viewport.clientWidth-48)/image.naturalWidth,
        Math.max(120,viewport.clientHeight-48)/image.naturalHeight);scale=fitted;
        panX=(viewport.clientWidth-image.naturalWidth*scale)/2;
        panY=(viewport.clientHeight-image.naturalHeight*scale)/2;draw()};
      const zoom=(factor,x,y)=>{if(!image.naturalWidth)return;const old=scale;
        scale=Math.max(fitted*.35,Math.min(Math.max(fitted*8,2),scale*factor));if(Math.abs(scale-old)<.0001)return;
        const rect=viewport.getBoundingClientRect(),px=x-rect.left,py=y-rect.top,ratio=scale/old;
        panX=px-(px-panX)*ratio;panY=py-(py-panY)*ratio;draw()};
      const centerZoom=factor=>{const r=viewport.getBoundingClientRect();zoom(factor,r.left+r.width/2,r.top+r.height/2)};
      const openViewer=async()=>{root.classList.add('viewer-open');
        try{await root.requestFullscreen()}catch(error){}
        requestAnimationFrame(fit)};
      const closeViewer=async()=>{if(document.fullscreenElement){await document.exitFullscreen()}
        root.classList.remove('viewer-open');requestAnimationFrame(resizeFrame)};
      document.getElementById('fullscreen').onclick=openViewer;
      document.getElementById('close').onclick=closeViewer;
      document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement)root.classList.remove('viewer-open')});
      document.getElementById('plus').onclick=()=>centerZoom(1.25);
      document.getElementById('minus').onclick=()=>centerZoom(.8);
      document.getElementById('reset').onclick=fit;viewport.ondblclick=fit;
      viewport.addEventListener('wheel',event=>{event.preventDefault();zoom(event.deltaY<0?1.16:.86,event.clientX,event.clientY)},{passive:false});
      viewport.addEventListener('pointerdown',event=>{if(event.button!==0)return;dragging=true;dragX=event.clientX;dragY=event.clientY;
        startPanX=panX;startPanY=panY;viewport.classList.add('dragging');viewport.setPointerCapture(event.pointerId)});
      viewport.addEventListener('pointermove',event=>{if(!dragging)return;panX=startPanX+(event.clientX-dragX);
        panY=startPanY+(event.clientY-dragY);draw()});
      const stop=event=>{dragging=false;viewport.classList.remove('dragging');
        if(event.pointerId!==undefined&&viewport.hasPointerCapture(event.pointerId))viewport.releasePointerCapture(event.pointerId)};
      viewport.addEventListener('pointerup',stop);viewport.addEventListener('pointercancel',stop);
      const imageBlob=async()=>{let blob;if('__COPY_MIME__'==='image/gif'){blob=await fetch(previewImage.src).then(response=>response.blob())}
          else{if(!previewImage.complete)await previewImage.decode();const canvas=document.createElement('canvas');canvas.width=previewImage.naturalWidth;
            canvas.height=previewImage.naturalHeight;const context=canvas.getContext('2d');context.fillStyle='#fff';
            context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(previewImage,0,0);
            blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'))}
          if(!blob)throw new Error('image conversion failed');return blob};
      const copyImage=async()=>{
        try{const blob=await imageBlob();await navigator.clipboard.write([new ClipboardItem({['__COPY_MIME__']:blob})])}
        catch(error){console.warn('Image copy failed',error)}};
      const downloadImage=async()=>{
        try{const blob=await imageBlob();
          const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;
          link.download='__DOWNLOAD_NAME__';document.body.appendChild(link);link.click();link.remove();
          setTimeout(()=>URL.revokeObjectURL(url),1000)}
        catch(error){console.warn('Image download failed',error)}};
      document.getElementById('copy-preview').onclick=copyImage;
      document.getElementById('copy-viewer').onclick=copyImage;
      document.getElementById('download-preview').onclick=downloadImage;
      document.getElementById('download-viewer').onclick=downloadImage;
      image.addEventListener('load',()=>{if(root.classList.contains('viewer-open'))fit()});
      previewImage.addEventListener('load',resizeFrame);window.addEventListener('resize',resizeFrame);
      new ResizeObserver(resizeFrame).observe(preview);
      if(previewImage.complete)requestAnimationFrame(resizeFrame);
    })();</script></body></html>
    """
    document = (
        document.replace("__IMAGE__", image_data)
        .replace("__CAPTION__", safe_caption)
        .replace("__CAPTION_HTML__", caption_html)
        .replace("__WIDTH__", preview_css)
        .replace("__PREVIEW_HEIGHT__", preview_height_css)
        .replace("__IMAGE_SIZE__", image_size_css)
        .replace("__COPY_LABEL__", copy_label)
        .replace("__DOWNLOAD_LABEL__", download_label)
        .replace("__COPY_MIME__", copy_mime)
        .replace("__DOWNLOAD_NAME__", html.escape(download_name, quote=True))
    )
    component_height = (
        preview_height + 12
        if preview_height
        else min(438, max(180, preview_width + 48))
        if isinstance(preview_width, int)
        else 438
    )
    st.iframe(document, height=component_height)


def render_plotly_chart(
    figure,
    *,
    key: str,
    legend_title: str = "模型",
    margin: dict | None = None,
) -> None:
    """Render all platform Plotly charts with one shared toolbar."""

    figure.update_layout(
        dragmode=False,
        margin=margin or dict(l=35, r=20, t=58, b=45),
        legend_title_text=legend_title,
    )
    st.plotly_chart(
        figure,
        width="stretch",
        key=key,
        config={
            "scrollZoom": False,
            "displaylogo": False,
            "displayModeBar": True,
            "modeBarButtonsToRemove": [
                "zoom2d",
                "pan2d",
                "select2d",
                "lasso2d",
                "zoomIn2d",
                "zoomOut2d",
                "autoScale2d",
                "resetScale2d",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": key,
                "scale": 2,
            },
        },
    )
