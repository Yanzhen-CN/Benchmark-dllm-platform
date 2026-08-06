from __future__ import annotations

from PIL import Image

from platform_core.gif_frames import decode_gif_frames


def test_decode_gif_frames_preserves_steps_and_durations(tmp_path):
    path = tmp_path / "trace.gif"
    frames = [
        Image.new("RGB", (20, 12), "red"),
        Image.new("RGB", (20, 12), "blue"),
    ]
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=[120, 240],
        loop=0,
    )

    encoded, durations, width, height = decode_gif_frames(path)

    assert len(encoded) == 2
    assert all(item.startswith("data:image/png;base64,") for item in encoded)
    assert durations == [120, 240]
    assert (width, height) == (20, 12)
