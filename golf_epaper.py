from __future__ import annotations

import importlib
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__:
    from .golf import (
        get_preferred_events,
        get_player_tee_off_time,
        get_round_hole_progress,
        get_scheduled_round_number,
        get_tournament_presentation_data,
        safe_int,
    )
else:
    from golf import (
        get_preferred_events,
        get_player_tee_off_time,
        get_round_hole_progress,
        get_scheduled_round_number,
        get_tournament_presentation_data,
        safe_int,
    )

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
REFRESH_SECONDS = 300
ROWS_TO_DISPLAY = 18
PORTRAIT_WIDTH = DISPLAY_HEIGHT
PORTRAIT_HEIGHT = DISPLAY_WIDTH

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (96, 96, 96)
GREEN = (0, 255, 0)


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


def wrap_text(draw: Any, text: Any, font: Any, max_width: int) -> list[str]:
    """Wrap text to a pixel width, splitting unusually long words if needed."""
    words = str(text or "").split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        while word and draw.textlength(word, font=font) > max_width:
            chunk = ""
            for character in word:
                if draw.textlength(chunk + character, font=font) > max_width and chunk:
                    break
                chunk += character
            lines.append(chunk)
            word = word[len(chunk):]
        current = word

    if current:
        lines.append(current)
    return lines


def draw_scoreboard(
    event: dict[str, Any] | None,
    updated_at: datetime,
    orientation: str = "vertical",
) -> Any:
    """Render a leaderboard for portrait or landscape physical panel mounting."""
    from PIL import Image, ImageDraw, ImageFont

    if orientation not in ("vertical", "horizontal"):
        raise ValueError("orientation must be 'vertical' or 'horizontal'")
    is_vertical = orientation == "vertical"
    canvas_size = (PORTRAIT_WIDTH, PORTRAIT_HEIGHT) if is_vertical else (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    image = Image.new("RGB", canvas_size, GREEN)
    draw = ImageDraw.Draw(image)
    title_font, header_font, row_font = load_fonts()
    tee_time_font = row_font
    text_color = WHITE
    line_color = WHITE
    image_rotation = Image.Transpose.ROTATE_90 if is_vertical else Image.Transpose.ROTATE_180

    if event is None:
        from PIL import ImageFont

        logo_path = Path(__file__).resolve().parent / "images" / "pga_logo.png"
        # Size the cropped artwork to 1.5x its previous visible size.
        logo_width, logo_height = (323, 410) if is_vertical else (245, 312)
        logo = None
        if logo_path.is_file():
            try:
                with Image.open(logo_path) as source:
                    logo = source.convert("RGBA")
                alpha_bounds = logo.getchannel("A").getbbox()
                if alpha_bounds:
                    logo = logo.crop(alpha_bounds)
                logo.thumbnail((logo_width, logo_height), Image.Resampling.LANCZOS)
            except (OSError, ValueError):
                logo = None

        footer_y = image.height - 22
        message = "No tournaments found"
        try:
            message_font = ImageFont.truetype(header_font.path, 22)
        except (AttributeError, OSError):
            try:
                message_font = ImageFont.load_default(size=22)
            except TypeError:
                message_font = header_font
        if logo is not None:
            message_width = draw.textlength(message, font=message_font)
            message_y = footer_y - 72
            image_area_bottom = message_y - 26
            logo_x = (image.width - logo.width) // 2
            logo_y = max(8, (image_area_bottom - logo.height) // 2)
            image.paste(logo, (logo_x, logo_y), logo)
            message_x = (image.width - message_width) / 2
            draw.text((message_x, message_y), message, font=message_font, fill=text_color)
        else:
            message_width = draw.textlength(message, font=message_font)
            draw.text(((image.width - message_width) / 2, image.height // 2), message, font=message_font, fill=text_color)

        draw.text((18, footer_y), f"Updated {updated_at:%I:%M %p}", font=row_font, fill=text_color)
        return image.transpose(image_rotation) if image_rotation is not None else image

    metadata, headers, rows = get_tournament_presentation_data(event, top_n=ROWS_TO_DISPLAY)
    vertical_live_rows = None
    if is_vertical and metadata.get("is_live"):
        competition = event.get("competitions", [{}])[0]
        competitors = sorted(
            competition.get("competitors", []),
            key=lambda competitor: safe_int(competitor.get("order")),
        )[:len(rows)]
        scheduled_round = get_scheduled_round_number(competition)
        tee_times = []
        if competitors:
            with ThreadPoolExecutor(max_workers=min(6, len(competitors))) as executor:
                tee_times = list(
                    executor.map(
                        lambda competitor: get_player_tee_off_time(event, competition, competitor),
                        competitors,
                    )
                )
        vertical_live_rows = []
        for row, competitor, tee_time in zip(rows, competitors, tee_times):
            progress = get_round_hole_progress(competitor, scheduled_round)
            total = f"{row[2]}({progress})" if progress != "-" else row[2]
            today = tee_time or row[3] or "-"
            vertical_live_rows.append([row[0], row[1], total, today])
    title = event.get("shortName") or event.get("name") or "Golf Leaderboard"
    course = metadata.get("course", "")
    location = metadata.get("location", "")
    course_line = f"Course: {course}" if course and course != "N/A" else ""
    location_line = f"Location: {location}" if location and location != "N/A" else ""
    weather = metadata.get("weather", "")
    weather_line = f"Weather: {weather}" if weather and weather != "N/A" else ""

    broadcast = metadata.get("broadcast", "")
    today = metadata.get("today", "")
    context_parts = [part for part in (f"Today: {today}" if today else "", f"TV: {broadcast}" if broadcast else "") if part]
    date_parts = [metadata.get("date_range", "")]
    if metadata.get("status_description"):
        date_parts.append(f"Status: {metadata['status_description']}")
    date_line = "  |  ".join(part for part in date_parts if part)

    if is_vertical:
        content_width = 448
        top_y = 8
        for text, font, line_height, x in (
            (title, title_font, 30, 16),
            (date_line, row_font, 19, 18),
            (course_line, row_font, 19, 18),
            (location_line, row_font, 19, 18),
            (weather_line, row_font, 19, 18),
            ("  |  ".join(context_parts), row_font, 19, 18),
        ):
            if not text:
                continue
            for line in wrap_text(draw, text, font, content_width):
                draw.text((x, top_y), line, font=font, fill=text_color)
                top_y += line_height
        vertical_table_top = top_y + 8
    else:
        content_width = 764
        draw.text((16, 8), shorten_text(draw, title, title_font, content_width), font=title_font, fill=text_color)
        draw.text((18, 40), shorten_text(draw, date_line, row_font, content_width), font=row_font, fill=text_color)
        if course_line:
            draw.text((18, 62), shorten_text(draw, course_line, row_font, content_width), font=row_font, fill=text_color)
        if location_line:
            draw.text((18, 84), shorten_text(draw, location_line, row_font, content_width), font=row_font, fill=text_color)
        if weather_line:
            draw.text((18, 106), shorten_text(draw, weather_line, row_font, content_width), font=row_font, fill=text_color)
        if context_parts:
            context_y = 128
            draw.text((18, context_y), shorten_text(draw, "  |  ".join(context_parts), row_font, content_width), font=row_font, fill=text_color)

    if is_vertical:
        # Portrait layout prioritizes readable names and current scores.
        table_top = vertical_table_top
        if metadata.get("is_live"):
            try:
                tee_time_font = ImageFont.truetype(row_font.path, 12)
            except (AttributeError, OSError):
                try:
                    tee_time_font = ImageFont.load_default(size=12)
                except TypeError:
                    tee_time_font = row_font
            positions = [12, 72, 334, 407]
            labels = ["Pos", "Player", "Tot", "Today"]
            column_widths = [50, 252, 65, 63]
        else:
            positions = [12, 72, 342, 408]
            labels = ["Pos", "Player", "Ctry", "Tot"]
            column_widths = [50, 260, 56, 64]
        row_height = 32
        footer_y = 770
        table_right = 470
    else:
        # Landscape layout also fits each hole score during a live round.
        table_top = 154
        is_live = bool(metadata.get("is_live"))
        if is_live:
            try:
                hole_font = ImageFont.truetype(row_font.path, 12)
            except (AttributeError, OSError):
                try:
                    hole_font = ImageFont.load_default(size=12)
                except TypeError:
                    hole_font = row_font
            positions = [12, 54, 222, 282]
            labels = ["Pos", "Player", "Tot", "Today"]
            column_widths = [38, 160, 56, 60]
            hole_start, hole_step = 350, 24
            labels.extend(str(hole) for hole in range(1, 19))
            positions.extend(hole_start + index * hole_step for index in range(18))
            column_widths.extend([hole_step] * 18)
        else:
            labels = headers[:8]
            positions = [12, 60, 300, 385, 485, 565, 645, 725][:len(labels)]
            column_widths = [42, 230, 78, 92, 72, 72, 72, 64][:len(labels)]
        rows_to_render = 8
        row_height = 31
        footer_y = 456
        table_right = 790

    if is_vertical:
        available_rows = max(0, (footer_y - table_top - 38) // row_height)
        rows_to_render = min(ROWS_TO_DISPLAY, available_rows)

    draw.line((10, table_top + 25, table_right, table_top + 25), fill=line_color, width=2)
    for index, label in enumerate(labels):
        if not is_vertical and metadata.get("is_live") and index >= 4:
            center_x = positions[index] + column_widths[index] / 2
            draw.text((center_x, table_top), label, font=hole_font, fill=text_color, anchor="mt")
        else:
            draw.text((positions[index], table_top), label, font=header_font, fill=text_color)

    if not rows:
        from PIL import ImageFont

        empty_message = "No players found yet"
        try:
            message_font = ImageFont.truetype(header_font.path, 22)
        except (AttributeError, OSError):
            try:
                message_font = ImageFont.load_default(size=22)
            except TypeError:
                message_font = header_font

        logo_path = metadata.get("logo_path") or str(Path(__file__).resolve().parent / "images" / "pga_logo.png")
        logo = None
        try:
            with Image.open(logo_path) as source:
                logo = source.convert("RGBA")
            alpha_bounds = logo.getchannel("A").getbbox()
            if alpha_bounds:
                logo = logo.crop(alpha_bounds)
            logo_bounds = (220, 220) if is_vertical else (180, 130)
            logo.thumbnail(logo_bounds, Image.Resampling.LANCZOS)
        except (OSError, ValueError):
            logo = None

        table_body_top = table_top + 34
        table_body_bottom = footer_y - 20
        message_width = draw.textlength(empty_message, font=message_font)
        message_height = 28
        logo_gap = 14 if logo is not None else 0
        logo_height = logo.height if logo is not None else 0
        group_height = logo_height + logo_gap + message_height
        group_top = table_body_top + max(0, (table_body_bottom - table_body_top - group_height) // 2)

        if logo is not None:
            logo_x = (image.width - logo.width) // 2
            image.paste(logo, (logo_x, group_top), logo)
        message_y = group_top + logo_height + logo_gap
        message_x = (image.width - message_width) / 2
        draw.text((message_x, message_y), empty_message, font=message_font, fill=text_color)

    display_rows = vertical_live_rows if vertical_live_rows is not None else rows
    for row_index, row in enumerate(display_rows[:rows_to_render]):
        y = table_top + 31 + row_index * row_height
        visible_columns = len(positions)
        for column_index, value in enumerate(row[:visible_columns]):
            max_width = column_widths[column_index] - 4
            is_hole_column = not is_vertical and metadata.get("is_live") and column_index >= 4
            is_tee_time = (
                is_vertical
                and metadata.get("is_live")
                and column_index == 3
                and str(value).endswith((" AM", " PM"))
            )
            font = (
                hole_font
                if is_hole_column
                else tee_time_font
                if is_tee_time
                else header_font
                if column_index == 1
                else row_font
            )
            text = shorten_text(draw, value, font, max_width)
            if is_hole_column:
                center_x = positions[column_index] + column_widths[column_index] / 2
                draw.text((center_x, y), text, font=font, fill=text_color, anchor="mt")
            else:
                draw.text((positions[column_index], y), text, font=font, fill=text_color)
        draw.line((10, y + row_height - 4, table_right, y + row_height - 4), fill=line_color, width=1)

    draw.text((18, footer_y), f"Updated {updated_at:%I:%M %p}", font=row_font, fill=text_color)
    return image.transpose(image_rotation) if image_rotation is not None else image


def run_epaper(
    refresh_seconds: int = REFRESH_SECONDS,
    driver_path: str | None = None,
    orientation: str = "vertical",
) -> None:
    """Continuously fetch tournament data and update the PhotoPainter panel."""
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Pillow is required for e-paper rendering; install python3-pil.") from exc

    epd_module = load_driver(driver_path)
    epd = epd_module.EPD()
    initialized = False
    current_index = -1
    last_display_buffer: Any = None
    last_displayed_at = datetime.now()

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

                image = draw_scoreboard(current_event, last_displayed_at, orientation)
                display_buffer = epd.getbuffer(image)
                if display_buffer != last_display_buffer:
                    last_displayed_at = datetime.now()
                    image = draw_scoreboard(current_event, last_displayed_at, orientation)
                    display_buffer = epd.getbuffer(image)
                    epd.display(display_buffer)
                    last_display_buffer = display_buffer
                    print(f"E-paper refreshed at {last_displayed_at:%Y-%m-%d %H:%M:%S}")
                else:
                    print(f"No visible changes at {datetime.now():%Y-%m-%d %H:%M:%S}; skipped refresh")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"Refresh failed; retaining the current e-paper image: {exc}")
            time.sleep(refresh_seconds)
    finally:
        if initialized:
            epd.sleep()
