"""
Configuration loader, schema validator, and interactive credential resolver.
"""

import json
import getpass
import os
import re
import sys
from typing import Dict, Any
from .executor import log_info, log_warn, log_error, is_dry_run


class ConfigError(Exception):
    """Raised when configuration validation fails."""
    pass


def clean_jsonc(text: str) -> str:
    """
    Strips single-line (//, #) and multi-line (/* */) comments,
    and removes trailing commas so users can comment JSON files freely.
    """
    pattern = r'(\"(?:\\.|[^\"\x5c])*\")|(/\*.*?\*/|//[^\r\n]*$|#[^\r\n]*$)'

    def replacer(match):
        if match.group(2) is not None:
            return ""
        return match.group(1)

    # 1. Strip comments
    no_comments = re.sub(pattern, replacer, text, flags=re.MULTILINE | re.DOTALL)
    # 2. Strip trailing commas before closing braces/brackets
    cleaned = re.sub(r',\s*([\]}])', r'\1', no_comments)
    return cleaned


def load_config(config_path: str) -> Dict[str, Any]:
    """Load JSON/JSONC configuration from a file path."""
    if not os.path.exists(config_path):
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        cleaned_text = clean_jsonc(raw_text)
        config = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON/JSONC syntax in {config_path}: {e}")

    validate_config(config)
    return config


def validate_config(cfg: Dict[str, Any]):
    """Validate required keys and types in configuration."""
    # 1. System
    if "system" not in cfg:
        raise ConfigError("Missing 'system' configuration section")
    sys_cfg = cfg["system"]
    for req in ["hostname", "timezone", "locale", "keymap"]:
        if not sys_cfg.get(req):
            raise ConfigError(f"Missing or empty required field in system: '{req}'")

    # 2. Storage
    if "storage" not in cfg:
        raise ConfigError("Missing 'storage' configuration section")
    storage = cfg["storage"]
    mode = storage.get("mode", "clean_install")

    if mode not in ["clean_install", "dual_boot"]:
        raise ConfigError(f"Invalid storage mode '{mode}'. Must be 'clean_install' or 'dual_boot'")

    if mode == "clean_install":
        if not storage.get("device"):
            raise ConfigError("Storage mode 'clean_install' requires 'device' (e.g. /dev/nvme0n1)")
    elif mode == "dual_boot":
        partitions = storage.get("partitions", {})
        if not partitions.get("efi", {}).get("device"):
            raise ConfigError("Storage mode 'dual_boot' requires 'partitions.efi.device'")
        if not partitions.get("root", {}).get("device"):
            raise ConfigError("Storage mode 'dual_boot' requires 'partitions.root.device'")

    # Filesystem check
    fs_cfg = storage.get("filesystem", {})
    fs_type = fs_cfg.get("type", "ext4").lower()
    if fs_type not in ["btrfs", "ext4"]:
        raise ConfigError(f"Unsupported filesystem type '{fs_type}'. Must be 'btrfs' or 'ext4'")

    if fs_type == "btrfs":
        subvols = fs_cfg.get("btrfs_subvolumes", [])
        if not any(sv.get("mount") == "/" for sv in subvols):
            raise ConfigError("Btrfs filesystem must define at least one subvolume mounted at '/' (e.g. name: '@')")

    # 3. Bootloader
    bl_cfg = cfg.get("bootloader", {})
    bl_type = bl_cfg.get("type", "systemd-boot").lower()
    if bl_type not in ["systemd-boot", "grub"]:
        raise ConfigError(f"Unsupported bootloader '{bl_type}'. Must be 'systemd-boot' or 'grub'")

    # 4. Packages
    pkg_cfg = cfg.get("packages", {})
    if "base" not in pkg_cfg or not isinstance(pkg_cfg["base"], list):
        raise ConfigError("'packages.base' must be a list of base packages (e.g. ['base', 'linux', ...])")

    # 5. Users
    users_cfg = cfg.get("users", {})
    accounts = users_cfg.get("accounts", [])
    if not isinstance(accounts, list):
        raise ConfigError("'users.accounts' must be a list of user accounts")

    for idx, acc in enumerate(accounts):
        if not acc.get("username"):
            raise ConfigError(f"User account at index {idx} missing 'username'")


def resolve_passwords(cfg: Dict[str, Any], interactive: bool = True):
    """
    Prompt user interactively for any passwords that are null or empty.
    In dry-run mode, placeholders are supplied if not provided.
    """
    dry = is_dry_run()

    # 1. LUKS passphrase
    storage = cfg.get("storage", {})
    enc = storage.get("encryption", {})
    if enc.get("enabled"):
        pw = enc.get("password")
        if not pw:
            if dry:
                enc["password"] = "dry_run_luks_pass"
            elif interactive:
                print("\n--- LUKS Disk Encryption Passphrase ---")
                while True:
                    p1 = getpass.getpass("Enter LUKS passphrase: ")
                    if not p1:
                        print("Passphrase cannot be empty. Try again.")
                        continue
                    p2 = getpass.getpass("Confirm LUKS passphrase: ")
                    if p1 == p2:
                        enc["password"] = p1
                        break
                    print("Passphrases do not match. Try again.")

    # 2. Root password
    users = cfg.setdefault("users", {})
    root_pw = users.get("root_password")
    if not root_pw:
        if dry:
            users["root_password"] = "dry_run_root_pass"
        elif interactive:
            print("\n--- Root Password Setup ---")
            while True:
                p1 = getpass.getpass("Enter root password: ")
                if not p1:
                    print("Root password cannot be empty. Try again.")
                    continue
                p2 = getpass.getpass("Confirm root password: ")
                if p1 == p2:
                    users["root_password"] = p1
                    break
                print("Passwords do not match. Try again.")

    # 3. User account passwords
    for acc in users.get("accounts", []):
        uname = acc["username"]
        u_pw = acc.get("password")
        if not u_pw:
            if dry:
                acc["password"] = f"dry_run_{uname}_pass"
            elif interactive:
                print(f"\n--- User Password Setup: '{uname}' ---")
                while True:
                    p1 = getpass.getpass(f"Enter password for '{uname}': ")
                    if not p1:
                        print("Password cannot be empty. Try again.")
                        continue
                    p2 = getpass.getpass(f"Confirm password for '{uname}': ")
                    if p1 == p2:
                        acc["password"] = p1
                        break
                    print("Passwords do not match. Try again.")

