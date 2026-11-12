import unittest
from unittest.mock import MagicMock, patch

import golf_live_gui as gui


class LcdLayoutTests(unittest.TestCase):
    def make_window(self):
        elements = {}
        window = MagicMock()
        window.__getitem__.side_effect = lambda key: elements.setdefault(key, MagicMock())
        window["TITLE"].Widget.winfo_width.return_value = 450
        return window

    def test_portrait_title_wraps_to_allocated_width(self):
        window = self.make_window()
        with patch.object(gui, "SCREEN_ORIENTATION", "vertical"):
            gui.fit_lcd_content_width(window, 4)
        window["TITLE"].Widget.configure.assert_called_once_with(wraplength=438, height=0)

    def test_all_visible_columns_expand_in_headers_and_rows(self):
        window = self.make_window()
        with patch.object(gui, "MAX_GRID_ROWS", 2):
            gui.fit_lcd_content_width(window, 4)
        for prefix in ("HEADER", "CELL_0", "CELL_1"):
            for col in range(4):
                window[f"{prefix}_{col}"].expand.assert_called_once_with(
                    expand_x=True, expand_row=False,
                )
            window[f"{prefix}_4"].expand.assert_not_called()

    def test_landscape_title_keeps_existing_format(self):
        window = self.make_window()
        with patch.object(gui, "SCREEN_ORIENTATION", "horizontal"):
            gui.fit_lcd_content_width(window, 4)
        window["TITLE"].Widget.configure.assert_not_called()

    def test_partially_compressed_row_is_hidden(self):
        window = self.make_window()
        viewport = window["LEADERBOARD_GRID"].Widget
        viewport.winfo_rooty.return_value = 100
        viewport.winfo_height.return_value = 100
        viewport.master = window.TKroot
        window.TKroot.winfo_rooty.return_value = 0
        window.TKroot.winfo_height.return_value = 200
        for row, y, height in ((0, 120, 25), (1, 150, 25), (2, 180, 19)):
            for col in range(4):
                widget = window[f"CELL_{row}_{col}"].Widget
                widget.winfo_ismapped.return_value = True
                widget.winfo_rooty.return_value = y
                widget.winfo_height.return_value = height
                widget.winfo_reqheight.return_value = 25
        self.assertEqual(gui.fit_visible_grid_rows(window, 4, 3), 2)
        for col in range(4):
            window[f"CELL_2_{col}"].update.assert_called_once_with(visible=False)
            window[f"CELL_1_{col}"].update.assert_not_called()

    def test_row_with_full_height_and_padding_fits(self):
        window = self.make_window()
        viewport = window["LEADERBOARD_GRID"].Widget
        viewport.winfo_rooty.return_value = 100
        viewport.winfo_height.return_value = 100
        viewport.master = window.TKroot
        window.TKroot.winfo_rooty.return_value = 0
        window.TKroot.winfo_height.return_value = 200
        for col in range(4):
            widget = window[f"CELL_0_{col}"].Widget
            widget.winfo_ismapped.return_value = True
            widget.winfo_rooty.return_value = 174
            widget.winfo_height.return_value = 25
            widget.winfo_reqheight.return_value = 25
        self.assertEqual(gui.fit_visible_grid_rows(window, 4, 1), 1)


if __name__ == "__main__":
    unittest.main()
