from __future__ import annotations

from typing import Any
from datetime import datetime
from pathlib import Path

import FreeSimpleGUI as Sg  # type: ignore[import]

try:
    # Works when launched from the workspace root as a package import.
    from golf_leaderboard.golf import get_preferred_events, get_tournament_presentation_data  # type: ignore[import]
except ModuleNotFoundError:
    # Works when this file is executed directly from the golf_leaderboard folder.
    from golf import get_preferred_events, get_tournament_presentation_data

WINDOW_SIZE = (1400, 1600)
AUTO_REFRESH_MS = 30000
TOP_N_DISPLAY: int | None = 25
MAX_GRID_COLUMNS = 22
MAX_GRID_ROWS = 25
LOGO_CACHE: dict[str, bytes] = {}
THEME = "DarkGreen5"
WINDOW_TITLE = "Golf Live Tournaments"
DEFAULT_TITLE = "Golf Leaderboard"
TITLE_TEXT = "Golf Leaderboard"
TIME_FORMAT = "%I:%M %p"

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


def fetch_logo_bytes(logo_path: str) -> bytes | None:
    """Load and cache logo image bytes from a local file path."""
    if not logo_path:
        return None
    if logo_path in LOGO_CACHE:
        return LOGO_CACHE[logo_path]

    path_obj = Path(logo_path)
    if not path_obj.exists() or not path_obj.is_file():
        return None

    try:
        content = path_obj.read_bytes()
        LOGO_CACHE[logo_path] = content
        return content
    except OSError:
        return None


def get_column_width(column_index: int) -> int:
    """Return a fixed character width for each leaderboard column."""
    if column_index == 0:
        return 5
    if column_index == 1:
        return 18
    if column_index in (2, 3):
        return 6
    return 4


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
                )
            )
        rows.append(row)
    return rows


def build_main_layout() -> list[list[Any]]:
    """Create a structured leaderboard layout for e-ink style display."""
    Sg.theme(THEME)

    return [
        [
            Sg.Image(key="TOURNAMENT_LOGO", visible=False, pad=PAD_LOGO),
            Sg.Push(),
            Sg.Text(TITLE_TEXT, font=FONT_TITLE, text_color=TEXT_COLOR_PRIMARY, key="TITLE"),
            Sg.Push(),
        ],
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
        [Sg.Frame("Leaderboard", build_grid_layout(), expand_x=True, expand_y=True, pad=PAD_LEADERBOARD)],
    ]


def get_next_event_index(events: list[dict[str, Any]], current_index: int | None) -> int:
    """Return the next event index, wrapping around for slideshow behavior."""
    if not events:
        return 0
    if current_index is None:
        return 0
    return (current_index + 1) % len(events)


def run_gui() -> None:
    """Run the golf live tournament GUI."""
    try:
        live_events = get_preferred_events()
    except Exception as exc:
        Sg.popup_error(f"Could not fetch live tournaments.\n\n{exc}")
        return

    current_index: int | None = None

    window = Sg.Window(
        WINDOW_TITLE,
        build_main_layout(),
        size=WINDOW_SIZE,
        resizable=True,
        return_keyboard_events=True,
        finalize=True,
    )

    def update_grid(headers: list[str], rows: list[list[str]]) -> None:
        active_column_count = min(len(headers), MAX_GRID_COLUMNS)
        padded_headers = headers[:MAX_GRID_COLUMNS] + [""] * (MAX_GRID_COLUMNS - len(headers))
        for column_index, header in enumerate(padded_headers):
            is_visible = column_index < active_column_count
            window[f"HEADER_{column_index}"].update(header if is_visible else "", visible=is_visible)

        for row_index in range(MAX_GRID_ROWS):
            row_values = rows[row_index] if row_index < len(rows) else []
            padded_row = [str(value) for value in row_values[:MAX_GRID_COLUMNS]] + [""] * (MAX_GRID_COLUMNS - len(row_values))
            for column_index, value in enumerate(padded_row):
                is_visible = column_index < active_column_count
                window[f"CELL_{row_index}_{column_index}"].update(value if is_visible else "", visible=is_visible)

    def render_current_event(events: list[dict[str, Any]], index: int | None) -> int | None:
        if not events:
            window["TITLE"].update(DEFAULT_TITLE)
            window["TOURNAMENT_LOGO"].update(visible=False)
            window["DATE_RANGE"].update("")
            window["STATUS"].update("No tournament data is available right now.")
            window["COURSE"].update("")
            window["LOCATION"].update("")
            window["WEATHER"].update("")
            window["BROADCAST"].update("")
            window["TODAY"].update("")
            update_grid([], [])
            now = datetime.now().strftime(TIME_FORMAT)
            window["LAST_UPDATE"].update(f"Last update ({now}): waiting for tournament data")
            return None

        next_index = get_next_event_index(events, index)
        current_event = events[next_index]
        metadata, headers, rows = get_tournament_presentation_data(current_event, top_n=TOP_N_DISPLAY)
        update_grid(headers, rows)
        event_name = current_event.get("shortName", current_event.get("name", "Tournament"))
        window["TITLE"].update(str(event_name))
        logo_path = metadata.get("logo_path", "")
        logo_bytes = fetch_logo_bytes(logo_path) if logo_path else None
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
        return next_index

    current_index = render_current_event(live_events, None)

    while True:
        event, _ = window.read(timeout=AUTO_REFRESH_MS)

        if event == Sg.WIN_CLOSED or (isinstance(event, str) and event.startswith("Escape")):
            break

        if isinstance(event, str) and (event.startswith("Right") or event.endswith(":39")):
            current_index = render_current_event(live_events, current_index)
            continue

        if isinstance(event, str) and (event.startswith("Left") or event.endswith(":37")):
            if live_events:
                if current_index is None:
                    current_index = len(live_events) - 1
                    current_index = render_current_event(live_events, current_index - 1)
                else:
                    previous_index = (current_index - 1) % len(live_events)
                    current_index = render_current_event(live_events, previous_index - 1)
            continue

        if event == Sg.TIMEOUT_EVENT:
            try:
                live_events = get_preferred_events()
                current_index = render_current_event(live_events, current_index)
            except Exception as exc:
                # Keep current content if refresh fails temporarily.
                now = datetime.now().strftime(TIME_FORMAT)
                window["LAST_UPDATE"].update(f"Last update failed ({now}): {exc}")
            continue

    window.close()


if __name__ == "__main__":
    run_gui()
