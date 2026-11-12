import unittest
from unittest.mock import patch

import golf_live_gui as gui


class LcdProgressTests(unittest.TestCase):
    def test_progress_uses_scheduled_round_and_row_order(self):
        event = {"competitions": [{"competitors": [
            {"order": 2, "linescores": [{"period": 2, "linescores": [{"value": 4}] * 18}]},
            {"order": 1, "linescores": [{"period": 2, "linescores": [{"value": 4}] * 17}]},
        ]}]}
        rows = [["1", "First", "-3", "-2"], ["2", "Second", "E", "E"]]
        with patch.object(gui, "get_scheduled_round_number", return_value=2):
            gui.add_hole_progress_to_live_rows(event, rows)
        self.assertEqual(rows[0][3], "-2 (17)")
        self.assertEqual(rows[1][3], "E (F)")

    def test_previous_round_does_not_supply_progress(self):
        event = {"competitions": [{"competitors": [
            {"order": 1, "linescores": [{"period": 1, "linescores": [{"value": 4}] * 18}]},
        ]}]}
        rows = [["1", "Player", "-3", "-"]]
        with patch.object(gui, "get_scheduled_round_number", return_value=2):
            gui.add_hole_progress_to_live_rows(event, rows)
        self.assertEqual(rows[0][3], "-")

    def test_no_hole_data_leaves_score_unchanged(self):
        event = {"competitions": [{"competitors": [{"order": 1}]}]}
        rows = [["1", "Player", "E", "E"]]
        with patch.object(gui, "get_scheduled_round_number", return_value=2):
            gui.add_hole_progress_to_live_rows(event, rows)
        self.assertEqual(rows[0][3], "E")

    def test_portrait_today_width_preserves_progress(self):
        with patch.object(gui, "SCREEN_ORIENTATION", "vertical"):
            with patch.object(gui, "GRID_WIDTH_SCALE", 0.55):
                self.assertEqual(gui.fit_grid_value("-12 (17)", 3), "-12 (17)")


if __name__ == "__main__":
    unittest.main()
