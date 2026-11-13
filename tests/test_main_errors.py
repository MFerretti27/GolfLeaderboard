import contextlib
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class MainErrorTests(unittest.TestCase):
    def test_virtualenv_failure_reports_original_exception(self):
        error_output = io.StringIO()
        with (
            patch("main.Path.exists", return_value=False),
            patch("main.venv.create", side_effect=OSError("disk full")),
            contextlib.redirect_stderr(error_output),
            self.assertRaises(SystemExit) as raised,
        ):
            main.create_virtualenv("test-venv")
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("OSError: disk full", error_output.getvalue())

    def test_dependency_failures_report_original_exception(self):
        for error in (
            subprocess.CalledProcessError(1, ["pip"]),
            FileNotFoundError("missing pip"),
        ):
            with self.subTest(error=type(error).__name__):
                error_output = io.StringIO()
                with (
                    patch("main.Path.exists", return_value=True),
                    patch("main.subprocess.check_call", side_effect=error),
                    contextlib.redirect_stderr(error_output),
                    self.assertRaises(SystemExit) as raised,
                ):
                    main.install_requirements("test-venv", "requirements.txt")
                self.assertEqual(raised.exception.code, 1)
                self.assertIn(type(error).__name__, error_output.getvalue())

    def test_program_launch_failure_reports_original_exception(self):
        error_output = io.StringIO()
        with (
            patch("main.Path.exists", return_value=True),
            patch("main.subprocess.call", side_effect=OSError("cannot launch")),
            contextlib.redirect_stderr(error_output),
            self.assertRaises(SystemExit) as raised,
        ):
            main.run_program_in_venv(Path("test-venv"), "golf_live_gui")
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("OSError: cannot launch", error_output.getvalue())
