# Golf Leaderboard

A Python app that fetches PGA tournament scores from ESPN and displays a live leaderboard on a computer screen or a Waveshare PhotoPainter E6 e-paper panel.

## Choose how to run it

| Where | Start here | What happens |
| --- | --- | --- |
| Desktop | `python3 main.py` | Sets up Python dependencies and opens the leaderboard window. |
| Raspberry Pi Zero 2 W + PhotoPainter E6 | Follow [Raspberry Pi setup](#raspberry-pi-setup) | Installs the display driver and can start the leaderboard automatically at boot. |

The main files are:

- `main.py` - easiest way to launch the desktop app; creates a virtual environment and installs dependencies.
- `golf_live_gui.py` - runs the leaderboard on a desktop screen or e-paper panel.
- `golf.py` - prints leaderboard data in the terminal.
- `golf_epaper.py` - draws the e-paper display; normally launched through `golf_live_gui.py`.

## Contents

- [Desktop setup](#manual-desktop-install)
- [Run and choose a display](#run)
- [Raspberry Pi e-paper setup](#raspberry-pi-setup)
- [GUI controls](#gui-controls)
- [Refresh behavior](#refresh-behavior)
- [Tournament logos](#local-tournament-logos)
- [Notes](#notes)

## Quick start

### Desktop

From the project folder, run:

```bash
python3 main.py
```

This prepares the app and opens the regular desktop leaderboard. See [Desktop setup](#manual-desktop-install) for manual installation or [Run](#run) for display options.

### Raspberry Pi

Use the [Raspberry Pi setup](#raspberry-pi-setup) instructions to install the PhotoPainter driver and start the app. By default, setup installs a service that starts the leaderboard at boot. To launch it manually instead, use `python3 golf_live_gui.py --display eink`.

## Install the app

### Manual desktop install

No `.env` file is required. The checked-in `.env.example` contains legacy settings that the current application does not read; changing those values will not configure the app.

For a manual Python install, create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead of the `source` command.

Alternatively, run through `main.py`; it creates a `venv/` directory automatically if needed and installs `requirements.txt` before starting the GUI:

```bash
python3 main.py
```

To run `golf.py` or `golf_live_gui.py` directly, use the activated environment after installing requirements.

### Raspberry Pi setup

For the Waveshare RPi Zero PhotoPainter E6, choose either a **manual launch** (you start the app yourself after boot) or **automatic startup** (systemd starts it at boot). Both require a Raspberry Pi Zero 2 W running Raspberry Pi OS, internet access during setup, and the PhotoPainter panel connected to the Pi. No `.env` file or Python virtual environment is needed on the Pi.

## Run

From this folder:

```bash
python3 golf.py
python3 golf_live_gui.py
```

`main.py` creates/uses the project virtual environment and forwards display options, for example `python3 main.py --display eink`.

### Display profiles

The app defaults to FreeSimpleGUI on a regular monitor. For the Waveshare RPi Zero PhotoPainter E6 panel, use:

```bash
python3 golf_live_gui.py --display eink
```

E-ink mode uses the panel's hardware driver directly; it does not open a desktop GUI. The default refresh interval is five minutes. The regular screen mode continues to use FreeSimpleGUI and refreshes every 30 seconds.

LCD orientation keeps the regular FreeSimpleGUI dashboard and adjusts it for portrait or landscape. Landscape shows all live hole columns; portrait shows the core live columns (Pos, Player, Tot, Today) so they remain readable. Without `--orientation`, the dashboard keeps its default landscape window:

```bash
python3 golf_live_gui.py --display screen --orientation vertical
python3 golf_live_gui.py --display screen --orientation horizontal
```

LCD mode detects the primary display resolution, fits the window to the available screen, scales text, and adjusts the visible row count. Use `--size WIDTHxHEIGHT` to override the detected window size.

E-paper defaults to a vertical leaderboard (rotate the panel to portrait). To use the panel horizontally, select the landscape layout:

```bash
python3 golf_live_gui.py --display eink --orientation horizontal
```

Use `--orientation vertical` to select portrait explicitly. Set the boot service's layout during remote deployment with `--orientation horizontal`; vertical remains the default:

```bash
bash .github/deploy_pi_zero_2w.sh --ip 192.168.1.42 --user pi --orientation horizontal
```

### PhotoPainter hardware

Use the driver/demo for the **RPi Zero PhotoPainter**, not a generic 7.3-inch Waveshare driver. The board has a different display power pin (BCM GPIO 27). Connect the panel according to the [Waveshare PhotoPainter guide](https://www.waveshare.com/wiki/RPi_Zero_PhotoPainter).

<details>
<summary>Option 1: Manual launch (start it when you want)</summary>

This option has you install the prerequisites yourself and start the app when wanted. It does **not** install a boot service. Run these commands on Raspberry Pi OS:

1. Clone the repository and enter it (replace the URL if using a fork):

    ```bash
    git clone https://github.com/MFerretti27/GolfLeaderboard.git
    cd GolfLeaderboard
    ```

2. Install the system packages required by the app and Waveshare driver:

   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pil python3-requests python3-rpi.gpio python3-spidev curl unzip
   ```

3. Enable SPI and download/extract the PhotoPainter-specific Waveshare driver:

   ```bash
   sudo raspi-config nonint do_spi 0
   mkdir -p RPi_Zero_PhotoPainter
   curl -fL https://files.waveshare.com/wiki/RPi_Zero_PhotoPainter/Demo/RPi_Zero_PhotoPainter.zip -o /tmp/photo-painter-demo.zip
   unzip -oq /tmp/photo-painter-demo.zip -d RPi_Zero_PhotoPainter
   ```

   Confirm this driver file exists: `RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib/waveshare_epd/epd7in3e.py`.

4. Ensure your Pi account can access SPI/GPIO, then reboot so SPI and group changes take effect:

   ```bash
   sudo usermod -aG spi,gpio "$USER"
   sudo reboot
   ```

5. After the Pi reboots, SSH back in (or use its local terminal), enter `~/GolfLeaderboard`, and start the app:

   ```bash
   cd ~/GolfLeaderboard
   python3 golf_live_gui.py --display eink
   ```

The manual command runs in the foreground; stop it with Ctrl+C. Vertical is the default. Add `--orientation horizontal` for landscape, or `--refresh-seconds 600` for a ten-minute refresh interval.

</details>

<details>
<summary>Option 2: Automatic startup at boot (recommended)</summary>

This option installs the same prerequisites and configures a systemd service to start the leaderboard automatically at boot. You can run setup directly on the Pi:

```bash
git clone https://github.com/MFerretti27/GolfLeaderboard.git
cd GolfLeaderboard
bash .github/setup_pi_zero_2w.sh
```

Or launch setup remotely from a Mac/Linux computer with SSH and Git installed. Push the desired branch to GitHub first; the helper clones or fast-forward-updates that branch under `~/GolfLeaderboard` on the Pi, then runs the Pi setup script:

```bash
bash .github/deploy_pi_zero_2w.sh --ip 192.168.1.42 --user pi
```

Replace the example IP and username with the Pi's values. SSH access and sudo permission are required; SSH may prompt for the Pi account password and setup may prompt for the sudo password. Add `--orientation horizontal` to configure the boot service for landscape (vertical is the default).

The Pi setup script installs Raspberry Pi OS packages for Python, Pillow, requests, GPIO, SPI, curl, and unzip; enables SPI; downloads the official PhotoPainter demo driver if it is missing; adds the account to available `spi` and `gpio` groups; and installs/enables/starts `golf-leaderboard-eink.service`. The service runs independently of SSH, starts again after reboot, and restarts if the app exits unexpectedly. It refreshes every five minutes by default. If setup reports that `/dev/spidev0.0` is unavailable, reboot the Pi; SPI changes and group membership also take effect after logging out/in or rebooting.

Check automatic service logs on the Pi with:

```bash
sudo journalctl -u golf-leaderboard-eink.service -f
```

Use `bash .github/setup_pi_zero_2w.sh --no-service` if you want the setup script to prepare dependencies and SPI but do not want automatic startup.

</details>

## Refresh Behavior

- Screen refresh defaults to 30 seconds; e-paper refresh defaults to 300 seconds.
- Override either interval with `--refresh-seconds`.
- E-paper checks for updates at the configured interval but only refreshes the panel when the rendered image changes. With multiple tournaments, automatic tournament rotation changes the image and therefore triggers a refresh.
- Last update text shows:
  - time on success
  - error details on refresh failure

## Local Tournament Logos

Tournament images are local-only (no ESPN image dependency). On e-paper, a matching tournament logo is shown only when that event has no player rows, above the “No players found yet” message. If there is no event at all, the PGA logo is used instead.

Put tournament logo files in the `images/` folder next to the scripts. The legacy `tournament_images/` folder is also checked for compatibility:

- `images/`

<details>
<summary>Logo filenames and supported formats</summary>

The app will search for files using these base names (first match wins):

- event id (example: `401811945.png`)
- tournament short name
- tournament full name
- slugified short/full name (lowercase, non-alphanumeric replaced by `_`)

Supported extensions:

- `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`

If no matching event logo exists when a tournament has no players, `images/pga_logo.png` is used as a fallback. If neither logo is available, only the no-players message is shown.

</details>

## Notes

- Weather is fetched from Open-Meteo using the tournament course location; it displays `N/A` when the location cannot be resolved or weather data is unavailable.
- Column visibility is dynamic in the GUI, so unused columns are hidden.
