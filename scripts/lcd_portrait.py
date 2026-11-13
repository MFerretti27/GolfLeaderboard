"""Apply the requested orientation to the active Wayland LCD before startup."""

import argparse
import os
import re
import subprocess
import sys


def parse_outputs(output: str) -> list[dict[str, str]]:
    displays = []
    current = None
    for line in output.splitlines():
        if line and not line[0].isspace():
            current = {"name": line.split()[0]}
            displays.append(current)
        elif current is not None:
            text = line.strip()
            if text.startswith("Enabled:"):
                current["enabled"] = text.split(":", 1)[1].strip()
            elif text.startswith("Transform:"):
                current["transform"] = text.split(":", 1)[1].strip()
            elif "(current)" in text or ", current)" in text:
                match = re.match(r"(\d+)x(\d+)\s+px,", text)
                if match:
                    current["width"], current["height"] = match.groups()
    return [display for display in displays if display.get("enabled") == "yes"]


def ensure_orientation(orientation: str = "vertical") -> None:
    if orientation not in ("vertical", "horizontal"):
        raise ValueError(f"Unsupported LCD orientation: {orientation}")
    description = "portrait" if orientation == "vertical" else "landscape"
    if not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "Automatic LCD rotation requires Wayland. On X11, rotate the display "
            f"in Raspberry Pi OS display settings; the app will use {description} layout.",
            file=sys.stderr,
        )
        return
    result = subprocess.run(["wlr-randr"], check=True, capture_output=True, text=True)
    displays = parse_outputs(result.stdout)
    if len(displays) != 1:
        raise RuntimeError(
            f"Expected one enabled LCD output, found {len(displays)}. "
            f"Connect only the leaderboard display before starting {description} mode."
        )
    display = displays[0]
    if not all(key in display for key in ("width", "height", "transform")):
        raise RuntimeError(f"Cannot determine display geometry: {display['name']}")
    width, height = int(display["width"]), int(display["height"])
    transform = display["transform"]
    if transform not in (
        "normal", "90", "180", "270",
        "flipped", "flipped-90", "flipped-180", "flipped-270",
    ):
        raise RuntimeError(f"Unsupported display transform: {transform}")
    if transform in ("90", "270", "flipped-90", "flipped-270"):
        width, height = height, width
    if (height >= width if orientation == "vertical" else width >= height):
        print(f"LCD output {display['name']} is already {description}; keeping {transform}.")
        return
    native_portrait = int(display["height"]) > int(display["width"])
    target_portrait = orientation == "vertical"
    target = "normal" if native_portrait == target_portrait else "270"
    subprocess.run(
        ["wlr-randr", "--output", display["name"], "--transform", target],
        check=True,
    )
    verified = subprocess.run(["wlr-randr"], check=True, capture_output=True, text=True)
    updated = parse_outputs(verified.stdout)
    if not any(
        item["name"] == display["name"] and item.get("transform") == target
        for item in updated
    ):
        raise RuntimeError(f"{description.capitalize()} rotation was not applied to {display['name']}")
    print(f"LCD output {display['name']} rotated to {target}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orientation", choices=("vertical", "horizontal"), default="vertical")
    ensure_orientation(parser.parse_args().orientation)
