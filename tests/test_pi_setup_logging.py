import subprocess
import unittest
from pathlib import Path

COMMON_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pi_setup_common.sh"


class PiSetupLoggingTests(unittest.TestCase):
    def run_deployment(self, entry_script, install_service=1, ssh_status=0):
        return subprocess.run(
            [
                "bash", "-c",
                """
set -Eeuo pipefail
source "$1"
REPO_ROOT=/example/GolfLeaderboard
PI_IP=192.0.2.1
PI_USER=pi
ORIENTATION=vertical
INSTALL_SERVICE="$3"
SSH_STATUS="$4"
git() {
    case "$*" in
        *"remote get-url origin") echo https://example.invalid/repository.git ;;
        *"branch --show-current") echo main ;;
        *) return 1 ;;
    esac
}
ssh() {
    [[ "$1" == -t && "$2" == pi@192.0.2.1 ]]
    bash -n -c "$3"
    return "$SSH_STATUS"
}
deploy_to_pi "$2"
""",
                "test", str(COMMON_SCRIPT), entry_script,
                str(install_service), str(ssh_status),
            ],
            capture_output=True, text=True, check=False,
        )

    def test_remote_summary_has_display_specific_log_command(self):
        for script, log_command in (
            ("setup_pi_lcd.sh", "tail -f ~/.local/state/golf-leaderboard/lcd.log"),
            ("setup_pi_eink.sh", "sudo journalctl -u golf-leaderboard-eink.service -f"),
        ):
            with self.subTest(script=script):
                result = self.run_deployment(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Golf Leaderboard: Remote Deployment", result.stdout)
                self.assertIn("==> [1/3] Connecting", result.stdout)
                self.assertIn("Remote Deployment Complete!", result.stdout)
                self.assertIn(log_command, result.stdout)
                self.assertIn("Local uncommitted/unpushed changes are not deployed", result.stdout)

    def test_failure_does_not_print_success_banner(self):
        result = self.run_deployment("setup_pi_lcd.sh", ssh_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Remote Deployment Complete!", result.stdout)

    def test_no_service_summary_reports_skipped_startup(self):
        result = self.run_deployment("setup_pi_eink.sh", install_service=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("were skipped (--no-service)", result.stdout)
        self.assertNotIn("Monitor e-paper logs", result.stdout)

    def test_shared_banner_and_step_format(self):
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; log_banner "Test Setup"; log_step 2 5 "Installing packages"',
             "test", str(COMMON_SCRIPT)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(
            result.stdout,
            "\n==========================================================\n"
            "  Test Setup\n"
            "==========================================================\n"
            "\n==> [2/5] Installing packages...\n",
        )
