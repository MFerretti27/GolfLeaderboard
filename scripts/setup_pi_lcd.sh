#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/pi_setup_common.sh"
ORIENTATION="horizontal"

usage() {
    cat <<'EOF'
Usage: bash scripts/setup_pi_lcd.sh [--ip ADDRESS --user USER] [--orientation vertical|horizontal] [--no-service]

Set up an LCD leaderboard on Raspberry Pi OS Desktop, locally or over SSH.
Remote mode deploys the published Git branch, not local uncommitted changes.

  --ip          Remote Pi address (omit to set up this Pi).
  --user        SSH account (default: pi).
  --orientation LCD layout (default: horizontal; does not rotate the OS display).
  --no-service  Install dependencies only; skip desktop autostart and Wi-Fi recovery.
  -h, --help    Show this help.

Automatic startup requires desktop login as the setup user. Enable desktop
autologin in raspi-config for unattended startup after boot.
EOF
}

parse_pi_options "$@"
if [[ -n "$PI_IP" ]]; then
    deploy_to_pi setup_pi_lcd.sh
    exit 0
fi
if [[ "$(uname -s)" != Linux ]] || ! command -v apt-get >/dev/null 2>&1; then
    echo "Run local setup on Raspberry Pi OS Desktop, or use --ip for remote deployment." >&2
    exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
    echo "Run LCD setup as the desktop user, without sudo; it requests sudo when needed." >&2
    exit 1
fi
SUDO=(sudo)
sudo -v
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-tk python3-pil python3-requests
/usr/bin/python3 -m venv --system-site-packages "${REPO_ROOT}/.venv-lcd"
"${REPO_ROOT}/.venv-lcd/bin/python" -m pip install -r "${REPO_ROOT}/requirements.txt"

if ((INSTALL_SERVICE)); then
    install_wifi_watchdog
    mkdir -p "$HOME/.local/bin" "$HOME/.local/lib/golf-leaderboard" \
        "$HOME/.local/state/golf-leaderboard" "$HOME/.config/autostart" "$HOME/.config/systemd/user"
    launcher="$HOME/.local/bin/golf-leaderboard-lcd"
    app_runner="$HOME/.local/lib/golf-leaderboard/lcd-app"
    {
        printf '#!/usr/bin/env bash\nset -Eeuo pipefail\n'
        printf 'cd %q\n' "$REPO_ROOT"
        printf 'exec %q %q --display screen --orientation %q >> %q 2>&1\n' \
            "${REPO_ROOT}/.venv-lcd/bin/python" "${REPO_ROOT}/golf_live_gui.py" \
            "$ORIENTATION" "$HOME/.local/state/golf-leaderboard/lcd.log"
    } >"$app_runner"
    chmod 0755 "$app_runner"
    install -m 0644 "${REPO_ROOT}/systemd/golf-leaderboard-lcd.service" \
        "$HOME/.config/systemd/user/golf-leaderboard-lcd.service"
    {
        printf '#!/usr/bin/env bash\nset -Eeuo pipefail\n'
        printf 'session_vars=()\n'
        printf 'for name in DISPLAY XAUTHORITY WAYLAND_DISPLAY XDG_RUNTIME_DIR; do\n'
        printf '    if printenv "$name" >/dev/null; then session_vars+=("$name"); fi\n'
        printf 'done\n'
        printf 'if ((${#session_vars[@]})); then systemctl --user import-environment "${session_vars[@]}"; fi\n'
        printf 'systemctl --user daemon-reload\n'
        printf 'exec systemctl --user restart golf-leaderboard-lcd.service\n'
    } >"$launcher"
    chmod 0755 "$launcher"
    # The desktop supplies its own DISPLAY/XAUTHORITY, including under Wayland.
    escaped_launcher="${launcher//\\/\\\\}"
    escaped_launcher="${escaped_launcher//\"/\\\"}"
    escaped_launcher="${escaped_launcher//\$/\\\$}"
    escaped_launcher="${escaped_launcher//\`/\\\`}"
    escaped_launcher="${escaped_launcher//%/%%}"
    printf '[Desktop Entry]\nType=Application\nName=Golf Leaderboard LCD\nExec="%s"\nTerminal=false\n' \
        "$escaped_launcher" >"$HOME/.config/autostart/golf-leaderboard-lcd.desktop"
    echo "LCD autostart configured. Log into the Pi desktop (or log out/in) to start it."
    echo "The user systemd service restarts the LCD app 20 seconds after a crash."
    echo "For unattended boot, enable Desktop Autologin using sudo raspi-config."
    echo "Logs: $HOME/.local/state/golf-leaderboard/lcd.log"
else
    printf 'Dependencies ready. Launch from a desktop terminal:\n%q %q --display screen --orientation %q\n' \
        "${REPO_ROOT}/.venv-lcd/bin/python" "${REPO_ROOT}/golf_live_gui.py" "$ORIENTATION"
fi
