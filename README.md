# Golf Leaderboard

A lightweight PGA leaderboard project with two entry points:

- `golf.py`: data + formatting layer (CLI-friendly)
- `golf_live_gui.py`: fullscreen-style GUI leaderboard using FreeSimpleGUI
- `main.py`: bootstrap runner that creates a virtual environment, installs dependencies, and launches the app

## Files

- `golf.py`
  - Fetches scoreboard data from ESPN
  - Builds structured leaderboard data for GUI rendering
  - Supports final and live tournament formats
  - Pulls course/location metadata from ESPN core event endpoint
  - Uses local image lookup for tournament logos

- `golf_live_gui.py`
  - Renders a professional-style leaderboard UI
  - Rotates tournaments automatically every refresh interval
  - Supports keyboard navigation
  - Shows/hides tournament logo based on local image availability

- `main.py`
  - Creates `./venv` automatically if it does not exist
  - Installs dependencies from `requirements.txt`
  - Removes `.DS_Store` files on macOS
  - Launches the `golf` module inside the virtual environment

## Requirements

Install dependencies:

```bash
pip install requests FreeSimpleGUI
```

## Run

Recommended (automatic setup + run):

```bash
python3 main.py
```

This command will:

- create `./venv`
- install packages from `requirements.txt`
- run the app inside the virtual environment

Manual run options:

From this folder:

```bash
python3 golf.py
python3 leadboard_gui.py
```

## GUI Controls

- Right Arrow: next tournament
- Left Arrow: previous tournament
- Escape: quit

## Refresh Behavior

- Auto-refresh interval is set by `AUTO_REFRESH_MS` in `golf_live_gui.py`
- Last update text shows:
  - time on success
  - error details on refresh failure

## Local Tournament Logos

Tournament images are local-only (no ESPN image dependency).

Create this folder next to the scripts:

- `tournament_images/`

The app will search for files using these base names (first match wins):

- event id (example: `401811945.png`)
- tournament short name
- tournament full name
- slugified short/full name (lowercase, non-alphanumeric replaced by `_`)

Supported extensions:

- `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`

If folder or matching file does not exist, logo path resolves to an empty string and the GUI hides the image automatically.

## Notes

- Weather currently displays `N/A` unless you add a separate weather source.
- Column visibility is dynamic in the GUI, so unused columns are hidden.
