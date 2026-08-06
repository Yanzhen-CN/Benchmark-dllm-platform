from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image


def decode_gif_frames(path: Path) -> tuple[list[str], list[int], int, int]:
    """Decode GIF frames for exact browser-side playback and scrubbing."""
    encoded_frames: list[str] = []
    durations: list[int] = []
    with Image.open(path) as image:
        width, height = image.size
        for frame_index in range(getattr(image, "n_frames", 1)):
            image.seek(frame_index)
            frame = image.convert("RGBA")
            payload = io.BytesIO()
            frame.save(payload, format="PNG")
            encoded_frames.append(
                "data:image/png;base64,"
                + base64.b64encode(payload.getvalue()).decode("ascii")
            )
            durations.append(max(40, int(image.info.get("duration") or 100)))
    return encoded_frames, durations, width, height
