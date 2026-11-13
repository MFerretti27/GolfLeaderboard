#!/usr/bin/env bash

parse_pi_options() {
    PI_IP=""
    PI_USER="pi"
    INSTALL_SERVICE=1
    while (($#)); do
        case "$1" in
            --ip|--user|--orientation)
                (($# >= 2)) || { echo "$1 requires a value." >&2; exit 2; }
                case "$1" in
                    --ip) PI_IP="$2" ;;
                    --user) PI_USER="$2" ;;
                    --orientation) ORIENTATION="$2" ;;
                esac
                shift 2
                ;;
            --no-service) INSTALL_SERVICE=0; shift ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
        esac
    done
    if [[ "$ORIENTATION" != vertical && "$ORIENTATION" != horizontal ]]; then
        echo "Orientation must be 'vertical' or 'horizontal'." >&2
        exit 2
    fi
    if [[ ! "$PI_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
        echo "Invalid SSH username." >&2
        exit 2
    fi
    if [[ -n "$PI_IP" && ! "$PI_IP" =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]*$ ]]; then
        echo "Invalid Pi address; use a hostname or IP address." >&2
        exit 2
    fi
}

deploy_to_pi() {
    local entry_script="$1" repo_url branch repo_b64 branch_b64 no_service=""
    command -v ssh >/dev/null && command -v base64 >/dev/null || {
        echo "Remote deployment requires ssh and base64." >&2; exit 1;
    }
    repo_url="$(git -C "$REPO_ROOT" remote get-url origin)"
    branch="$(git -C "$REPO_ROOT" branch --show-current)"
    [[ -n "$branch" ]] || { echo "Check out a named branch before deploying." >&2; exit 1; }
    repo_b64="$(printf '%s' "$repo_url" | base64 | tr -d '\n')"
    branch_b64="$(printf '%s' "$branch" | base64 | tr -d '\n')"
    if ((!INSTALL_SERVICE)); then
        no_service="--no-service"
    fi
    echo "Deploying published branch ${branch} to ${PI_USER}@${PI_IP}."
    echo "Local uncommitted/unpushed changes are not deployed. SSH and sudo may prompt for passwords."
    # Keep stdin attached to the terminal so sudo prompts cannot consume script input.
    ssh -t "${PI_USER}@${PI_IP}" "bash -c 'set -Eeuo pipefail
repo_url=\$(printf %s ${repo_b64} | base64 --decode)
branch=\$(printf %s ${branch_b64} | base64 --decode)
repo_dir=\"\$HOME/GolfLeaderboard\"
if [[ -d \"\$repo_dir/.git\" ]]; then
    git -C \"\$repo_dir\" fetch origin \"refs/heads/\$branch:refs/remotes/origin/\$branch\"
    if git -C \"\$repo_dir\" show-ref --verify --quiet \"refs/heads/\$branch\"; then
        git -C \"\$repo_dir\" checkout \"\$branch\"
    else
        git -C \"\$repo_dir\" checkout --no-track -b \"\$branch\" \"origin/\$branch\"
    fi
    git -C \"\$repo_dir\" pull --ff-only origin \"\$branch\"
else
    [[ ! -e \"\$repo_dir\" ]] || { echo \"Destination exists but is not a Git checkout.\" >&2; exit 1; }
    git clone --single-branch --branch \"\$branch\" \"\$repo_url\" \"\$repo_dir\"
fi
bash \"\$repo_dir/scripts/${entry_script}\" --orientation ${ORIENTATION} ${no_service}
'"
}

install_wifi_watchdog() {
    if ! command -v nmcli >/dev/null 2>&1 || ! systemctl is-active --quiet NetworkManager; then
        echo "Automatic Wi-Fi recovery requires active NetworkManager and nmcli." >&2
        echo "Use --no-service for manual setup with another network manager." >&2
        exit 1
    fi
    "${SUDO[@]}" install -d -o root -g root -m 0755 /usr/local/lib/golf-leaderboard
    "${SUDO[@]}" install -o root -g root -m 0755 \
        "${SCRIPT_DIR}/pi_wifi_watchdog.sh" /usr/local/lib/golf-leaderboard/pi_wifi_watchdog.sh
    "${SUDO[@]}" install -o root -g root -m 0644 \
        "${REPO_ROOT}/systemd/golf-wifi-watchdog.service" /etc/systemd/system/golf-wifi-watchdog.service
    "${SUDO[@]}" systemctl daemon-reload
    "${SUDO[@]}" systemctl enable golf-wifi-watchdog.service
    "${SUDO[@]}" systemctl restart golf-wifi-watchdog.service
    echo "Wi-Fi recovery enabled. Logs: sudo journalctl -u golf-wifi-watchdog.service -f"
}
