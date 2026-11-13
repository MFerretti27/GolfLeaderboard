import os
import subprocess
import unittest
from unittest.mock import patch

from scripts.lcd_portrait import ensure_portrait, parse_outputs


def output(name="HDMI-A-1", transform="normal", mode="1024x600", enabled="yes"):
    return (
        f'{name} "Display"\n  Enabled: {enabled}\n  Modes:\n'
        f'    {mode} px, 60.000000 Hz (preferred, current)\n'
        f'  Transform: {transform}\n'
    )


class LcdRotationTests(unittest.TestCase):
    def test_detects_hdmi_and_dsi_without_hardcoded_name(self):
        for name in ("HDMI-A-1", "DSI-1"):
            with self.subTest(name=name), patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
                with patch("scripts.lcd_portrait.subprocess.run") as run:
                    run.side_effect = [
                        subprocess.CompletedProcess([], 0, output(name)),
                        subprocess.CompletedProcess([], 0),
                        subprocess.CompletedProcess([], 0, output(name, "270")),
                    ]
                    ensure_portrait()
                    self.assertEqual(
                        run.call_args_list[1].args[0],
                        ["wlr-randr", "--output", name, "--transform", "270"],
                    )

    def test_preserves_existing_portrait(self):
        for transform, mode in (("90", "800x480"), ("270", "800x480"), ("normal", "480x800")):
            with self.subTest(transform=transform, mode=mode):
                with patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
                    with patch("scripts.lcd_portrait.subprocess.run") as run:
                        run.return_value = subprocess.CompletedProcess([], 0, output("DSI-1", transform, mode))
                        ensure_portrait()
                        self.assertEqual(run.call_count, 1)

    def test_ignores_disabled_outputs(self):
        displays = parse_outputs(output(enabled="no") + output("DSI-1"))
        self.assertEqual([display["name"] for display in displays], ["DSI-1"])

    def test_ambiguous_or_missing_output_is_an_error(self):
        for text in ("", output() + output("DSI-1")):
            with patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
                with patch("scripts.lcd_portrait.subprocess.run") as run:
                    run.return_value = subprocess.CompletedProcess([], 0, text)
                    with self.assertRaisesRegex(RuntimeError, "Expected one"):
                        ensure_portrait()

    def test_failed_rotation_is_propagated(self):
        with patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
            with patch("scripts.lcd_portrait.subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess([], 0, output()),
                    subprocess.CalledProcessError(1, ["wlr-randr"]),
                ]
                with self.assertRaises(subprocess.CalledProcessError):
                    ensure_portrait()

    def test_rotation_must_be_verified(self):
        with patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
            with patch("scripts.lcd_portrait.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, output())
                with self.assertRaisesRegex(RuntimeError, "was not applied"):
                    ensure_portrait()

    def test_native_portrait_panel_returns_to_normal(self):
        with patch.dict(os.environ, WAYLAND_DISPLAY="wayland-0"):
            with patch("scripts.lcd_portrait.subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess([], 0, output("DSI-1", "90", "480x800")),
                    subprocess.CompletedProcess([], 0),
                    subprocess.CompletedProcess([], 0, output("DSI-1", "normal", "480x800")),
                ]
                ensure_portrait()
                self.assertEqual(
                    run.call_args_list[1].args[0],
                    ["wlr-randr", "--output", "DSI-1", "--transform", "normal"],
                )

    def test_x11_reports_manual_rotation_without_changing_display(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("scripts.lcd_portrait.subprocess.run") as run:
                with patch("sys.stderr") as stderr:
                    ensure_portrait()
                    self.assertTrue(stderr.write.called)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
