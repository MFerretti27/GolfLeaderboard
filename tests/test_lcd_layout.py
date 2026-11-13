import unittest
from unittest.mock import MagicMock, patch

import golf_live_gui as gui


class LcdLayoutTests(unittest.TestCase):
    def test_portrait_fonts_scale_for_readability(self):
        for size, expected in (((600, 1024), 16), ((480, 800), 12)):
            with self.subTest(size=size), patch.dict(gui.__dict__, gui.__dict__.copy()):
                gui.configure_display("screen", size, orientation="vertical")
                self.assertEqual(gui.FONT_GRID_SIZE, expected)
                self.assertEqual(gui.FONT_META_SIZE, expected)

    def test_landscape_keeps_original_font_scale(self):
        for size, expected in (((1024, 600), 11), ((800, 480), 10)):
            for orientation in ("horizontal", None):
                with self.subTest(size=size, orientation=orientation), patch.dict(gui.__dict__, gui.__dict__.copy()):
                    gui.configure_display("screen", size, orientation=orientation)
                    self.assertEqual(gui.FONT_GRID_SIZE, expected)
                    self.assertEqual(gui.FONT_META_SIZE, expected)

    def test_tall_screen_can_display_more_than_25_players(self):
        with patch.dict(gui.__dict__, gui.__dict__.copy()):
            gui.configure_display("screen", (600, 1024), orientation="vertical")
            self.assertEqual(gui.TOP_N_DISPLAY, gui.MAX_GRID_ROWS)
            self.assertGreater(gui.MAX_GRID_ROWS, 25)

    def test_eink_keeps_existing_player_limit(self):
        with patch.dict(gui.__dict__, gui.__dict__.copy()):
            gui.configure_display("eink")
            self.assertEqual(gui.TOP_N_DISPLAY, 12)
            self.assertEqual(gui.MAX_GRID_ROWS, 12)
            self.assertEqual(gui.FONT_GRID_SIZE, 14)

    def make_window(self):
        elements = {}
        window = MagicMock()
        window.__getitem__.side_effect = lambda key: elements.setdefault(key, MagicMock())
        window["TITLE"].Widget.winfo_width.return_value = 450
        window.TKroot.winfo_pixels.return_value = 0
        window["LEADERBOARD_GRID"].Widget.winfo_pixels.return_value = 0
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
                window[f"{prefix}_{col}"].Widget.configure.assert_called_once_with(
                    anchor="w" if col == 1 else "center",
                )
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

    def test_row_overlapping_frame_border_is_hidden(self):
        window = self.make_window()
        viewport = window["LEADERBOARD_GRID"].Widget
        viewport.winfo_rooty.return_value = 100
        viewport.winfo_height.return_value = 100
        viewport.master = window.TKroot
        viewport.cget.side_effect = lambda option: "2" if option == "borderwidth" else "0"
        viewport.winfo_pixels.side_effect = int
        window.TKroot.winfo_rooty.return_value = 0
        window.TKroot.winfo_height.return_value = 200
        for col in range(4):
            widget = window[f"CELL_0_{col}"].Widget
            widget.winfo_ismapped.return_value = True
            widget.winfo_rooty.return_value = 174
            widget.winfo_height.return_value = 25
            widget.winfo_reqheight.return_value = 25
        self.assertEqual(gui.fit_visible_grid_rows(window, 4, 1), 0)
        for col in range(4):
            window[f"CELL_0_{col}"].update.assert_called_once_with(visible=False)


if __name__ == "__main__":
    unittest.main()
