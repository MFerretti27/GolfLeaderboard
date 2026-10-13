# Golf Leaderboard

A lightweight PGA leaderboard project with two entry points:

- `golf.py`: data + formatting layer (CLI-friendly)
- `golf_live_gui.py`: selects FreeSimpleGUI for regular screens or a native Waveshare driver for the PhotoPainter e-paper display
- `golf_epaper.py`: renders the leaderboard as an 800x480 image and sends it to the Waveshare E6 panel

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
- `golf_epaper.py`
  - Renders a compact leaderboard for the 7.3-inch PhotoPainter E6 panel
  - Uses the `epd7in3e` driver from the official PhotoPainter demo
  - Refreshes every five minutes by default

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

From this folder:

```bash
python3 golf.py
python3 golf_live_gui.py
```

`main.py` also creates/uses the project virtual environment and forwards display options, for example `python3 main.py --display eink`.

### Display profiles

The app defaults to FreeSimpleGUI on a regular monitor. For the Waveshare RPi Zero PhotoPainter E6 panel, use:

```bash
python3 golf_live_gui.py --display eink
```

E-ink mode uses the panel's hardware driver directly; it does not open a desktop GUI. The default refresh interval is five minutes. The regular screen mode continues to use FreeSimpleGUI and refreshes every 30 seconds.

### PhotoPainter setup

Use the driver/demo for the **RPi Zero PhotoPainter**, not a generic 7.3-inch Waveshare driver. The board has a different display power pin (BCM GPIO 27). Follow the [Waveshare PhotoPainter guide](https://www.waveshare.com/wiki/RPi_Zero_PhotoPainter), enable SPI with `sudo raspi-config`, and run the vendor's e-paper demo before using this app.

Download and extract the [official PhotoPainter demo](https://files.waveshare.com/wiki/RPi_Zero_PhotoPainter/Demo/RPi_Zero_PhotoPainter.zip). If its driver library is not in the default expected location, pass the path to its `7in3_e-Paper_E/python/lib` folder:

```bash
python3 golf_live_gui.py --display eink --driver-path /path/to/RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib
```

Install `requests` and Pillow for the app, plus the SPI/GPIO dependencies required by the Waveshare demo. E-ink mode loads the driver only when selected, so a desktop-only setup does not need the Waveshare library. To change the refresh interval, add `--refresh-seconds 600` (for ten minutes).

You can run setup directly on the Pi as described below, or launch it remotely from a Mac/Linux computer with SSH access and Git installed. The remote helper clones or updates the current branch under `~/GolfLeaderboard`, then runs the same Pi setup script. Push the branch to `origin` first so the Pi can clone it.

```bash
bash .github/deploy_pi_zero_2w.sh --ip 192.168.1.42 --user pi
```

Replace the example address and username with your Pi's values. SSH key login is recommended; the command may prompt for the Pi account password and the setup script may prompt for sudo. Once installed, the leaderboard runs as a systemd service and does not depend on the SSH session staying open.

To set up directly on the Pi instead, run `bash .github/setup_pi_zero_2w.sh` from the repository checkout. The script installs Raspberry Pi OS packages, enables SPI, downloads the PhotoPainter-specific driver if it is missing, and enables a systemd service to start the e-paper leaderboard at boot. Use `--no-service` if you only want to install the dependencies and run the app manually. Reboot if the script reports that SPI is not available yet.

## GUI Controls

- Right Arrow: next tournament
- Left Arrow: previous tournament
- Escape: quit

## Refresh Behavior

- Screen refresh defaults to 30 seconds; e-paper refresh defaults to 300 seconds.
- Override either interval with `--refresh-seconds`.
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
