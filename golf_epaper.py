from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__:
    from .golf import get_preferred_events, get_tournament_presentation_data
else:
    from golf import get_preferred_events, get_tournament_presentation_data

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
REFRESH_SECONDS = 300
ROWS_TO_DISPLAY = 12

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (96, 96, 96)


def load_driver(driver_path: str | None = None) -> Any:
    """Load the PhotoPainter-specific Waveshare e-paper driver."""
    candidates = [
        driver_path,
        os.environ.get("WAVESHARE_EPD_PATH"),
        str(
            Path(__file__).resolve().parent
            / "RPi_Zero_PhotoPainter"
            / "7in3_e-Paper_E"
            / "python"
            / "lib"
        ),
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser()
            if path.is_dir() and str(path.resolve()) not in sys.path:
                sys.path.insert(0, str(path.resolve()))

    try:
        return importlib.import_module("waveshare_epd.epd7in3e")
    except ImportError as exc:
        raise RuntimeError(
            "Could not load the Waveshare PhotoPainter driver. Download the official "
            "RPi Zero PhotoPainter demo, then pass --driver-path pointing to its "
            "7in3_e-Paper_E/python/lib folder (or set WAVESHARE_EPD_PATH)."
        ) from exc


def load_fonts() -> tuple[Any, Any, Any]:
    """Load readable fonts, falling back to Pillow's built-in font."""
    from PIL import ImageFont

    regular_paths = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    bold_paths = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    )

    def find_font(paths: tuple[str, ...], size: int) -> Any:
        for font_path in paths:
            if Path(font_path).is_file():
                return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()

    return find_font(bold_paths, 25), find_font(bold_paths, 15), find_font(regular_paths, 14)


def shorten_text(draw: Any, text: Any, font: Any, max_width: int) -> str:
    """Trim text to fit a pixel width."""
    value = str(text or "")
    if draw.textlength(value, font=font) <= max_width:
        return value
    while value and draw.textlength(value + "…", font=font) > max_width:
        value = value[:-1]
    return value + "…" if value else ""


def draw_scoreboard(event: dict[str, Any] | None, updated_at: datetime) -> Any:
    """Render one tournament as an 800x480 image for the E6 panel."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    title_font, header_font, row_font = load_fonts()
    small_font = row_font

    if event is None:
        draw.text((20, 24), "Golf Leaderboard", font=title_font, fill=BLACK)
        draw.text((20, 86), "No tournament data is available.", font=header_font, fill=BLACK)
        draw.text((20, 444), f"Updated {updated_at:%I:%M %p}", font=row_font, fill=GRAY)
        return image

    metadata, headers, rows = get_tournament_presentation_data(event, top_n=ROWS_TO_DISPLAY)
    title = event.get("shortName") or event.get("name") or "Golf Leaderboard"
    draw.text((18, 10), shorten_text(draw, title, title_font, 764), font=title_font, fill=BLUE)
    draw.text((20, 44), f"{metadata.get('date_range', '')}  |  {metadata.get('status', '')}", font=small_font, fill=BLACK)

    location_parts = [metadata.get("course", ""), metadata.get("location", "")]
    location_line = "  |  ".join(str(part) for part in location_parts if part and part != "N/A")
    weather = metadata.get("weather", "")
    if weather and weather != "N/A":
        location_line = f"{location_line}  |  {weather}" if location_line else weather
    draw.text((20, 66), shorten_text(draw, location_line, small_font, 760), font=small_font, fill=BLACK)

    broadcast = metadata.get("broadcast", "")
    today = metadata.get("today", "")
    context_parts = [part for part in (f"Today: {today}" if today else "", f"TV: {broadcast}" if broadcast else "") if part]
    if context_parts:
        draw.text((20, 88), shorten_text(draw, "  |  ".join(context_parts), small_font, 760), font=small_font, fill=BLACK)

    table_top = 116
    is_live = bool(metadata.get("is_live"))
    if is_live:
        # Hole columns are condensed to keep all 18 visible at the panel's width.
        positions = [12, 62, 258, 318]
        labels = ["Pos", "Player", "Tot", "Today"]
        hole_start, hole_step = 385, 22
        labels.extend(str(hole) for hole in range(1, 19))
        positions.extend(hole_start + index * hole_step for index in range(18))
        column_widths = [42, 188, 54, 60] + [hole_step] * 18
    else:
        labels = headers[:8]
        positions = [12, 62, 310, 390, 490, 565, 640, 715][:len(labels)]
        column_widths = [46, 240, 75, 92, 70, 70, 70, 70][:len(labels)]

    draw.line((10, table_top + 23, 790, table_top + 23), fill=BLACK, width=2)
    for index, label in enumerate(labels):
        draw.text((positions[index], table_top), str(label), font=header_font, fill=BLACK)

    row_height = 27
    for row_index, row in enumerate(rows[:ROWS_TO_DISPLAY]):
        y = table_top + 29 + row_index * row_height
        if row_index % 2 == 1:
            draw.rectangle((10, y - 2, 790, y + row_height - 2), fill=(238, 238, 238))
        for column_index, value in enumerate(row[:len(positions)]):
            if is_live and column_index >= 4:
                max_width = column_widths[column_index] - 2
                font = row_font
            else:
                max_width = column_widths[column_index] - 4
                font = row_font
            text = shorten_text(draw, value, font, max_width)
            color = RED if column_index == 0 and str(value).strip() in ("1", "T1") else BLACK
            draw.text((positions[column_index], y), text, font=font, fill=color)

    footer_y = min(table_top + 29 + ROWS_TO_DISPLAY * row_height, 456)
    draw.line((10, footer_y, 790, footer_y), fill=GRAY, width=1)
    draw.text((20, 459), f"Updated {updated_at:%I:%M %p}", font=row_font, fill=BLACK)
    return image


def run_epaper(refresh_seconds: int = REFRESH_SECONDS, driver_path: str | None = None) -> None:
    """Continuously fetch tournament data and update the PhotoPainter panel."""
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Pillow is required for e-paper rendering; install python3-pil.") from exc

    epd_module = load_driver(driver_path)
    epd = epd_module.EPD()
    initialized = False
    current_index = -1

    try:
        if epd.init() != 0:
            raise RuntimeError("The e-paper driver could not initialize the PhotoPainter panel.")
        initialized = True

        while True:
            try:
                events = get_preferred_events()
                if events:
                    current_index = (current_index + 1) % len(events)
                    current_event = events[current_index]
                else:
                    current_event = None
                image = draw_scoreboard(current_event, datetime.now())
                epd.display(epd.getbuffer(image))
                print(f"E-paper refreshed at {datetime.now():%Y-%m-%d %H:%M:%S}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"Refresh failed; retaining the current e-paper image: {exc}")
            time.sleep(refresh_seconds)
    finally:
        if initialized:
            epd.sleep()
