#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: bash .github/deploy_pi_zero_2w.sh --ip <pi-ip-address> [--user <ssh-user>] [--orientation vertical|horizontal]

Connects to a Raspberry Pi over SSH, clones/updates this repository, and runs
its PhotoPainter e-paper setup script. SSH key authentication is recommended.

Options:
  --ip       Raspberry Pi IP address (required)
  --user     Pi account name (default: pi)
    --orientation  Boot-service layout (vertical by default)
  -h, --help Show this help.
EOF
}

PI_IP=""
PI_USER="pi"
ORIENTATION="vertical"
while (($#)); do
    case "$1" in
        --ip)
            (($# >= 2)) || { echo "--ip requires an address." >&2; exit 2; }
            PI_IP="$2"
            shift 2
            ;;
        --user)
            (($# >= 2)) || { echo "--user requires a username." >&2; exit 2; }
            PI_USER="$2"
            shift 2
            ;;
        --orientation)
            (($# >= 2)) || { echo "--orientation requires vertical or horizontal." >&2; exit 2; }
            ORIENTATION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$ORIENTATION" != "vertical" && "$ORIENTATION" != "horizontal" ]]; then
    echo "Orientation must be 'vertical' or 'horizontal'." >&2
    exit 2
fi

if [[ -z "$PI_IP" ]]; then
    echo "Provide the Pi's IP address with --ip." >&2
    usage >&2
    exit 2
fi

if ! command -v ssh >/dev/null 2>&1 || ! command -v base64 >/dev/null 2>&1; then
    echo "This script requires ssh and base64 on the computer running it." >&2
    exit 1
fi

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! REPO_URL="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null)"; then
    echo "Could not find the Git origin URL for this checkout." >&2
    exit 1
fi
if ! BRANCH="$(git -C "$REPO_ROOT" branch --show-current)" || [[ -z "$BRANCH" ]]; then
    echo "Check out a named branch before deploying; detached HEAD is not supported." >&2
    exit 1
fi

REPO_URL_B64="$(printf '%s' "$REPO_URL" | base64 | tr -d '\n')"
BRANCH_B64="$(printf '%s' "$BRANCH" | base64 | tr -d '\n')"
REMOTE_COMMAND="bash -s -- ${REPO_URL_B64} ${BRANCH_B64} ${ORIENTATION}"

printf 'Connecting to %s@%s; deploying branch %s from %s\n' "$PI_USER" "$PI_IP" "$BRANCH" "$REPO_URL"
printf 'SSH may prompt for your Pi password, and setup may prompt for sudo.\n'

# Base64 arguments keep the SSH command safely quoted. The script body is sent
# over stdin, so nothing needs to be copied to the Pi ahead of time.
ssh -tt "${PI_USER}@${PI_IP}" "$REMOTE_COMMAND" <<'REMOTE_SCRIPT'
set -Eeuo pipefail
REPO_URL="$(printf '%s' "$1" | base64 --decode)"
BRANCH="$(printf '%s' "$2" | base64 --decode)"
ORIENTATION="$3"
REPO_DIR="$HOME/GolfLeaderboard"

if [[ -d "$REPO_DIR/.git" ]]; then
    echo "Updating existing checkout at $REPO_DIR..."
    git -C "$REPO_DIR" fetch origin "$BRANCH"
    if git -C "$REPO_DIR" show-ref --verify --quiet "refs/heads/$BRANCH"; then
        git -C "$REPO_DIR" checkout "$BRANCH"
    else
        git -C "$REPO_DIR" checkout --track -b "$BRANCH" "origin/$BRANCH"
    fi
    git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
else
    if [[ -e "$REPO_DIR" ]]; then
        echo "$REPO_DIR exists but is not a Git checkout; move it aside and retry." >&2
        exit 1
    fi
    git clone --single-branch --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
bash .github/setup_pi_zero_2w.sh --orientation "$ORIENTATION"
REMOTE_SCRIPT
