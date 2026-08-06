from __future__ import annotations

from pathlib import Path


def test_platform_keeps_four_focused_pages():
    pages = Path(__file__).parents[1] / "pages"
    assert sorted(path.name for path in pages.glob("*.py")) == [
        "1_Score_Overview.py",
        "3_Performance.py",
        "4_Trace.py",
        "5_Run.py",
    ]
