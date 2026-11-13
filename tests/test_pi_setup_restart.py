import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

COMMON_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pi_setup_common.sh"


class PiSetupRestartTests(unittest.TestCase):
    def run_restart(self, graphical=True, bus=True, restart_status=0, local=False):
        # Unix socket paths have a short limit on macOS.
        with (
            tempfile.TemporaryDirectory(dir="/tmp") as runtime_dir,
            socket.socket(socket.AF_UNIX) as session_bus,
        ):
            if bus:
                session_bus.bind(str(Path(runtime_dir) / "bus"))
            environment = os.environ.copy()
            environment.update(
                XDG_RUNTIME_DIR=runtime_dir,
                SSH_CONNECTION="" if local else "test-ssh-session",
                DISPLAY=":0" if local else "",
                WAYLAND_DISPLAY="",
                TEST_GRAPHICAL="1" if graphical else "0",
                TEST_RESTART_STATUS=str(restart_status),
            )
            return subprocess.run(
                [
                    "bash",
                    "-c",
                    """
set -Eeuo pipefail
source "$1"
systemctl() {
    echo "systemctl $*" >&2
    case "$*" in
        "--user show-environment")
            if [[ "$TEST_GRAPHICAL" == 1 ]]; then
                echo WAYLAND_DISPLAY=wayland-0
            fi
            ;;
        "--user restart golf-leaderboard-lcd.service")
            return "$TEST_RESTART_STATUS"
            ;;
    esac
}
launcher() { echo "desktop launcher" >&2; }
restart_lcd_after_setup launcher
""",
                    "test",
                    str(COMMON_SCRIPT),
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_ssh_restarts_using_saved_desktop_environment(self):
        result = self.run_restart()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--user daemon-reload", result.stderr)
        self.assertIn("--user restart golf-leaderboard-lcd.service", result.stderr)
        self.assertIn("--user is-active --quiet", result.stderr)
        self.assertNotIn("desktop launcher", result.stderr)

    def test_local_desktop_uses_launcher(self):
        result = self.run_restart(local=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("desktop launcher", result.stderr)

    def test_no_graphical_environment_waits_for_login(self):
        result = self.run_restart(graphical=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("log into the Pi desktop", result.stdout)
        self.assertNotIn("--user restart", result.stderr)

    def test_no_user_session_waits_for_login(self):
        result = self.run_restart(bus=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No user session", result.stdout)
        self.assertNotIn("systemctl", result.stderr)

    def test_restart_failure_is_reported(self):
        result = self.run_restart(restart_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("service restarted", result.stdout)
