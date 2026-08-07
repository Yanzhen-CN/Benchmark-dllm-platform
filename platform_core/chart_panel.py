from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from .i18n import tr
from .maintenance import (
    move_output_paths_to_trash,
    permanently_delete_output_paths,
)
from .paths import PlatformPaths
from .visualization import (
    platform_chart_command,
    run_visualization_command,
)


def plotly_spec(figure) -> dict:
    return {"kind": "plotly", "figure": json.loads(figure.to_json())}


def _path_key(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]


@st.dialog("Delete visualization / 删除图表")
def _delete_generated_chart(output_root: Path, path: Path) -> None:
    try:
        relative = path.resolve().relative_to(output_root.resolve())
    except ValueError:
        st.error(
            tr(
                "该文件不在输出目录中，不能从平台删除。",
                "This file is outside the output directory and cannot be deleted here.",
            )
        )
        return

    st.write(relative.as_posix())
    st.caption(
        tr(
            "移到回收站后可以恢复；永久删除后无法恢复。",
            "Items moved to the Recycle Bin can be restored. Permanent deletion cannot be undone.",
        )
    )
    token = _path_key(path)
    recycle_column, permanent_column = st.columns(2)
    with recycle_column:
        if st.button(
            tr("移到回收站", "Move to Recycle Bin"),
            key=f"recycle_generated_{token}",
            use_container_width=True,
        ):
            move_output_paths_to_trash(output_root, [path])
            st.rerun()
    with permanent_column:
        if st.button(
            tr("永久删除", "Delete permanently"),
            key=f"permanent_generated_{token}",
            type="primary",
            use_container_width=True,
        ):
            permanently_delete_output_paths(output_root, [path])
            st.rerun()


def render_chart_panel(
    paths: PlatformPaths,
    *,
    title: str,
    section: str,
    key: str,
    preview: Callable[[], None],
    spec: dict | None = None,
    generated_path: Path | None = None,
    command: list[str] | list[list[str]] | None = None,
    prefer_generated: bool = False,
    generated_width: int | str = "stretch",
    generated_height: int | None = None,
    compact_header: bool = False,
    collapsible: bool = False,
    show_heading: bool = True,
    footer: Callable[[], None] | None = None,
) -> None:
    if collapsible:
        with st.expander(title, expanded=False):
            render_chart_panel(
                paths,
                title=title,
                section=section,
                key=key,
                preview=preview,
                spec=spec,
                generated_path=generated_path,
                command=command,
                prefer_generated=prefer_generated,
                generated_width=generated_width,
                generated_height=generated_height,
                compact_header=True,
                collapsible=False,
                show_heading=False,
                footer=footer,
            )
        return
    if spec is not None:
        command, generated_path = platform_chart_command(
            paths,
            section=section,
            key=key,
            spec={**spec, "title": spec.get("title") or title},
        )
    if generated_path is None or command is None:
        raise ValueError("chart panel requires a spec or an explicit command/path")

    view_options = [tr("预览", "Preview"), tr("正式图", "Generated")]
    default_view = (
        tr("正式图", "Generated")
        if prefer_generated and generated_path.is_file()
        else tr("预览", "Preview")
    )
    if compact_header:
        if show_heading:
            st.markdown(f"**{title}**")
        with st.container(
            horizontal=True,
            horizontal_alignment="right",
            vertical_alignment="center",
            gap="small",
        ):
            view = st.segmented_control(
                tr("查看方式", "View"),
                view_options,
                default=default_view,
                key=f"chart_view_{section}_{key}",
                label_visibility="collapsed",
                width="content",
            )
            generate = st.button(
                tr("生成", "Generate"),
                key=f"chart_generate_{section}_{key}",
                width="content",
            )
            delete_slot = st.empty()
        delete_width = "content"
    else:
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
            gap="small",
        ):
            st.markdown(f"#### {title}")
            with st.container(
                horizontal=True,
                horizontal_alignment="right",
                vertical_alignment="center",
                gap="small",
                width="content",
            ):
                view = st.segmented_control(
                    tr("查看方式", "View"),
                    view_options,
                    default=default_view,
                    key=f"chart_view_{section}_{key}",
                    label_visibility="collapsed",
                    width="content",
                )
                generate = st.button(
                    tr("生成", "Generate"),
                    key=f"chart_generate_{section}_{key}",
                    width="content",
                )
                delete_slot = st.empty()
        delete_width = "content"
    if generate:
        commands = command if command and isinstance(command[0], list) else [command]
        failures = []
        with st.spinner(tr(f"正在生成 {title}...", f"Generating {title}...")):
            for item in commands:
                result = run_visualization_command(paths, item)
                if result.returncode:
                    failures.append(
                        "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-24:])
                    )
        if failures:
            st.error(tr("生成失败。", "Generation failed."))
            st.code("\n\n".join(failures), language="text")
        else:
            st.success(tr("正式图已保存。", "Generated visualization saved."))

    delete = delete_slot.button(
        tr("删除", "Delete"),
        key=f"chart_delete_{section}_{key}",
        disabled=not generated_path.is_file(),
        width=delete_width,
    )
    if delete:
        _delete_generated_chart(paths.output_root, generated_path)

    if view == tr("正式图", "Generated"):
        if generated_path.is_file():
            from platform_core.ui import zoomable_image

            preview_width = (
                generated_width if isinstance(generated_width, int) else "100%"
            )
            zoomable_image(
                generated_path,
                caption="",
                preview_width=preview_width,
                preview_height=generated_height,
            )
        else:
            st.info(
                tr(
                    "尚未生成正式图，请点击“生成”。",
                    "No generated visualization yet. Select Generate.",
                )
            )
    else:
        preview()
    if footer is not None:
        footer()
