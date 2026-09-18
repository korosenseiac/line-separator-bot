"""Tests for style presets and config parsing."""

import unittest
from bot.styles import get_separators, get_available_styles, STYLE_PRESETS
from bot.config import _str_to_bool, _parse_chat_ids, BotConfig


class TestStylesAndConfig(unittest.TestCase):

    def test_styles_presets_exist(self):
        styles = get_available_styles()
        self.assertIn("luxury_gold", styles)
        self.assertIn("minimal_sleek", styles)
        self.assertIn("diamond_dots", styles)
        self.assertIn("modern_bar", styles)
        self.assertIn("aesthetic_stars", styles)
        self.assertIn("clean_double", styles)

    def test_get_separators_defaults(self):
        top, bottom = get_separators("luxury_gold")
        self.assertEqual(top, STYLE_PRESETS["luxury_gold"][0])
        self.assertEqual(bottom, STYLE_PRESETS["luxury_gold"][1])

    def test_get_separators_unknown_falls_back(self):
        top, bottom = get_separators("non_existent_style_xyz")
        self.assertEqual(top, STYLE_PRESETS["luxury_gold"][0])

    def test_custom_style(self):
        custom_top = "--- TOP ---"
        custom_bottom = "--- BOTTOM ---"
        top, bottom = get_separators("custom", custom_top=custom_top, custom_bottom=custom_bottom)
        self.assertEqual(top, custom_top)
        self.assertEqual(bottom, custom_bottom)

    def test_str_to_bool(self):
        self.assertTrue(_str_to_bool("true"))
        self.assertTrue(_str_to_bool("TRUE"))
        self.assertTrue(_str_to_bool("1"))
        self.assertTrue(_str_to_bool("yes"))
        self.assertFalse(_str_to_bool("false"))
        self.assertFalse(_str_to_bool("0"))
        self.assertFalse(_str_to_bool("no"))
        self.assertTrue(_str_to_bool(None, default=True))
        self.assertFalse(_str_to_bool(None, default=False))

    def test_parse_chat_ids(self):
        raw = "-1001234567890, -1009876543210, invalid, 12345"
        ids = _parse_chat_ids(raw)
        self.assertIn(-1001234567890, ids)
        self.assertIn(-1009876543210, ids)
        self.assertIn(12345, ids)
        self.assertEqual(len(ids), 3)

    def test_bot_config_owner(self):
        import os
        os.environ["OWNER_ID"] = "12345678"
        os.environ["ADMIN_USER_IDS"] = "111,222"
        conf = BotConfig.load_from_env()
        self.assertEqual(conf.owner_id, 12345678)
        self.assertIn(111, conf.admin_user_ids)
        self.assertIn(222, conf.admin_user_ids)


if __name__ == "__main__":
    unittest.main()
