"""Tests for style presets and config parsing."""

import unittest
from bot.styles import get_separators, get_available_styles, STYLE_PRESETS
from bot.config import _str_to_bool, _parse_chat_ids, _parse_float, _parse_int, BotConfig


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

    def test_parse_int_and_float_clamp_and_fall_back(self):
        self.assertEqual(_parse_int("7", 5), 7)
        self.assertEqual(_parse_int("0", 5, minimum=1), 1)
        self.assertEqual(_parse_int("garbage", 5), 5)
        self.assertEqual(_parse_int("", 5), 5)
        self.assertEqual(_parse_int(None, 5), 5)
        self.assertEqual(_parse_float("2.5", 1.0), 2.5)
        self.assertEqual(_parse_float("-3", 1.0, minimum=0.0), 0.0)
        self.assertEqual(_parse_float("nope", 1.0), 1.0)
        self.assertEqual(_parse_float(None, 1.0), 1.0)

    def test_flood_control_settings_from_env(self):
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "FLOOD_RETRY_MAX_ATTEMPTS": "3",
                "FLOOD_RETRY_BUFFER_SEC": "2.5",
                "MAX_FLOOD_WAIT_SEC": "30",
                "PERMISSION_CACHE_TTL_SEC": "0",
                "MIN_SEND_INTERVAL_SEC": "0.5",
            },
        ):
            conf = BotConfig.load_from_env()

        self.assertEqual(conf.flood_retry_max_attempts, 3)
        self.assertEqual(conf.flood_retry_buffer_sec, 2.5)
        self.assertEqual(conf.max_flood_wait_sec, 30.0)
        self.assertEqual(conf.permission_cache_ttl_sec, 0.0)
        self.assertEqual(conf.min_send_interval_sec, 0.5)

    def test_flood_control_settings_fall_back_on_invalid_values(self):
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "FLOOD_RETRY_MAX_ATTEMPTS": "garbage",
                "FLOOD_RETRY_BUFFER_SEC": "",
                "MAX_FLOOD_WAIT_SEC": "-10",
                "PERMISSION_CACHE_TTL_SEC": "abc",
                "MIN_SEND_INTERVAL_SEC": "not-a-number",
            },
        ):
            conf = BotConfig.load_from_env()

        self.assertEqual(conf.flood_retry_max_attempts, 5)
        self.assertEqual(conf.flood_retry_buffer_sec, 1.0)
        self.assertEqual(conf.max_flood_wait_sec, 0.0)  # clamped, never negative
        self.assertEqual(conf.permission_cache_ttl_sec, 300.0)
        self.assertEqual(conf.min_send_interval_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
