"""Render desktop images with the Horizontal DepthFlow preset.

Inputs:
- ~/Desktop/DepthFlow (jpg, jpeg, png)

Outputs:
- ~/Desktop/Export/<input-stem>.mp4
"""

import argparse
import math
from pathlib import Path
from typing import Any, cast

from attrs import define
from depthflow.estimators.anything import DepthAnythingV2
from depthflow.scene import DepthScene


# --------------------------------------------------------------------------- #
# Centralized settings: tweak these values to tune the output.

INPUTS_DIR = Path.home() / "Desktop" / "DepthFlow"  # Folder with source images.

IMAGE_EXTENSIONS = ("jpg", "jpeg", "png")  # File types to include: "jpg", "jpeg", "png".

DEPTH_MODEL = DepthAnythingV2.Model.Large  # Depth model: Small, Base, Large, Giant.

# Change only this value to switch style quickly.
ACTIVE_PRESET = "horizontal"  # Preset: "horizontal", "vertical", "zoom" or "dolly".

# Horizontal style settings.
H_LOOP_COUNT = 10  # Number of horizontal swings.
H_LOOP_TIME_SECONDS = 0.3  # Duration of one horizontal swing.
H_MOTION_AMPLITUDE = 0.10  # Strength of left-right movement.
H_MOTION_SPEED = 0.65  # Motion pacing multiplier.
H_ISOMETRIC = 0.45  # Perspective angle amount.
H_STEADY = 0.24  # How anchored the subject feels.

# Vertical style settings.
V_LOOP_COUNT = 10  # Number of vertical swings.
V_LOOP_TIME_SECONDS = 0.3  # Duration of one vertical swing.
V_MOTION_AMPLITUDE = 0.10  # Strength of up-down movement.
V_MOTION_SPEED = 0.65  # Motion pacing multiplier.
V_ISOMETRIC = 0.45  # Perspective angle amount.
V_STEADY = 0.24  # How anchored the subject feels.

# Zoom style settings.
Z_LOOP_COUNT = 4  # Number of zoom pulses.
Z_LOOP_TIME_SECONDS = .75  # Duration of one zoom pulse.
Z_HEIGHT = 0.15  # Zoom intensity for the zoom preset.
Z_ISOMETRIC = 0.15  # Perspective angle amount.
Z_STEADY = 0.20  # How anchored the subject feels.

# Dolly zoom settings.
D_LOOP_COUNT = 4  # Number of dolly cycles.
D_LOOP_TIME_SECONDS = .75  # Duration of one dolly cycle.
D_HEIGHT = 0.10  # Main dolly intensity: stronger depth movement.
D_STEADY = 0.35  # How anchored the subject feels.
D_FOCUS = 0.35  # Depth plane used as the focus anchor.
D_ZOOM = 0.99  # Base framing/zoom level.

VIDEO_FPS = 24  # Output frames per second.
VIDEO_PRESET = "slow"  # Encoder preset: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow.
VIDEO_CRF = 20  # Lower = sharper image, larger files.
VIDEO_PROFILE = "high"  # H.264 profile: baseline, main, high, high10, high422, high444p.
VIDEO_TUNE = "film"  # Encoder tune: film, animation, grain, stillimage, fastdecode, zerolatency.

MAX_LONG_SIDE = 3000  # Set None for native size, or cap longest side.

# --------------------------------------------------------------------------- #

@define
class Horizontal(DepthScene):
    """Simple horizontal parallax preset."""

    def update(self) -> None:
        phase = self.cycle * H_MOTION_SPEED * H_LOOP_COUNT
        self.state.offset = (H_MOTION_AMPLITUDE * math.sin(phase), 0.0)
        self.state.isometric = H_ISOMETRIC
        self.state.steady = H_STEADY


@define
class Vertical(DepthScene):
    """Simple vertical parallax preset."""

    def update(self) -> None:
        phase = self.cycle * V_MOTION_SPEED * V_LOOP_COUNT
        self.state.offset = (0.0, V_MOTION_AMPLITUDE * math.sin(phase))
        self.state.isometric = V_ISOMETRIC
        self.state.steady = V_STEADY


@define
class Zoom(DepthScene):
    """Simple zoom in/out preset."""

    def update(self) -> None:
        # Exactly Z_LOOP_COUNT loops over total video duration.
        phase = self.cycle * Z_LOOP_COUNT
        self.state.offset = (0.0, 0.0)
        self.state.height = Z_HEIGHT * (math.sin(phase / 2.0) ** 2.0)
        self.state.isometric = Z_ISOMETRIC
        self.state.steady = Z_STEADY


@define
class Dolly(DepthScene):
    """Simple dolly zoom preset."""

    def update(self) -> None:
        phase = self.cycle * D_LOOP_COUNT
        self.state.height = D_HEIGHT
        self.state.steady = D_STEADY
        self.state.focus = D_FOCUS
        self.state.zoom = D_ZOOM
        self.state.isometric = 0.5 * (1.0 - math.cos(phase))


def _even(value: int) -> int:
    return value if (value % 2 == 0) else (value - 1)


def _fit_resolution(width: int, height: int, max_long_side: int | None = MAX_LONG_SIDE) -> tuple[int, int]:
    scale = 1.0 if (max_long_side is None) else min(1.0, max_long_side / max(width, height))
    out_w = max(2, _even(int(round(width * scale))))
    out_h = max(2, _even(int(round(height * scale))))
    return (out_w, out_h)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render all images in an input directory with the active preset. "
            "Outputs are written to a sibling 'Export' folder."
        )
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        default=INPUTS_DIR,
        help="Input folder with images (default: ~/Desktop/DepthFlow)",
    )
    args = parser.parse_args()

    inputs = args.inputs.expanduser().resolve()
    outputs = inputs.parent / "Export"

    if ACTIVE_PRESET == "horizontal":
        scene: DepthScene = Horizontal(backend="headless")
        total_time_seconds = H_LOOP_TIME_SECONDS * H_LOOP_COUNT
    elif ACTIVE_PRESET == "vertical":
        scene = Vertical(backend="headless")
        total_time_seconds = V_LOOP_TIME_SECONDS * V_LOOP_COUNT
    elif ACTIVE_PRESET == "zoom":
        scene = Zoom(backend="headless")
        total_time_seconds = Z_LOOP_TIME_SECONDS * Z_LOOP_COUNT
    elif ACTIVE_PRESET == "dolly":
        scene = Dolly(backend="headless")
        total_time_seconds = D_LOOP_TIME_SECONDS * D_LOOP_COUNT
    else:
        raise SystemExit("ACTIVE_PRESET must be 'horizontal', 'vertical', 'zoom' or 'dolly'")

    if not inputs.exists() or not inputs.is_dir():
        raise SystemExit(f"Input folder not found: {inputs}")

    files = []
    for ext in IMAGE_EXTENSIONS:
        files.extend(sorted(inputs.glob(f"*.{ext}")))

    if not files:
        raise SystemExit(f"No images found in: {inputs}")

    outputs.mkdir(parents=True, exist_ok=True)

    scene.estimator = DepthAnythingV2(model=DEPTH_MODEL)
    cast(Any, scene.ffmpeg).h264(
        preset=VIDEO_PRESET,
        crf=VIDEO_CRF,
        profile=VIDEO_PROFILE,
        tune=VIDEO_TUNE,
    )

    for image in files:
        output = outputs / f"{image.stem}.mp4"
        print(f"Rendering: {image.name} -> {output.name}")
        scene.input(image=image)

        image_width, image_height = scene.image.size
        out_width, out_height = _fit_resolution(image_width, image_height)

        scene.main(
            output=output,
            time=total_time_seconds,
            fps=VIDEO_FPS,
            width=out_width,
            height=out_height,
            ratio=(image_width / image_height),
        )

    print(f"Done. Exported {len(files)} video(s) to: {outputs}")


if __name__ == "__main__":
    main()