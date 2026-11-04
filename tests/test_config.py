"""
Test suite to validate schema checker and preset configurations.
"""

import os
import unittest
from lib.config import load_config, validate_config, ConfigError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfigValidation(unittest.TestCase):

    def test_default_config_json(self):
        path = os.path.join(PROJECT_ROOT, "config.json")
        cfg = load_config(path)
        self.assertEqual(cfg["system"]["hostname"], "archlinux")
        self.assertEqual(cfg["storage"]["mode"], "clean_install")

    def test_example_config(self):
        path = os.path.join(PROJECT_ROOT, "config.example.json")
        cfg = load_config(path)
        self.assertEqual(cfg["system"]["hostname"], "archlinux")
        self.assertEqual(cfg["storage"]["mode"], "clean_install")

    def test_annotated_jsonc_config(self):
        path = os.path.join(PROJECT_ROOT, "config.annotated.jsonc")
        cfg = load_config(path)
        self.assertEqual(cfg["system"]["hostname"], "archlinux")
        self.assertEqual(cfg["storage"]["filesystem"]["type"], "btrfs")

    def test_vm_qemu_profile(self):
        path = os.path.join(PROJECT_ROOT, "profiles", "vm-qemu.json")
        cfg = load_config(path)
        self.assertEqual(cfg["storage"]["device"], "/dev/vda")
        self.assertEqual(cfg["storage"]["mode"], "clean_install")

    def test_btrfs_luks_profile(self):
        path = os.path.join(PROJECT_ROOT, "profiles", "btrfs-luks.json")
        cfg = load_config(path)
        self.assertTrue(cfg["storage"]["encryption"]["enabled"])
        self.assertEqual(cfg["storage"]["filesystem"]["type"], "btrfs")

    def test_lvm_luks_profile(self):
        path = os.path.join(PROJECT_ROOT, "profiles", "lvm-luks.json")
        cfg = load_config(path)
        self.assertTrue(cfg["storage"]["lvm"]["enabled"])
        self.assertEqual(cfg["bootloader"]["type"], "grub")

    def test_dual_boot_profile(self):
        path = os.path.join(PROJECT_ROOT, "profiles", "dual-boot.json")
        cfg = load_config(path)
        self.assertEqual(cfg["storage"]["mode"], "dual_boot")
        self.assertFalse(cfg["storage"]["partitions"]["efi"]["format"])
        self.assertTrue(cfg["dual_boot"]["enabled"])

    def test_simple_ext4_profile(self):
        path = os.path.join(PROJECT_ROOT, "profiles", "simple-ext4.json")
        cfg = load_config(path)
        self.assertEqual(cfg["storage"]["mode"], "clean_install")
        self.assertFalse(cfg["storage"]["encryption"]["enabled"])

    def test_invalid_missing_system(self):
        with self.assertRaises(ConfigError):
            validate_config({"storage": {}})

    def test_invalid_storage_mode(self):
        bad_cfg = {
            "system": {"hostname": "h", "timezone": "t", "locale": "l", "keymap": "k"},
            "storage": {"mode": "alien_mode"}
        }
        with self.assertRaises(ConfigError):
            validate_config(bad_cfg)


if __name__ == "__main__":
    unittest.main()

