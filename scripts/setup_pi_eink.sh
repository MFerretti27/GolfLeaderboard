#!/usr/bin/env bash
set -Eeuo pipefail

# Run this on Raspberry Pi OS from the GolfLeaderboard repository root or from
# anywhere inside the checkout. It prepares the PhotoPainter E6 e-paper app.

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly DRIVER_DIR="${REPO_ROOT}/RPi_Zero_PhotoPainter/7in3_e-Paper_E/python/lib"
readonly DRIVER_ZIP_URL="https://files.waveshare.com/wiki/RPi_Zero_PhotoPainter/Demo/RPi_Zero_PhotoPainter.zip"
readonly SERVICE_NAME="golf-leaderboard-eink.service"
# shellcheck source=pi_setup_common.sh
source "${SCRIPT_DIR}/pi_setup_common.sh"
INSTALL_SERVICE=1
ORIENTATION="vertical"
TMP_DIR=""
SERVICE_TMP=""

cleanup() {
    [[ -z "$TMP_DIR" ]] || rm -rf "$TMP_DIR"
    [[ -z "$SERVICE_TMP" ]] || rm -f "$SERVICE_TMP"
}
trap cleanup EXIT

usage() {
    cat <<'EOF'
Usage: bash scripts/setup_pi_eink.sh [--ip ADDRESS --user USER] [--orientation vertical|horizontal] [--no-service]

Installs the PhotoPainter-specific e-paper driver and Python system packages,
enables SPI, and configures the leaderboard to start at boot. Run on the Pi
from a checkout of this repository.
With --ip, deploy the published Git branch over SSH and run setup on that Pi.

Options:
  --ip          Remote Pi address (omit for local setup on the Pi).
  --user        SSH account (default: pi).
  --no-service   Install dependencies and enable SPI, but do not install or
                 start the systemd service.
  --orientation Set the boot service's display layout (default: vertical).
  -h, --help     Show this help.
EOF
}

parse_pi_options "$@"
if [[ -n "$PI_IP" ]]; then
    deploy_to_pi setup_pi_eink.sh
    exit 0
fi

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Run this setup script on Raspberry Pi OS on the Pi, not on macOS/Windows." >&2
    exit 1
fi

if [[ -r /proc/device-tree/model ]]; then
    PI_MODEL="$(tr -d '\0' </proc/device-tree/model)"
    if [[ "$PI_MODEL" != *"Zero 2"* ]]; then
        echo "Warning: detected '${PI_MODEL}', expected a Raspberry Pi Zero 2 W." >&2
    fi
fi

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
    RUN_USER="${SUDO_USER:-root}"
else
    SUDO=(sudo)
    RUN_USER="${USER}"
fi

if [[ "${RUN_USER}" != "root" ]] && ! id "${RUN_USER}" >/dev/null 2>&1; then
    echo "Could not determine the account that should run the display service." >&2
    exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
    sudo -v
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This script expects Raspberry Pi OS (Debian-based) with apt-get." >&2
    exit 1
fi

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y \
    curl \
    python3 \
    python3-pil \
    python3-requests \
    python3-rpi.gpio \
    python3-spidev \
    unzip

# Enable SPI using raspi-config when available; otherwise update the active
# Raspberry Pi OS boot configuration file.
if command -v raspi-config >/dev/null 2>&1; then
    "${SUDO[@]}" raspi-config nonint do_spi 0
else
    SPI_CONFIG=""
    for candidate in /boot/firmware/config.txt /boot/config.txt; do
        if [[ -f "$candidate" ]]; then
            SPI_CONFIG="$candidate"
            break
        fi
    done
    if [[ -z "$SPI_CONFIG" ]]; then
        echo "Could not find the Raspberry Pi boot config to enable SPI." >&2
        exit 1
    fi
    if ! grep -Eq '^[[:space:]]*dtparam=spi=on([[:space:]]|$)' "$SPI_CONFIG"; then
        printf '\n# Enable SPI for the PhotoPainter e-paper display\ndtparam=spi=on\n' \
            | "${SUDO[@]}" tee -a "$SPI_CONFIG" >/dev/null
    fi
fi

# Fetch the board-specific demo only when its Python driver is not already present.
if [[ ! -f "${DRIVER_DIR}/waveshare_epd/epd7in3e.py" ]]; then
    TMP_DIR="$(mktemp -d)"
    curl -fL --retry 3 "$DRIVER_ZIP_URL" -o "${TMP_DIR}/photo-painter-demo.zip"
    mkdir -p "${REPO_ROOT}/RPi_Zero_PhotoPainter"
    unzip -oq "${TMP_DIR}/photo-painter-demo.zip" -d "${REPO_ROOT}/RPi_Zero_PhotoPainter"
fi

if [[ ! -f "${DRIVER_DIR}/waveshare_epd/epd7in3e.py" ]]; then
    echo "The official archive did not contain the expected epd7in3e driver at ${DRIVER_DIR}." >&2
    exit 1
fi

if [[ "${RUN_USER}" != "root" && "${EUID}" -eq 0 ]]; then
    RUN_GROUP="$(id -gn "$RUN_USER")"
    chown -R "${RUN_USER}:${RUN_GROUP}" "${REPO_ROOT}/RPi_Zero_PhotoPainter"
fi

if [[ "${RUN_USER}" != "root" ]]; then
    for group in spi gpio; do
        if getent group "$group" >/dev/null 2>&1; then
            "${SUDO[@]}" usermod -aG "$group" "$RUN_USER"
        else
            echo "Warning: group '$group' does not exist; SPI/GPIO permissions may need manual setup." >&2
        fi
    done
fi

if ((INSTALL_SERVICE)); then
    install_wifi_watchdog
    RUN_GROUP="$(id -gn "$RUN_USER")"
    SERVICE_TMP="$(mktemp)"
    cat >"${SERVICE_TMP}" <<EOF
[Unit]
Description=Golf leaderboard on Waveshare PhotoPainter e-paper
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${REPO_ROOT}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 ${REPO_ROOT}/golf_live_gui.py --display eink --orientation ${ORIENTATION}
Restart=on-failure
RestartSec=20

[Install]
WantedBy=multi-user.target
EOF
    "${SUDO[@]}" install -m 0644 "$SERVICE_TMP" "/etc/systemd/system/${SERVICE_NAME}"
    "${SUDO[@]}" systemctl daemon-reload
    "${SUDO[@]}" systemctl enable "$SERVICE_NAME"

    if [[ -e /dev/spidev0.0 ]]; then
        "${SUDO[@]}" systemctl restart "$SERVICE_NAME" || "${SUDO[@]}" systemctl start "$SERVICE_NAME"
        echo "The e-paper service is enabled and started. Check logs with: sudo journalctl -u ${SERVICE_NAME} -f"
    else
        echo "SPI is enabled in the boot configuration, but /dev/spidev0.0 is not available yet. Reboot the Pi; the service will start automatically afterward."
    fi
else
    echo "SPI and application dependencies are configured. Run the app with: python3 ${REPO_ROOT}/golf_live_gui.py --display eink --orientation ${ORIENTATION}"
fi

if [[ "${RUN_USER}" != "root" ]]; then
    echo "The account '${RUN_USER}' was added to available SPI/GPIO groups. Log out and back in (or reboot) for group changes to take effect."
fi
