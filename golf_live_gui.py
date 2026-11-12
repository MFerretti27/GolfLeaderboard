from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any
from datetime import datetime
from pathlib import Path

if __package__:
    from .golf import get_player_tee_off_time, get_preferred_events, get_round_hole_progress, get_scheduled_round_number, get_tournament_presentation_data, safe_int, select_display_event
else:
    from golf import get_player_tee_off_time, get_preferred_events, get_round_hole_progress, get_scheduled_round_number, get_tournament_presentation_data, safe_int, select_display_event

WINDOW_SIZE = (1400, 900)
AUTO_REFRESH_MS = 30000
TOP_N_DISPLAY: int | None = 25
MAX_GRID_COLUMNS = 22
MAX_GRID_ROWS = 25
SCREEN_ORIENTATION: str | None = None
GRID_WIDTH_SCALE = 1.0
GRID_CHARACTER_WIDTH_PIXELS = 0.0
PLAYER_NAME_COLUMN_WIDTH = 18
LOGO_CACHE: dict[tuple[str, tuple[int, int] | None], bytes] = {}
THEME = "DarkGreen5"
WINDOW_TITLE = "Golf Live Tournaments"
DEFAULT_TITLE = "Golf Leaderboard"
TITLE_TEXT = "Golf Leaderboard"
TIME_FORMAT = "%I:%M %p"
BASE_SCREEN_SIZE = (1400, 900)

FONT_FAMILY = "Helvetica"
FONT_GRID_SIZE = 16
FONT_META_SIZE = 16
FONT_INFO_SIZE = 14
FONT_TITLE_SIZE = 30

FONT_GRID_HEADER = (FONT_FAMILY, FONT_GRID_SIZE, "bold")
FONT_GRID_CELL = (FONT_FAMILY, FONT_GRID_SIZE)
FONT_TITLE = (FONT_FAMILY, FONT_TITLE_SIZE, "bold")
FONT_META = (FONT_FAMILY, FONT_META_SIZE)
FONT_INFO = (FONT_FAMILY, FONT_INFO_SIZE)
FONT_INFO_BOLD = (FONT_FAMILY, FONT_INFO_SIZE, "bold")
FONT_LAST_UPDATE = (FONT_FAMILY, FONT_META_SIZE)

PAD_LOGO = (0, 0)
PAD_CELL = (1, 1)
PAD_TOURNAMENT_INFO = (0, 8)
PAD_LEADERBOARD = (0, 4)

ROW_BG_EVEN = "#f5f5f5"
ROW_BG_ODD = "#ebebeb"
ROW_BG_HEADER = ROW_BG_EVEN
TEXT_COLOR_PRIMARY = "#f7f7f7"
TEXT_COLOR_GRID = "#111111"
Sg: Any = None


def configure_display(
    mode: str,
    size: tuple[int, int] | None = None,
    refresh_seconds: int | None = None,
    orientation: str | None = None,
) -> None:
    """Apply screen dimensions and visual settings for the dashboard."""
    global WINDOW_SIZE, AUTO_REFRESH_MS, TOP_N_DISPLAY, MAX_GRID_COLUMNS, MAX_GRID_ROWS, SCREEN_ORIENTATION
    global GRID_WIDTH_SCALE, GRID_CHARACTER_WIDTH_PIXELS, PLAYER_NAME_COLUMN_WIDTH
    global THEME, FONT_GRID_SIZE, FONT_META_SIZE, FONT_INFO_SIZE, FONT_TITLE_SIZE
    global FONT_GRID_HEADER, FONT_GRID_CELL, FONT_TITLE, FONT_META, FONT_INFO, FONT_INFO_BOLD
    global FONT_LAST_UPDATE, ROW_BG_EVEN, ROW_BG_ODD, ROW_BG_HEADER
    global TEXT_COLOR_PRIMARY, TEXT_COLOR_GRID

    if mode == "eink":
        WINDOW_SIZE = size or (800, 600)
        AUTO_REFRESH_MS = (refresh_seconds if refresh_seconds is not None else 300) * 1000
        TOP_N_DISPLAY = 12
        MAX_GRID_COLUMNS = 22
        MAX_GRID_ROWS = 12
        GRID_WIDTH_SCALE = 1.0
        THEME = "LightGrey1"
        FONT_GRID_SIZE, FONT_META_SIZE, FONT_INFO_SIZE, FONT_TITLE_SIZE = 14, 14, 14, 24
        ROW_BG_EVEN = ROW_BG_HEADER = "#ffffff"
        ROW_BG_ODD = "#e6e6e6"
        TEXT_COLOR_PRIMARY = TEXT_COLOR_GRID = "#000000"
    else:
        SCREEN_ORIENTATION = orientation
        GRID_CHARACTER_WIDTH_PIXELS = 0.0
        PLAYER_NAME_COLUMN_WIDTH = 18
        screen_width, screen_height = size or get_screen_window_size()
        WINDOW_SIZE = (screen_width, screen_height)
        GRID_WIDTH_SCALE = max(0.55, min(1.0, screen_width / 1200))
        AUTO_REFRESH_MS = (refresh_seconds if refresh_seconds is not None else 30) * 1000
        TOP_N_DISPLAY = 25
        MAX_GRID_COLUMNS = 7 if orientation == "vertical" else 22
        scale = max(0.65, min(1.3, min(screen_width / BASE_SCREEN_SIZE[0], screen_height / BASE_SCREEN_SIZE[1])))
        FONT_GRID_SIZE = max(10, round(16 * scale))
        FONT_META_SIZE = max(10, round(16 * scale))
        FONT_INFO_SIZE = max(9, round(14 * scale))
        FONT_TITLE_SIZE = max(18, round(30 * scale))
        MAX_GRID_ROWS = 25
        THEME = "DarkGreen5"
        ROW_BG_EVEN = "#f5f5f5"
        ROW_BG_ODD = "#ebebeb"
        ROW_BG_HEADER = ROW_BG_EVEN
        TEXT_COLOR_PRIMARY = "#f7f7f7"
        TEXT_COLOR_GRID = "#111111"

    FONT_GRID_HEADER = (FONT_FAMILY, FONT_GRID_SIZE, "bold")
    FONT_GRID_CELL = (FONT_FAMILY, FONT_GRID_SIZE)
    FONT_TITLE = (FONT_FAMILY, FONT_TITLE_SIZE, "bold")
    FONT_META = (FONT_FAMILY, FONT_META_SIZE)
    FONT_INFO = (FONT_FAMILY, FONT_INFO_SIZE)
    FONT_INFO_BOLD = (FONT_FAMILY, FONT_INFO_SIZE, "bold")
    FONT_LAST_UPDATE = (FONT_FAMILY, FONT_META_SIZE)


def get_screen_window_size() -> tuple[int, int]:
    """Detect the primary display size and reserve space for desktop chrome."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()
        return max(320, screen_width), max(240, screen_height)
    except Exception:
        return BASE_SCREEN_SIZE


def parse_window_size(value: str) -> tuple[int, int]:
    """Parse a WIDTHxHEIGHT window size supplied on the command line."""
    try:
        width_text, height_text = value.lower().split("x", maxsplit=1)
        width, height = int(width_text), int(height_text)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("size must be formatted as WIDTHxHEIGHT, for example 800x600") from None
    if width < 320 or height < 240:
        raise argparse.ArgumentTypeError("window size must be at least 320x240")
    return width, height


def fetch_logo_bytes(logo_path: str, max_size: tuple[int, int] | None = None) -> bytes | None:
    """Load and cache logo image bytes from a local file path."""
    if not logo_path:
        return None
    cache_key = (logo_path, max_size)
    if cache_key in LOGO_CACHE:
        return LOGO_CACHE[cache_key]

    path_obj = Path(logo_path)
    if not path_obj.exists() or not path_obj.is_file():
        return None

    try:
        content = path_obj.read_bytes()
        if max_size is not None:
            from PIL import Image

            with Image.open(BytesIO(content)) as source:
                image = source.convert("RGBA")
            bounds = image.getchannel("A").getbbox()
            if bounds:
                image = image.crop(bounds)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="PNG")
            content = output.getvalue()
        LOGO_CACHE[cache_key] = content
        return content
    except OSError:
        return None


def update_empty_leaderboard(
    window: Any, visible: bool, logo_path: str = "", message: str = "No players found yet"
) -> None:
    """Show an empty-state message and local logo without replacing event details."""
    logo_bytes = None
    if visible:
        fallback_path = str(Path(__file__).resolve().parent / "images" / "pga_logo.png")
        for candidate in (logo_path, fallback_path):
            logo_bytes = fetch_logo_bytes(candidate, (180, 130))
            if logo_bytes:
                break
    window["EMPTY_LEADERBOARD_LOGO"].update(data=logo_bytes, visible=bool(logo_bytes))
    window["EMPTY_LEADERBOARD_MESSAGE"].update(message, visible=visible)


def get_column_width(column_index: int) -> int:
    """Return a fixed character width for each leaderboard column."""
    if column_index == 1:
        return PLAYER_NAME_COLUMN_WIDTH

    return get_base_column_width(column_index)


def get_base_column_width(column_index: int) -> int:
    """Return the default character width before expanding the player column."""
    if SCREEN_ORIENTATION == "vertical":
        base_widths = (5, 24, 6, 10, 6, 6, 6)
        minimum_widths = (3, 8, 5, 10, 3, 3, 3)
    else:
        base_widths = (5, 18, 6, 10) + (4,) * 18
        minimum_widths = (4, 8, 5, 10) + (2,) * 18
    if column_index < len(base_widths):
        return max(minimum_widths[column_index], round(base_widths[column_index] * GRID_WIDTH_SCALE))

    if SCREEN_ORIENTATION == "vertical":
        return 6
    return 4


def fit_grid_value(value: Any, column_index: int) -> str:
    """Add an ellipsis to player names that are too long for the grid cell."""
    text = str(value)
    if column_index != 1:
        return text

    max_characters = max(3, get_column_width(column_index) - 2)
    if len(text) <= max_characters:
        return text
    return f"{text[:max_characters - 3].rstrip()}..."


def get_visible_column_count(headers: list[str], screen_width: int) -> int:
    """Return the number of grid columns that fit within the LCD width."""
    available_width = max(0, screen_width - 80)
    character_width = GRID_CHARACTER_WIDTH_PIXELS or FONT_GRID_SIZE * 0.62
    used_width = 0.0
    visible_count = 0
    for column_index, _ in enumerate(headers[:MAX_GRID_COLUMNS]):
        column_width = get_base_column_width(column_index) * character_width + 4
        if visible_count and used_width + column_width > available_width:
            break
        used_width += column_width
        visible_count += 1
    return max(1, visible_count)


def get_player_name_column_width(visible_column_count: int, screen_width: int) -> int:
    """Use the width left by the other visible columns for player names."""
    available_width = max(0, screen_width - 80)
    character_width = GRID_CHARACTER_WIDTH_PIXELS or FONT_GRID_SIZE * 0.62
    fixed_width = sum(
        get_base_column_width(column_index) * character_width + 4
        for column_index in range(visible_column_count)
        if column_index != 1
    )
    remaining_width = available_width - fixed_width - 4
    return max(8, int(remaining_width / character_width))


def fit_visible_grid_rows(window: Any, column_count: int, row_count: int) -> int:
    """Hide rows whose rendered cells extend outside the leaderboard viewport."""
    window.TKroot.update_idletasks()
    viewport = window["LEADERBOARD_GRID"].Widget
    bottom = viewport.winfo_rooty() + viewport.winfo_height()
    ancestor = viewport.master
    while ancestor is not None:
        bottom = min(bottom, ancestor.winfo_rooty() + ancestor.winfo_height())
        # FreeSimpleGUI's hidden Tk parent is not part of this window's viewport.
        if ancestor == window.TKroot:
            break
        ancestor = ancestor.master

    visible_rows = 0
    for row_index in range(row_count):
        cells = [window[f"CELL_{row_index}_{column_index}"] for column_index in range(column_count)]
        if not cells or any(not cell.Widget.winfo_ismapped() for cell in cells):
            break
        row_bottom = max(
            (
                cell.Widget.winfo_rooty()
                + max(cell.Widget.winfo_height(), cell.Widget.winfo_reqheight())
                + PAD_CELL[1]
                for cell in cells
            ),
            default=bottom + 1,
        )
        if row_bottom > bottom:
            break
        visible_rows += 1

    for row_index in range(visible_rows, row_count):
        for column_index in range(column_count):
            window[f"CELL_{row_index}_{column_index}"].update(visible=False)
    window.TKroot.update_idletasks()
    return visible_rows


def build_grid_layout() -> list[list[Any]]:
    """Create fixed leaderboard header and row cells."""
    header_row = []
    for column_index in range(MAX_GRID_COLUMNS):
        justification = "left" if column_index == 1 else "center"
        header_row.append(
            Sg.Text(
                "",
                key=f"HEADER_{column_index}",
                size=(get_column_width(column_index), 1),
                justification=justification,
                font=FONT_GRID_HEADER,
                text_color=TEXT_COLOR_GRID,
                pad=PAD_CELL,
                relief=Sg.RELIEF_SOLID,
                background_color=ROW_BG_HEADER,
                expand_x=column_index == 1,
                expand_y=True,
            )
        )

    rows = [header_row]
    for row_index in range(MAX_GRID_ROWS):
        row = []
        for column_index in range(MAX_GRID_COLUMNS):
            justification = "left" if column_index == 1 else "center"
            row.append(
                Sg.Text(
                    "",
                    key=f"CELL_{row_index}_{column_index}",
                    size=(get_column_width(column_index), 1),
                    justification=justification,
                    font=FONT_GRID_CELL,
                    text_color=TEXT_COLOR_GRID,
                    pad=PAD_CELL,
                    relief=Sg.RELIEF_SOLID,
                    background_color=ROW_BG_EVEN if row_index % 2 == 0 else ROW_BG_ODD,
                    expand_x=column_index == 1,
                    expand_y=True,
                )
            )
        rows.append(row)
    return rows


def build_main_layout() -> list[list[Any]]:
    """Create the LCD leaderboard layout."""
    Sg.theme(THEME)

    if SCREEN_ORIENTATION == "vertical":
        title_rows = [
            [Sg.Push(), Sg.Image(key="TOURNAMENT_LOGO", visible=False, pad=PAD_LOGO), Sg.Push()],
            [Sg.Text(
                TITLE_TEXT, font=FONT_TITLE, text_color=TEXT_COLOR_PRIMARY,
                key="TITLE", size=(1, None), expand_x=True, justification="center",
            )],
        ]
    else:
        title_rows = [
            [
                Sg.Image(key="TOURNAMENT_LOGO", visible=False, pad=PAD_LOGO),
                Sg.Push(),
                Sg.Text(TITLE_TEXT, font=FONT_TITLE, text_color=TEXT_COLOR_PRIMARY, key="TITLE"),
                Sg.Push(),
            ],
        ]

    return title_rows + [
        [
            Sg.Text("", key="DATE_RANGE", font=FONT_META, text_color=TEXT_COLOR_PRIMARY),
            Sg.Push(),
            Sg.Text("", key="LAST_UPDATE", font=FONT_LAST_UPDATE, text_color=TEXT_COLOR_PRIMARY),
        ],
        [
            Sg.Frame(
                "Tournament Info",
                [
                    [Sg.Text("", key="STATUS", font=FONT_INFO, text_color=TEXT_COLOR_PRIMARY)],
                    [Sg.Text("", key="COURSE", font=FONT_INFO, text_color=TEXT_COLOR_PRIMARY)],
                    [Sg.Text("", key="LOCATION", font=FONT_INFO, text_color=TEXT_COLOR_PRIMARY)],
                    [Sg.Text("", key="WEATHER", font=FONT_INFO, text_color=TEXT_COLOR_PRIMARY)],
                    [Sg.Text("", key="BROADCAST", font=FONT_INFO, text_color=TEXT_COLOR_PRIMARY)],
                    [Sg.Text("", key="TODAY", font=FONT_INFO_BOLD, text_color=TEXT_COLOR_PRIMARY)],
                ],
                expand_x=True,
                font=FONT_INFO_BOLD,
                pad=PAD_TOURNAMENT_INFO,
            )
        ],
        [
            Sg.Frame(
                "Leaderboard",
                [
                    [Sg.Push(), Sg.Image(key="EMPTY_LEADERBOARD_LOGO", visible=False), Sg.Push()],
                    [
                        Sg.Text(
                            "No players found yet",
                            key="EMPTY_LEADERBOARD_MESSAGE",
                            font=FONT_INFO_BOLD,
                            text_color=TEXT_COLOR_PRIMARY,
                            justification="center",
                            expand_x=True,
                            visible=False,
                        )
                    ],
                    [Sg.Column(build_grid_layout(), key="LEADERBOARD_GRID", expand_x=True, expand_y=True, pad=(0, 0))],
                ],
                expand_x=True,
                expand_y=True,
                pad=PAD_LEADERBOARD,
            )
        ],
    ]


def fit_lcd_content_width(window: Any, column_count: int) -> None:
    """Wrap the portrait title and let visible grid cells fill their row."""
    window.TKroot.update_idletasks()
    if SCREEN_ORIENTATION == "vertical":
        title = window["TITLE"].Widget
        title.configure(wraplength=max(1, title.winfo_width() - 12), height=0)

    for row_index in range(-1, MAX_GRID_ROWS):
        prefix = "HEADER" if row_index == -1 else f"CELL_{row_index}"
        for column_index in range(column_count):
            element = window[f"{prefix}_{column_index}"]
            element.expand(expand_x=True, expand_row=False)
    window.TKroot.update_idletasks()


def add_hole_progress_to_live_rows(event: dict[str, Any], rows: list[list[str]]) -> None:
    """Append current-round holes completed to LCD Today scores."""
    competition = event.get("competitions", [{}])[0]
    round_number = get_scheduled_round_number(competition)
    competitors = sorted(
        competition.get("competitors", []),
        key=lambda competitor: safe_int(competitor.get("order")),
    )
    for row, competitor in zip(rows, competitors):
        if len(row) > 3 and row[3] not in ("", "-"):
            progress = get_round_hole_progress(competitor, round_number)
            if progress != "-":
                row[3] = f"{row[3]} ({progress})"


def add_tee_times_to_live_rows(event: dict[str, Any], rows: list[list[str]]) -> None:
    """Fill blank Today cells with tee times for players who have not started."""
    if not rows:
        return

    competition = event.get("competitions", [{}])[0]
    competitors = sorted(
        competition.get("competitors", []),
        key=lambda competitor: safe_int(competitor.get("order")),
    )[:len(rows)]
    pending = [
        (row_index, competitors[row_index])
        for row_index, row in enumerate(rows)
        if len(row) > 3 and row[3] == "-" and row_index < len(competitors)
    ]
    if not pending:
        return

    with ThreadPoolExecutor(max_workers=min(6, len(pending))) as executor:
        tee_times = executor.map(
            lambda item: get_player_tee_off_time(event, competition, item[1]),
            pending,
        )
        for (row_index, _), tee_time in zip(pending, tee_times):
            if tee_time:
                rows[row_index][3] = tee_time


def run_gui(
    display: str = "screen",
    size: tuple[int, int] | None = None,
    refresh_seconds: int | None = None,
    orientation: str | None = None,
) -> None:
    """Run the golf live tournament LCD dashboard."""
    global Sg
    try:
        import FreeSimpleGUI as Sg  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("FreeSimpleGUI is required for screen mode. Install it with pip.") from exc

    configure_display(display, size, refresh_seconds, orientation)
    try:
        live_events = get_preferred_events()
    except Exception as exc:
        Sg.popup_error(f"Could not fetch live tournaments.\n\n{exc}")
        raise RuntimeError("Could not fetch tournaments at startup.") from exc

    window = Sg.Window(
        WINDOW_TITLE,
        build_main_layout(),
        size=WINDOW_SIZE,
        resizable=True,
        return_keyboard_events=True,
        finalize=True,
    )
    if display == "screen" and size is None:
        window.TKroot.attributes("-fullscreen", True)
    import tkinter.font as tkfont

    global GRID_CHARACTER_WIDTH_PIXELS
    GRID_CHARACTER_WIDTH_PIXELS = float(
        tkfont.Font(root=window.TKroot, font=FONT_GRID_CELL).measure("0")
    )
    def update_grid(headers: list[str], rows: list[list[str]]) -> None:
        global PLAYER_NAME_COLUMN_WIDTH
        active_column_count = min(len(headers), MAX_GRID_COLUMNS)
        if active_column_count > 1:
            PLAYER_NAME_COLUMN_WIDTH = get_player_name_column_width(active_column_count, WINDOW_SIZE[0])
        else:
            PLAYER_NAME_COLUMN_WIDTH = get_base_column_width(1)
        window["HEADER_1"].set_size((PLAYER_NAME_COLUMN_WIDTH, 1))
        for row_index in range(MAX_GRID_ROWS):
            window[f"CELL_{row_index}_1"].set_size((PLAYER_NAME_COLUMN_WIDTH, 1))

        padded_headers = headers[:MAX_GRID_COLUMNS] + [""] * (MAX_GRID_COLUMNS - len(headers))
        for column_index, header in enumerate(padded_headers):
            is_visible = column_index < active_column_count
            window[f"HEADER_{column_index}"].update(header if is_visible else "", visible=is_visible)

        for row_index in range(MAX_GRID_ROWS):
            row_values = rows[row_index] if row_index < len(rows) else []
            padded_row = [
                fit_grid_value(value, column_index)
                for column_index, value in enumerate(row_values[:MAX_GRID_COLUMNS])
            ] + [""] * (MAX_GRID_COLUMNS - len(row_values))
            for column_index, value in enumerate(padded_row):
                is_visible = column_index < active_column_count and row_index < len(rows)
                window[f"CELL_{row_index}_{column_index}"].update(value if is_visible else "", visible=is_visible)
        window.refresh()
        fit_lcd_content_width(window, active_column_count)
        fit_visible_grid_rows(window, active_column_count, min(len(rows), MAX_GRID_ROWS))

    def render_current_event(events: list[dict[str, Any]]) -> None:
        current_event = select_display_event(events)
        if current_event is None:
            update_empty_leaderboard(window, True, message="No tournaments found")
            window["TITLE"].update(DEFAULT_TITLE)
            window["TOURNAMENT_LOGO"].update(visible=False)
            window["DATE_RANGE"].update("")
            window["STATUS"].update("")
            window["COURSE"].update("")
            window["LOCATION"].update("")
            window["WEATHER"].update("")
            window["BROADCAST"].update("")
            window["TODAY"].update("")
            update_grid([], [])
            now = datetime.now().strftime(TIME_FORMAT)
            window["LAST_UPDATE"].update(f"Last update ({now}): waiting for tournament data")
            return

        metadata, headers, rows = get_tournament_presentation_data(current_event, top_n=TOP_N_DISPLAY)
        has_players = bool(rows)
        update_empty_leaderboard(window, not has_players, metadata.get("logo_path", ""))
        if metadata.get("is_live"):
            add_hole_progress_to_live_rows(current_event, rows)
            add_tee_times_to_live_rows(current_event, rows)
        if orientation == "vertical":
            max_columns = 4 if metadata.get("is_live") else len(headers)
        else:
            max_columns = len(headers)
        visible_columns = min(max_columns, get_visible_column_count(headers, WINDOW_SIZE[0]))
        headers = headers[:visible_columns]
        rows = [row[:visible_columns] for row in rows[:MAX_GRID_ROWS]]
        event_name = current_event.get("shortName", current_event.get("name", "Tournament"))
        window["TITLE"].update(str(event_name))
        logo_path = metadata.get("logo_path", "")
        logo_bytes = fetch_logo_bytes(logo_path) if logo_path and has_players else None
        if logo_bytes:
            window["TOURNAMENT_LOGO"].update(data=logo_bytes, visible=True)
        else:
            window["TOURNAMENT_LOGO"].update(visible=False)
        window["DATE_RANGE"].update(f"Dates: {metadata['date_range']}")
        window["STATUS"].update(metadata["status"])
        window["COURSE"].update(f"Course: {metadata['course']}")
        window["LOCATION"].update(f"Location: {metadata['location']}")
        window["WEATHER"].update(f"Weather: {metadata['weather']}")
        window["BROADCAST"].update(f"TV: {metadata['broadcast']}" if metadata["broadcast"] else "TV: N/A")
        window["TODAY"].update(f"Today: {metadata['today']}" if metadata["today"] else "")
        now = datetime.now().strftime(TIME_FORMAT)
        window["LAST_UPDATE"].update(f"Last update: {now}")
        update_grid(headers, rows)

    render_current_event(live_events)

    while True:
        event, _ = window.read(timeout=AUTO_REFRESH_MS)

        if event == Sg.WIN_CLOSED or (isinstance(event, str) and event.startswith("Escape")):
            break

        if event == Sg.TIMEOUT_EVENT:
            try:
                live_events = get_preferred_events()
                render_current_event(live_events)
            except Exception as exc:
                # Keep current content if refresh fails temporarily.
                now = datetime.now().strftime(TIME_FORMAT)
                window["LAST_UPDATE"].update(f"Last update failed ({now}): {exc}")
            continue

    window.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display PGA tournament leaderboards.")
    parser.add_argument(
        "--display",
        choices=("screen", "eink"),
        default="screen",
        help="use FreeSimpleGUI for a regular screen or the native PhotoPainter driver for e-ink",
    )
    parser.add_argument(
        "--size",
        type=parse_window_size,
        help="override the profile window size, for example 1024x768",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        help="override refresh interval (defaults to 30 seconds for screen, 300 for e-ink)",
    )
    parser.add_argument(
        "--driver-path",
        help="PhotoPainter demo's 7in3_e-Paper_E/python/lib folder (e-ink mode only)",
    )
    parser.add_argument(
        "--orientation",
        choices=("vertical", "horizontal"),
        default=None,
        help="LCD window/layout orientation, or e-ink panel layout orientation",
    )
    args = parser.parse_args()
    if args.refresh_seconds is not None and args.refresh_seconds < 1:
        parser.error("--refresh-seconds must be at least 1")
    if args.display == "eink":
        if args.size is not None:
            parser.error("--size applies only to screen mode; the PhotoPainter resolution is fixed at 800x480")
        try:
            if __package__:
                from .golf_epaper import run_epaper
            else:
                from golf_epaper import run_epaper
            run_epaper(args.refresh_seconds or 300, args.driver_path, args.orientation or "vertical")
        except (ImportError, RuntimeError) as exc:
            parser.error(str(exc))
    else:
        run_gui("screen", args.size, args.refresh_seconds, args.orientation)
