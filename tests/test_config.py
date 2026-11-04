"""
Test suite to validate schema checker and single config.json configuration.
"""

import os
import unittest
from lib.config import load_config, validate_config, clean_jsonc, ConfigError
from lib.disk import get_swap_config
from lib.tui import TUI, list_disks, list_partitions

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfigValidation(unittest.TestCase):

    def test_default_config_json(self):
        path = os.path.join(PROJECT_ROOT, "config.json")
        cfg = load_config(path)
        self.assertEqual(cfg["system"]["hostname"], "archlinux")
        self.assertEqual(cfg["storage"]["mode"], "clean_install")
        self.assertIn("swap", cfg["storage"])

    def test_clean_jsonc_comments_and_trailing_commas(self):
        sample = """
        {
          // Comment 1
          # Comment 2
          "system": {
            "hostname": "test-box",
            "timezone": "UTC",
            "locale": "en_US.UTF-8",
            "keymap": "us",
          },
          "storage": {
            "mode": "clean_install",
            "device": "/dev/vda",
            "swap": {
              "enabled": false,
            },
          },
          "packages": {
            "base": ["base", "linux",],
          },
        }
        """
        cleaned = clean_jsonc(sample)
        import json
        data = json.loads(cleaned)
        self.assertEqual(data["system"]["hostname"], "test-box")
        self.assertFalse(data["storage"]["swap"]["enabled"])

    def test_swap_detection_enabled(self):
        storage = {"swap": {"enabled": True, "size": "16G"}}
        has_swap, size = get_swap_config(storage)
        self.assertTrue(has_swap)
        self.assertEqual(size, "16G")

    def test_swap_detection_disabled(self):
        storage = {"swap": {"enabled": False, "size": "8G"}}
        has_swap, size = get_swap_config(storage)
        self.assertFalse(has_swap)
        self.assertEqual(size, "")

    def test_swap_detection_legacy_none(self):
        storage = {"swap_size": "none"}
        has_swap, size = get_swap_config(storage)
        self.assertFalse(has_swap)

    def test_tui_initialization(self):
        tui = TUI()
        self.assertIsNotNone(tui)

    def test_list_disks(self):
        disks = list_disks()
        self.assertIsInstance(disks, list)
        self.assertTrue(len(disks) > 0)

    def test_invalid_missing_system(self):
        with self.assertRaises(ConfigError):
            validate_config({"storage": {}})

    def test_invalid_storage_mode(self):
        bad_cfg = {
            "system": {"hostname": "h", "timezone": "t", "locale": "l", "keymap": "k"},
            "storage": {"mode": "invalid_mode"}
        }
        with self.assertRaises(ConfigError):
            validate_config(bad_cfg)


if __name__ == "__main__":
    unittest.main()
