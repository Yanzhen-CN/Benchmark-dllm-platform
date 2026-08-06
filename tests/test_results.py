from __future__ import annotations

from platform_core.results import load_trace_assets


def test_load_trace_assets_includes_model_agnostic_sudoku_token_gif(tmp_path):
    path = (
        tmp_path
        / "visualization_output"
        / "llada2_1"
        / "qmode"
        / "sudoku4_1shot"
        / "sudoku4-d1-0004_token_trace.gif"
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(b"GIF89a")

    assets = load_trace_assets(tmp_path)

    assert len(assets) == 1
    assert assets[0]["model"] == "llada2_1/qmode"
    assert assets[0]["dataset"] == "sudoku4_1shot"
    assert assets[0]["sample"] == "sudoku4-d1-0004"
