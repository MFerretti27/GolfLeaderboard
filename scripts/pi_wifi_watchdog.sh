#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

readonly CHECK_SECONDS=30
readonly DISCONNECTED_SECONDS=300
disconnected_since=""
radio_disabled=0

log() {
    printf '%s\n' "$*"
}

restore_radio() {
    if ((radio_disabled)); then
        log "Restoring Wi-Fi radio before exiting."
        nmcli --wait 10 radio wifi on || {
            log "ERROR: Could not restore the Wi-Fi radio."
            return 1
        }
    fi
}
trap restore_radio EXIT
trap 'exit 0' TERM INT

while true; do
    if ! devices="$(nmcli --wait 10 -t -f DEVICE,TYPE,STATE device status)"; then
        log "ERROR: Could not query NetworkManager; resetting disconnection timer."
        disconnected_since=""
        sleep "$CHECK_SECONDS"
        continue
    fi

    has_wifi=0
    connected=0
    while IFS=: read -r device type state; do
        if [[ "$type" == "wifi" ]]; then
            has_wifi=1
            if [[ "$state" == "connected" || "$state" == "connected (externally)" ]]; then
                connected=1
            fi
        fi
    done <<< "$devices"

    if ((!has_wifi)); then
        log "ERROR: No Wi-Fi device found; not cycling the radio."
        disconnected_since=""
    elif ((connected)); then
        if [[ -n "$disconnected_since" ]]; then
            log "Wi-Fi reconnected; resetting disconnection timer."
        fi
        disconnected_since=""
    else
        read -r uptime_seconds _ </proc/uptime
        now="${uptime_seconds%%.*}"
        if [[ -z "$disconnected_since" ]]; then
            disconnected_since="$now"
            log "Wi-Fi disconnected; waiting five minutes before radio recovery."
        elif ((now - disconnected_since >= DISCONNECTED_SECONDS)); then
            log "Wi-Fi disconnected for five minutes; turning radio off for five seconds."
            # Mark this first so cleanup restores Wi-Fi even if the command fails.
            radio_disabled=1
            nmcli --wait 10 radio wifi off
            sleep 5
            nmcli --wait 10 radio wifi on
            radio_disabled=0
            disconnected_since=""
            log "Wi-Fi radio enabled; NetworkManager will retry saved autoconnect networks."
        fi
    fi
    sleep "$CHECK_SECONDS"
done
