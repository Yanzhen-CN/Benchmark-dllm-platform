from __future__ import annotations

import json
import importlib.util
import math
import os
import re
from pathlib import Path
from typing import Any

import plotly.graph_objects as go


TRACE_COLORS = [
    [0.00, "#d8d6d1"],
    [0.19, "#d8d6d1"],
    [0.20, "#b9ddd5"],
    [0.39, "#b9ddd5"],
    [0.40, "#4c78a8"],
    [0.59, "#4c78a8"],
    [0.60, "#f2c14e"],
    [0.79, "#f2c14e"],
    [0.80, "#e76f51"],
    [1.00, "#a62929"],
]

REACCEPT_COLORSCALE = [
    [0.00, "#dc2626"],
    [0.50, "#c026d3"],
    [1.00, "#6d28d9"],
]


def _nice_tick_step(width: int, target_ticks: int = 10) -> int:
    """Return an integer 1/2/5-style step with at most about target_ticks."""

    rough = max(1.0, width / max(1, target_ticks))
    magnitude = 10 ** math.floor(math.log10(rough))
    normalized = rough / magnitude
    factor = 1 if normalized <= 1 else 2 if normalized <= 2 else 5 if normalized <= 5 else 10
    return max(1, int(factor * magnitude))


def _reaccept_color(rank: int, maximum_rank: int) -> str:
    """Return the final marker color without relying on browser color mapping."""

    if maximum_rank <= 2:
        return "#dc2626"
    amount = max(0.0, min(1.0, (rank - 2) / (maximum_rank - 2)))
    stops = (
        (0.0, (220, 38, 38)),
        (0.5, (192, 38, 211)),
        (1.0, (109, 40, 217)),
    )
    left, right = stops[0], stops[-1]
    for start, end in zip(stops, stops[1:]):
        if start[0] <= amount <= end[0]:
            left, right = start, end
            break
    span = right[0] - left[0]
    local = 0.0 if span == 0 else (amount - left[0]) / span
    rgb = tuple(
        round(left[1][channel] * (1.0 - local) + right[1][channel] * local)
        for channel in range(3)
    )
    return "#" + "".join(f"{value:02x}" for value in rgb)


def _extract_acceptance_events(trace: list[dict[str, Any]]) -> dict[str, Any]:
    configured = os.environ.get("BENCHMARK_DLLM_ROOT") or os.environ.get(
        "DLLM_BENCH_ROOT"
    )
    if configured:
        benchmark_root = Path(configured).expanduser().resolve()
    else:
        embedded_root = Path(__file__).resolve().parents[2]
        benchmark_root = (
            embedded_root
            if (embedded_root / "src" / "dllm_bench").is_dir()
            else embedded_root / "Benchmark-dllm"
        ).resolve()
    source = benchmark_root / "src" / "dllm_bench" / "trace_events.py"
    spec = importlib.util.spec_from_file_location("dllm_bench_shared_trace_events", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared trace rules from {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extract_acceptance_events(trace)


def load_trace_record(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def trace_event_activity(record: dict[str, Any]) -> tuple[int, int]:
    """Return token-changing accepts and all later state transitions."""

    trace = [step for step in record.get("trace", []) if isinstance(step, dict)]
    if not trace:
        return 0, 0
    events = _extract_acceptance_events(trace)
    revisions = len(events["revision_positions"])
    later_events = (
        revisions
        + len(events["reaccept_positions"])
        + len(events["renoise_positions"])
    )
    return revisions, later_events


def trace_figure(record: dict[str, Any], *, title: str) -> go.Figure:
    trace = [step for step in record.get("trace", []) if isinstance(step, dict)]
    if not trace:
        figure = go.Figure()
        figure.add_annotation(text="No trace data", showarrow=False)
        return figure

    events = _extract_acceptance_events(trace)
    positions = events["accept_positions"]
    steps = events["accept_steps"]
    ranks = events["accept_ranks"]
    revision_indices = set(events["revision_accept_indices"])
    first = [index for index, rank in enumerate(ranks) if rank == 1]
    same_token = [
        index
        for index, rank in enumerate(ranks)
        if rank > 1 and index not in revision_indices
    ]
    revisions = sorted(revision_indices)
    maximum_rank = max(ranks, default=1)
    color_maximum = max(3, maximum_rank)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[positions[index] for index in first],
            y=[steps[index] for index in first],
            mode="markers",
            marker=dict(size=8, color="#2563eb"),
            name="First accept",
        )
    )
    if same_token:
        figure.add_trace(
            go.Scatter(
                x=[positions[index] for index in same_token],
                y=[steps[index] for index in same_token],
                mode="markers",
                marker=dict(
                    size=10,
                    color=[
                        _reaccept_color(ranks[index], maximum_rank)
                        for index in same_token
                    ],
                    line=dict(color="#ffffff", width=1),
                ),
                customdata=[ranks[index] for index in same_token],
                hovertemplate="position %{x}<br>forward %{y}<br>accept #%{customdata}<extra></extra>",
                name="Re-accept, same token",
            )
        )
    if revisions:
        figure.add_trace(
            go.Scatter(
                x=[positions[index] for index in revisions],
                y=[steps[index] for index in revisions],
                mode="markers",
                marker=dict(
                    symbol="x",
                    size=14,
                    color=[
                        _reaccept_color(ranks[index], maximum_rank)
                        for index in revisions
                    ],
                ),
                customdata=[ranks[index] for index in revisions],
                hovertemplate="position %{x}<br>forward %{y}<br>accept #%{customdata}<extra></extra>",
                name="Re-accept, token changed",
            )
        )
    if (same_token or revisions) and maximum_rank > 2:
        figure.add_trace(
            go.Scatter(
                x=[None, None],
                y=[None, None],
                mode="markers",
                marker=dict(
                    size=0.1,
                    color=[2, color_maximum],
                    colorscale=REACCEPT_COLORSCALE,
                    cmin=2,
                    cmax=color_maximum,
                    showscale=True,
                    colorbar=dict(
                        title="Accept<br>number",
                        tickvals=list(range(2, maximum_rank + 1)),
                        thickness=10,
                        x=0.99,
                        xanchor="right",
                        y=0.76,
                        len=0.28,
                    ),
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    if events["renoise_positions"]:
        figure.add_trace(
            go.Scatter(
                x=events["renoise_positions"],
                y=events["renoise_steps"],
                mode="markers",
                marker=dict(symbol="triangle-down", size=9, color="#9ca3af"),
                name="Re-noise",
            )
        )
    width = max(len(step.get("position_states") or []) for step in trace)
    x_tick_step = _nice_tick_step(width)
    maximum_forward = max(int(step.get("forward_index", 0)) for step in trace)
    summary = (
        f"accept events: {len(positions)}<br>"
        f"re-noise events: {len(events['renoise_positions'])}<br>"
        f"re-accept events: {sum(rank > 1 for rank in ranks)}<br>"
        f"token-changing accepts: {len(revisions)}<br>"
        f"revised positions: {len(set(events['revision_positions']))}<br>"
        f"accepted more than once: {sum(count > 1 for count in events['accept_count_by_position'].values())}<br>"
        f"maximum accepts: {max(ranks, default=0)}"
    )
    figure.update_layout(
        title="",
        height=520,
        margin=dict(l=55, r=20, t=75, b=50),
        paper_bgcolor="#f6f3eb",
        plot_bgcolor="#fbfaf6",
        font=dict(color="#17201e", family="DejaVu Sans"),
        xaxis=dict(
            title="Global token position",
            range=[-0.5, width - 0.5],
            tickmode="linear",
            tick0=0,
            dtick=x_tick_step,
            tickformat="d",
        ),
        yaxis=dict(title="Forward step", range=[-1, maximum_forward + 1]),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.04,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=10),
            bgcolor="rgba(246,243,235,0.78)",
        ),
        annotations=[
            dict(
                x=0.99,
                y=0.02,
                xref="paper",
                yref="paper",
                xanchor="right",
                yanchor="bottom",
                text=summary,
                showarrow=False,
                align="left",
                font=dict(size=9),
                bgcolor="rgba(246,243,235,0.84)",
                bordercolor="rgba(100,116,139,0.22)",
                borderpad=4,
            )
        ],
        dragmode=False,
    )
    figure.update_xaxes(gridcolor="#dedbd2", zeroline=False)
    figure.update_yaxes(gridcolor="#dedbd2", zeroline=False)
    return figure


def _puzzle_from_record(record: dict[str, Any], size: int) -> str | None:
    prompt = str((record.get("request") or {}).get("prompt") or "")
    length = size * size
    labelled = re.search(rf"Puzzle\s*:\s*([0-{size}]{{{length}}})", prompt, re.I)
    if labelled:
        return labelled.group(1)
    candidates = re.findall(rf"(?<![0-9])[0-{size}]{{{length}}}(?![0-9])", prompt)
    return candidates[-1] if candidates else None


def _solve_sudoku(puzzle: str, size: int) -> str | None:
    box = int(size**0.5)
    values = [int(value) for value in puzzle]

    def solve() -> bool:
        try:
            position = values.index(0)
        except ValueError:
            return True
        row, column = divmod(position, size)
        used = set(values[row * size : (row + 1) * size])
        used.update(values[column::size])
        box_row = (row // box) * box
        box_column = (column // box) * box
        used.update(
            values[(box_row + offset_row) * size + box_column + offset_column]
            for offset_row in range(box)
            for offset_column in range(box)
        )
        for candidate in range(1, size + 1):
            if candidate in used:
                continue
            values[position] = candidate
            if solve():
                return True
        values[position] = 0
        return False

    return "".join(str(value) for value in values) if solve() else None


def _visible_answer(text: str, size: int) -> str:
    length = size * size
    full = re.findall(rf"(?<![0-9])[1-{size}]{{{length}}}(?![0-9])", text)
    if full:
        return full[-1]
    fragments = re.findall(rf"[1-{size}]+", text)
    if not fragments:
        return ""
    fragment = max(enumerate(fragments), key=lambda item: (len(item[1]), item[0]))[1]
    return fragment[-length:]


def sudoku_animation_figure(
    record: dict[str, Any],
    *,
    dataset: str,
    title: str,
) -> go.Figure | None:
    size = 4 if dataset.startswith("sudoku4") else 9
    puzzle = _puzzle_from_record(record, size)
    if puzzle is None:
        return None
    solution = _solve_sudoku(puzzle, size)
    trace = [step for step in record.get("trace", []) if isinstance(step, dict)]
    if not trace:
        return None

    def frame_payload(step: dict[str, Any]) -> tuple[list[list[int]], list[dict[str, Any]]]:
        answer = _visible_answer(str(step.get("decoded_text") or ""), size)
        cells = list(answer[: size * size]) + [""] * max(0, size * size - len(answer))
        state_rows: list[list[int]] = []
        annotations: list[dict[str, Any]] = []
        for row in range(size):
            state_row = []
            for column in range(size):
                position = row * size + column
                digit = cells[position]
                clue = puzzle[position]
                if not digit:
                    state = 0
                    shown = "<n>"
                    color = "#666666"
                elif clue != "0":
                    state = 1
                    shown = digit
                    color = "#111111" if digit == clue else "#b42318"
                else:
                    correct = solution is None or digit == solution[position]
                    state = 2 if correct else 3
                    shown = digit
                    color = "#167665" if correct else "#b42318"
                state_row.append(state)
                annotations.append(
                    dict(
                        x=column,
                        y=row,
                        text=shown,
                        showarrow=False,
                        font=dict(size=18 if size == 9 else 24, color=color),
                    )
                )
            state_rows.append(state_row)
        return state_rows, annotations

    frames = []
    first_z: list[list[int]] | None = None
    first_annotations: list[dict[str, Any]] = []
    for ordinal, step in enumerate(trace):
        forward = int(step.get("forward_index", ordinal))
        z, annotations = frame_payload(step)
        if first_z is None:
            first_z = z
            first_annotations = annotations
        frames.append(
            go.Frame(
                name=str(forward),
                data=[
                    go.Heatmap(
                        z=z,
                        zmin=0,
                        zmax=3,
                        colorscale=[
                            [0.00, "#d8d6d1"],
                            [0.32, "#d8d6d1"],
                            [0.33, "#ffffff"],
                            [0.65, "#ffffff"],
                            [0.66, "#dcefe8"],
                            [0.98, "#dcefe8"],
                            [0.99, "#f6d7d2"],
                            [1.00, "#f6d7d2"],
                        ],
                        showscale=False,
                        hoverinfo="skip",
                        xgap=1,
                        ygap=1,
                    )
                ],
                layout=go.Layout(annotations=annotations),
            )
        )

    if first_z is None:
        return None
    figure = go.Figure(data=frames[0].data, frames=frames)
    box = int(size**0.5)
    shapes = []
    for index in range(0, size + 1, box):
        coordinate = index - 0.5
        shapes.extend(
            [
                dict(type="line", x0=coordinate, x1=coordinate, y0=-0.5, y1=size - 0.5, line=dict(color="#17201e", width=3)),
                dict(type="line", x0=-0.5, x1=size - 0.5, y0=coordinate, y1=coordinate, line=dict(color="#17201e", width=3)),
            ]
        )
    figure.update_layout(
        title=title,
        annotations=first_annotations,
        height=620 if size == 9 else 470,
        margin=dict(l=30, r=20, t=65, b=70),
        paper_bgcolor="#f6f3eb",
        plot_bgcolor="#fbfaf6",
        font=dict(color="#17201e", family="DejaVu Sans"),
        title_font=dict(size=20, color="#17201e"),
        xaxis=dict(visible=False, range=[-0.5, size - 0.5], constrain="domain"),
        yaxis=dict(visible=False, range=[size - 0.5, -0.5], scaleanchor="x"),
        shapes=shapes,
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0,
                y=-0.08,
                buttons=[
                    dict(label="播放", method="animate", args=[None, {"frame": {"duration": 450, "redraw": True}, "fromcurrent": True}]),
                    dict(label="暂停", method="animate", args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]),
                ],
            )
        ],
        sliders=[
            dict(
                active=0,
                currentvalue=dict(prefix="Forward "),
                pad=dict(t=30),
                steps=[
                    dict(label=frame.name, method="animate", args=[[frame.name], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}])
                    for frame in frames
                ],
            )
        ],
        dragmode=False,
    )
    return figure
