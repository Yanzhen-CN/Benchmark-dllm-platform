from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import subprocess
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from .gif_frames import decode_gif_frames
from .paths import PlatformPaths


def configure_page(title: str, icon: str = "▦") -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    components.html(
        """
        <script>
        (() => {
          const host = window.parent;
          const copyMarker = "__benchmarkCopyShortcutGuard";
          if (!host[copyMarker]) {
            host.document.addEventListener("keydown", (event) => {
              const isCopy = (event.ctrlKey || event.metaKey)
                && String(event.key).toLowerCase() === "c";
              if (isCopy) event.stopImmediatePropagation();
            }, true);
            host[copyMarker] = true;
          }

          const plotlyToolsMarker = "__benchmarkPlotlyToolsV2";
          if (!host[plotlyToolsMarker]) {
            const installButtons = () => {
              host.document.querySelectorAll(".js-plotly-plot").forEach((plot) => {
                const modebar = plot.querySelector(".modebar");
                if (!modebar) return;
                const buttonGroup = modebar.querySelector(".modebar-group") || modebar;
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
                  copyButton.setAttribute("data-title", "复制 PNG");
                  copyButton.setAttribute("role", "button");
                  copyButton.setAttribute("aria-label", "复制 PNG");
                  copyButton.innerHTML = '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
                  copyButton.addEventListener("click", async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const originalTitle = copyButton.getAttribute("data-title");
                    try {
                      const svg = plot.querySelector(".svg-container > .main-svg")
                        || plot.querySelector(".main-svg");
                      if (!svg) throw new Error("plot SVG unavailable");
                      const rect = svg.getBoundingClientRect();
                      const clone = svg.cloneNode(true);
                      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
                      clone.setAttribute("width", String(rect.width));
                      clone.setAttribute("height", String(rect.height));
                      const source = new XMLSerializer().serializeToString(clone);
                      const sourceBlob = new Blob([source], {type: "image/svg+xml;charset=utf-8"});
                      const sourceUrl = URL.createObjectURL(sourceBlob);
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
                      const pngBlob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
                      if (!pngBlob) throw new Error("PNG conversion failed");
                      await host.navigator.clipboard.write([
                        new host.ClipboardItem({"image/png": pngBlob})
                      ]);
                      copyButton.setAttribute("data-title", "已复制 PNG");
                    } catch (error) {
                      copyButton.setAttribute("data-title", "复制失败");
                      console.warn("Plotly PNG copy failed", error);
                    }
                    setTimeout(() => copyButton.setAttribute("data-title", originalTitle), 1600);
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
        })();
        </script>
        """,
        height=0,
        width=0,
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def paths_sidebar() -> PlatformPaths:
    defaults = PlatformPaths.from_values()
    with st.sidebar.expander("Workspace", expanded=False):
        benchmark_key = "workspace_benchmark_root"
        output_key = "workspace_output_root"
        st.session_state.setdefault(benchmark_key, str(defaults.benchmark_root))
        st.session_state.setdefault(output_key, str(defaults.output_root))

        benchmark_input, benchmark_browse = st.columns([5, 1])
        benchmark_root = benchmark_input.text_input(
            "Benchmark-dllm root", key=benchmark_key
        )
        with benchmark_browse:
            _directory_picker(benchmark_key, key_prefix="benchmark_root")

        output_input, output_browse = st.columns([5, 1])
        output_root = output_input.text_input("Output root", key=output_key)
        with output_browse:
            _directory_picker(output_key, key_prefix="output_root")
        if st.button("退出平台", width="stretch", type="secondary"):
            st.warning("平台服务正在退出。")
            _schedule_exit()
            st.stop()
    return PlatformPaths.from_values(benchmark_root, output_root)


def _set_browser_directory(browser_key: str, path: str) -> None:
    st.session_state[browser_key] = path


def _select_browser_directory(state_key: str, browser_key: str, path: str) -> None:
    st.session_state[state_key] = path
    st.session_state[browser_key] = path


def _directory_picker(state_key: str, *, key_prefix: str) -> None:
    browser_key = f"{state_key}_browser"
    current_input = Path(st.session_state.get(state_key, "")).expanduser()
    initial = current_input if current_input.is_dir() else Path.home()
    browser_path = Path(st.session_state.get(browser_key, initial)).expanduser()
    if not browser_path.is_dir():
        browser_path = initial
    browser_path = browser_path.resolve()

    with st.popover("浏览", width="stretch"):
        st.caption("当前文件夹")
        st.code(str(browser_path), language=None)
        home_column, parent_column = st.columns(2)
        home_column.button(
            "主页",
            key=f"{key_prefix}_home",
            width="stretch",
            on_click=_set_browser_directory,
            args=(browser_key, str(Path.home().resolve())),
        )
        parent_column.button(
            "上一级",
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
            "子文件夹",
            child_directories,
            index=None,
            placeholder="选择要进入的文件夹",
            format_func=lambda path: path.name,
            key=f"{key_prefix}_child",
        )
        st.button(
            "进入",
            key=f"{key_prefix}_enter",
            width="stretch",
            disabled=selected_child is None,
            on_click=_set_browser_directory,
            args=(browser_key, str(selected_child) if selected_child else ""),
        )
        st.button(
            "选择当前文件夹",
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
    pid = os.getpid()
    if os.name == "nt":
        command = (
            "Start-Sleep -Milliseconds 500; "
            f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                command,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        subprocess.Popen(["sh", "-c", f"sleep 0.5; kill -TERM {pid}"])


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
        frames, durations, source_width, source_height = decode_gif_frames(path)
    except (OSError, ValueError) as exc:
        st.error(f"无法读取动图：{exc}")
        return
    if not frames:
        st.info("动图没有可显示的帧。")
        return

    identifier = "gif_" + hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    safe_caption = html.escape(caption or path.name)
    display_width = min(source_width, 560)
    display_height = round(source_height * display_width / max(1, source_width))
    frame_height = max(230, min(900, display_height + 84))
    frame_json = json.dumps(frames, ensure_ascii=True)
    duration_json = json.dumps(durations)

    components.html(
        f"""
        <!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
        *{{box-sizing:border-box}}html,body{{margin:0;padding:0;background:transparent;font-family:sans-serif}}
        .wrap{{width:100%;text-align:center}}.stage{{position:relative;display:inline-block;
          width:min(100%,{source_width}px);cursor:pointer;user-select:none}}
        .stage img{{display:block;width:100%;height:auto;border-radius:10px;background:#fff}}
        .overlay{{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none}}
        .icon{{display:grid;place-items:center;width:54px;height:54px;border-radius:999px;
          color:#fff;background:rgba(15,23,42,.42);font-size:22px;line-height:1;
          opacity:.22;transition:opacity .16s ease,transform .16s ease;transform:scale(.94)}}
        .stage:hover .icon,.icon.flash{{opacity:.78;transform:scale(1)}}
        .controls{{display:flex;align-items:center;gap:10px;width:min(100%,{source_width}px);
          margin:8px auto 0;color:#64748b;font-size:12px}}
        .controls input{{flex:1;min-width:80px;accent-color:#0f766e;cursor:pointer}}
        .step{{min-width:76px;text-align:right;font-variant-numeric:tabular-nums}}
        .caption{{margin-top:5px;color:#64748b;font-size:12px}}
        </style></head><body><div class="wrap">
          <div class="stage" id="{identifier}_stage" role="button" tabindex="0"
               aria-label="点击播放或暂停 GIF">
            <img id="{identifier}_image" alt="{safe_caption}">
            <div class="overlay"><div class="icon" id="{identifier}_icon">❚❚</div></div>
          </div>
          <div class="controls">
            <input id="{identifier}_range" type="range" min="0" max="{len(frames) - 1}"
                   value="0" step="1" aria-label="GIF step">
            <span class="step" id="{identifier}_step">step 1 / {len(frames)}</span>
          </div>
          <div class="caption">{safe_caption}</div>
        </div><script>
        (() => {{
          const frames={frame_json},durations={duration_json};
          const stage=document.getElementById("{identifier}_stage");
          const image=document.getElementById("{identifier}_image");
          const icon=document.getElementById("{identifier}_icon");
          const range=document.getElementById("{identifier}_range");
          const step=document.getElementById("{identifier}_step");
          let index=0,playing=true,timer=null,flashTimer=null;
          const show=()=>{{image.src=frames[index];range.value=String(index);
            step.textContent="step "+(index+1)+" / "+frames.length}};
          const flash=()=>{{icon.textContent=playing?"❚❚":"▶";icon.classList.add("flash");
            clearTimeout(flashTimer);flashTimer=setTimeout(()=>icon.classList.remove("flash"),520)}};
          const schedule=()=>{{clearTimeout(timer);if(!playing)return;
            timer=setTimeout(()=>{{index=(index+1)%frames.length;show();schedule()}},durations[index])}};
          const toggle=()=>{{playing=!playing;flash();schedule()}};
          stage.onclick=toggle;stage.onkeydown=event=>{{if(event.key===" "||event.key==="Enter"){{
            event.preventDefault();toggle()}}}};
          range.oninput=()=>{{playing=false;clearTimeout(timer);index=Number(range.value);show();flash()}};
          show();schedule();
        }})();
        </script></body></html>
        """,
        height=frame_height,
        scrolling=False,
    )

def zoomable_image(
    path: str | Path,
    *,
    caption: str = "",
    preview_width: int | str = "66.666%",
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
    safe_caption = html.escape(caption or image_path.name)
    preview_css = f"{preview_width}px" if isinstance(preview_width, int) else preview_width
    image_data = f"data:{mime};base64,{encoded}"
    copy_mime = "image/gif" if suffix == ".gif" else "image/png"
    copy_label = "复制 GIF" if suffix == ".gif" else "复制 PNG"
    copied_label = "已复制 GIF" if suffix == ".gif" else "已复制 PNG"
    document = """
    <!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;font-family:sans-serif}
    .preview{position:relative;width:__WIDTH__;max-width:100%;margin:.25rem 0 1rem}
    .preview img{display:block;width:100%;max-height:420px;object-fit:contain;object-position:left center;
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
    </div><img id="preview-image" src="__IMAGE__" alt="__CAPTION__">
    <div class="caption">__CAPTION__</div></div>
    <div class="viewer"><div class="toolbar"><div class="tools">
      <button class="tool" id="minus" type="button" title="缩小">−</button>
      <span class="scale" id="scale">100%</span>
      <button class="tool" id="plus" type="button" title="放大">+</button>
      <button class="tool" id="reset" type="button">复位</button>
      <button class="tool" id="copy-viewer" type="button">__COPY_LABEL__</button>
    </div><span class="hint">滚轮缩放 · 拖动查看 · 双击复位</span>
    <button class="tool" id="close" type="button">退出全屏</button></div>
    <div class="viewport" id="viewport"><div class="canvas">
      <img id="viewer-image" src="__IMAGE__" alt="__CAPTION__">
    </div></div></div>
    <script>(()=>{
      const root=document.documentElement,viewport=document.getElementById('viewport');
      const image=document.getElementById('viewer-image'),previewImage=document.getElementById('preview-image');
      const scaleText=document.getElementById('scale');
      let scale=1,fitted=1,panX=0,panY=0,dragging=false,dragX=0,dragY=0,startPanX=0,startPanY=0;
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
        root.classList.remove('viewer-open')};
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
      const copyImage=async(button)=>{const original=button.textContent;
        try{let blob;if('__COPY_MIME__'==='image/gif'){blob=await fetch(previewImage.src).then(response=>response.blob())}
          else{if(!previewImage.complete)await previewImage.decode();const canvas=document.createElement('canvas');canvas.width=previewImage.naturalWidth;
            canvas.height=previewImage.naturalHeight;const context=canvas.getContext('2d');context.fillStyle='#fff';
            context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(previewImage,0,0);
            blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'))}
          if(!blob)throw new Error('image conversion failed');
          await navigator.clipboard.write([new ClipboardItem({['__COPY_MIME__']:blob})]);button.textContent='__COPIED_LABEL__'}
        catch(error){button.textContent='复制失败'}setTimeout(()=>{button.textContent=original},1600)};
      document.getElementById('copy-preview').onclick=event=>copyImage(event.currentTarget);
      document.getElementById('copy-viewer').onclick=event=>copyImage(event.currentTarget);
      image.addEventListener('load',()=>{if(root.classList.contains('viewer-open'))fit()});
    })();</script></body></html>
    """
    document = (
        document.replace("__IMAGE__", image_data)
        .replace("__CAPTION__", safe_caption)
        .replace("__WIDTH__", preview_css)
        .replace("__COPY_LABEL__", copy_label)
        .replace("__COPIED_LABEL__", copied_label)
        .replace("__COPY_MIME__", copy_mime)
    )
    components.html(document, height=455, scrolling=False)
