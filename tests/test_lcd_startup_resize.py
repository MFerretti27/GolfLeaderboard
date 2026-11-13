import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import golf_live_gui as gui


class LcdStartupResizeTests(unittest.TestCase):
    def test_startup_failure_raises_without_opening_a_dialog(self):
        toolkit = MagicMock()
        error = ConnectionError("Wi-Fi is offline")
        with (
            patch.object(gui, "Sg", None),
            patch.dict(sys.modules, FreeSimpleGUI=toolkit),
            patch.object(gui, "configure_display"),
            patch.object(gui, "get_preferred_events", side_effect=error),
            self.assertLogs(gui.__name__, level="ERROR") as logs,
            self.assertRaisesRegex(RuntimeError, "Wi-Fi is offline") as raised,
        ):
            gui.run_gui()
        self.assertIs(raised.exception.__cause__, error)
        toolkit.popup_error.assert_not_called()
        toolkit.Window.assert_not_called()
        self.assertIn("Wi-Fi is offline", logs.output[0])

    def make_window(self):
        window = MagicMock()
        elements = {}
        window.__getitem__.side_effect = lambda key: elements.setdefault(
            key, MagicMock()
        )
        return window

    def presentation(self, live=True):
        metadata = {
            "is_live": live,
            "date_range": "Today",
            "status": "Round 2",
            "course": "Course",
            "location": "Location",
            "weather": "Clear",
            "broadcast": "",
            "today": "Round 2",
        }
        headers = ["Pos", "Player", "Tot", "Today"] + [
            str(hole) for hole in range(1, 19)
        ]
        rows = [
            [str(i + 1), "A very long player name to truncate", "E", "-"] + ["4"] * 18
            for i in range(10)
        ]
        return metadata, headers, rows

    def test_resize_recalculates_columns_and_restores_unsliced_values(self):
        for initial_width in (600, 1400):
            with (
                self.subTest(initial_width=initial_width),
                patch.dict(gui.__dict__, gui.__dict__.copy()),
            ):
                self.check_resize(initial_width)

    def check_resize(self, initial_width):
        window = self.make_window()
        width = initial_width
        window.TKroot.winfo_width.side_effect = lambda: width
        toolkit = MagicMock(WIN_CLOSED="CLOSED")
        toolkit.Window.return_value = window
        metadata, headers, rows = self.presentation(live=False)
        snapshots = []

        def capture():
            snapshots.append(
                (
                    sum(
                        window[f"HEADER_{col}"].update.call_args.kwargs["visible"]
                        for col in range(gui.MAX_GRID_COLUMNS)
                    ),
                    gui.PLAYER_NAME_COLUMN_WIDTH,
                    window["CELL_0_1"].update.call_args.args[0],
                    window["CELL_0_21"].update.call_args,
                )
            )

        def resize_and_close(*, timeout):
            nonlocal width
            capture()
            callback = window.TKroot.bind.call_args.args[1]
            for width in (600, 1400, 600, 1400):
                callback(SimpleNamespace(widget=window.TKroot, width=width, height=900))
                window.TKroot.after.call_args.args[1]()
                capture()
            return toolkit.WIN_CLOSED, {}

        window.read.side_effect = resize_and_close
        with (
            patch.dict(sys.modules, FreeSimpleGUI=toolkit),
            patch.object(gui, "get_preferred_events", return_value=[{}]),
            patch.object(gui, "select_display_event", return_value={}),
            patch.object(gui, "build_main_layout", return_value=[]),
            patch("tkinter.font.Font") as font,
            patch.object(
                gui,
                "get_tournament_presentation_data",
                return_value=(metadata, headers, rows),
            ),
            patch.object(gui, "fit_lcd_content_width"),
            patch.object(gui, "get_grid_row_capacity", return_value=3),
            patch.object(
                gui,
                "fit_visible_grid_rows",
                side_effect=lambda window, columns, count: count,
            ),
        ):
            font.return_value.measure.return_value = 8
            gui.run_gui(size=(1400, 900), orientation="horizontal")
            for snapshot, current_width in zip(
                snapshots, (initial_width, 600, 1400, 600, 1400)
            ):
                count, name_width, name, last_cell = snapshot
                self.assertEqual(
                    count, gui.get_visible_column_count(headers, current_width)
                )
                self.assertEqual(
                    name_width, gui.get_player_name_column_width(count, current_width)
                )
                if current_width == 1400:
                    self.assertEqual(name, rows[0][1])
                    self.assertTrue(last_cell.kwargs["visible"])
                    self.assertEqual(last_cell.args[0], "4")
                else:
                    self.assertFalse(last_cell.kwargs["visible"])
        self.assertEqual(len(headers), 22)
        self.assertEqual(len(rows[0]), 22)
        window.close.assert_called_once()

    def test_tee_times_only_requested_for_complete_visible_rows_on_each_refresh(self):
        window = self.make_window()
        window.TKroot.winfo_width.return_value = 600
        toolkit = MagicMock(WIN_CLOSED="CLOSED", TIMEOUT_EVENT="TIMEOUT")
        toolkit.Window.return_value = window
        window.read.side_effect = [
            (toolkit.TIMEOUT_EVENT, {}),
            (toolkit.WIN_CLOSED, {}),
        ]
        event = {
            "competitions": [{"competitors": [{"order": i + 1} for i in range(10)]}]
        }
        presentations = [self.presentation(), self.presentation()]

        def measure_capacity(window, columns):
            window["TODAY"].update.assert_called_with("Today: Round 2")
            window["TITLE"].update.assert_called_with("Tournament")
            return 3

        with (
            patch.dict(gui.__dict__, gui.__dict__.copy()),
            patch.dict(sys.modules, FreeSimpleGUI=toolkit),
            patch.object(gui, "get_preferred_events", return_value=[event]),
            patch.object(gui, "select_display_event", return_value=event),
            patch.object(gui, "build_main_layout", return_value=[]),
            patch("tkinter.font.Font") as font,
            patch.object(
                gui, "get_tournament_presentation_data", side_effect=presentations
            ),
            patch.object(gui, "add_hole_progress_to_live_rows"),
            patch.object(gui, "fit_lcd_content_width"),
            patch.object(gui, "get_grid_row_capacity", side_effect=measure_capacity),
            patch.object(gui, "fit_visible_grid_rows", return_value=2),
            patch.object(
                gui, "get_player_tee_off_time", return_value="9:00 AM"
            ) as lookup,
        ):
            font.return_value.measure.return_value = 8
            gui.run_gui(size=(600, 1024), orientation="vertical")
            self.assertEqual(lookup.call_count, 4)
            self.assertEqual(
                sorted(call.args[2]["order"] for call in lookup.call_args_list),
                [1, 1, 2, 2],
            )
            for _, _, rows in presentations:
                self.assertEqual([row[3] for row in rows[:2]], ["9:00 AM"] * 2)
                self.assertTrue(all(row[3] == "-" for row in rows[2:]))
            window["HEADER_4"].update.assert_called_with("", visible=False)

    def test_refresh_keeps_tee_time_visible_until_new_value_is_ready(self):
        window = self.make_window()
        window.TKroot.winfo_width.return_value = 600
        toolkit = MagicMock(WIN_CLOSED="CLOSED", TIMEOUT_EVENT="TIMEOUT")
        toolkit.Window.return_value = window
        event = {"id": "event-1", "competitions": [{"competitors": [{"order": 1}]}]}
        presentations = [self.presentation() for _ in range(4)]
        for _, _, rows in presentations:
            del rows[1:]
        presentations[3][2][0][1] = "Different player"
        updates = []

        def read(*, timeout):
            cell = window["CELL_0_3"]
            updates.append([call.args[0] for call in cell.update.call_args_list])
            cell.update.reset_mock()
            return (toolkit.TIMEOUT_EVENT if len(updates) < 4 else toolkit.WIN_CLOSED), {}

        window.read.side_effect = read
        with (
            patch.dict(gui.__dict__, gui.__dict__.copy()),
            patch.dict(sys.modules, FreeSimpleGUI=toolkit),
            patch.object(gui, "get_preferred_events", return_value=[event]),
            patch.object(gui, "select_display_event", return_value=event),
            patch.object(gui, "build_main_layout", return_value=[]),
            patch("tkinter.font.Font") as font,
            patch.object(gui, "get_tournament_presentation_data", side_effect=presentations),
            patch.object(gui, "add_hole_progress_to_live_rows"),
            patch.object(gui, "fit_lcd_content_width"),
            patch.object(gui, "get_grid_row_capacity", return_value=1),
            patch.object(gui, "fit_visible_grid_rows", return_value=1),
            patch.object(gui, "get_player_tee_off_time", side_effect=["9:00 AM", "9:00 AM", "9:30 AM", "10:00 AM"]),
        ):
            font.return_value.measure.return_value = 8
            gui.run_gui(size=(600, 1024), orientation="vertical")

        self.assertEqual(updates[0], ["-", "9:00 AM"])
        self.assertEqual(updates[1], ["9:00 AM", "9:00 AM"])
        self.assertEqual(updates[2], ["9:00 AM", "9:30 AM"])
        self.assertEqual(updates[3], ["-", "10:00 AM"])


if __name__ == "__main__":
    unittest.main()
