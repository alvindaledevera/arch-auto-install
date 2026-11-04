#!/usr/bin/env python3
"""
Arch Linux Automated Installer
Declarative Arch Linux installer driven by a JSON configuration file.
"""

import argparse
import os
import sys
from typing import Dict, Any

from lib.executor import (
    set_dry_run, is_dry_run,
    log_info, log_warn, log_error, log_success, log_step,
    BOLD, GREEN, RED, YELLOW, CYAN, RESET
)
from lib.config import load_config, resolve_passwords, ConfigError
from lib.disk import setup_disk, get_swap_config
from lib.tui import TUI, run_cfdisk_wizard, run_lvm_wizard, run_format_and_mount_wizard
from lib.pacman import configure_pacman, update_mirrors, install_base_packages
from lib.system import generate_fstab, configure_system
from lib.users import configure_users
from lib.bootloader import install_bootloader
from lib.post import enable_services, run_post_install_commands, cleanup_and_unmount


def check_preflight(dry_run: bool):
    """Perform pre-flight sanity checks."""
    if not dry_run and os.geteuid() != 0:
        log_error("This script must be run as root (or with sudo).")
        sys.exit(1)

    # Check UEFI mode
    if not os.path.exists("/sys/firmware/efi/efivars"):
        log_warn("UEFI efivars not detected! Ensure you booted in UEFI mode.")


def confirm_installation(cfg: Dict[str, Any], unattended: bool):
    """Prompt user for explicit confirmation before wiping/formatting disks."""
    if is_dry_run() or unattended:
        return

    storage = cfg["storage"]
    mode = storage.get("mode", "clean_install")

    print("\n" + "=" * 50)
    print(f"{BOLD}{YELLOW}  WARNING: INSTALLATION SUMMARY & CONFIRMATION{RESET}")
    print("=" * 50)
    print(f" Mode:            {mode}")

    if mode == "clean_install":
        dev = storage.get("device")
        has_swap, swap_size = get_swap_config(storage)
        has_sep = storage.get("separate_home", {}).get("enabled", False)
        print(f" Target Disk:     {dev} {RED}(ENTIRE DISK WILL BE WIPED!){RESET}")
        print(f" EFI Size:        {storage.get('efi_size')}")
        print(f" Swap:            {swap_size if has_swap else 'Disabled (No swap partition)'}")
        print(f" Root & Home:     {'Separate /home partition' if has_sep else 'Combined (Magkasama sa iisang partition)'}")
        print(f" Filesystem:      {storage.get('filesystem', {}).get('type')}")
        print(f" Encryption:      {storage.get('encryption', {}).get('enabled')}")
        print(f" LVM:             {storage.get('lvm', {}).get('enabled')}")
    else:
        parts = storage.get("partitions", {})
        swap_part = parts.get("swap", {})
        swap_enabled = swap_part.get("enabled", True) if swap_part else False
        print(f" Target Mode:     Dual Boot / Existing Partitions")
        print(f" EFI Partition:   {parts.get('efi', {}).get('device')} (Format: {parts.get('efi', {}).get('format', False)})")
        print(f" Root Partition:  {parts.get('root', {}).get('device')} (Format: {parts.get('root', {}).get('format', True)})")
        print(f" Swap Partition:  {swap_part.get('device', 'None') if swap_enabled else 'Disabled'}")

    print(f" Hostname:        {cfg['system']['hostname']}")
    print(f" Bootloader:      {cfg.get('bootloader', {}).get('type')}")
    print("=" * 50)

    prompt = f"\nType '{BOLD}YES{RESET}' to confirm and start installation: "
    answer = input(prompt).strip()
    if answer != "YES":
        log_error("Installation aborted by user.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Declarative Arch Linux Auto-Installer")
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to JSON configuration file (default: config.json)"
    )
    parser.add_argument(
        "-p", "--profile",
        help="Use a pre-made profile from profiles/<profile>.json (e.g. btrfs-luks, dual-boot)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the installation without modifying any disks or files"
    )
    parser.add_argument(
        "-y", "--unattended",
        action="store_true",
        help="Bypass interactive confirmations (use with care!)"
    )

    args = parser.parse_args()

    if args.dry_run:
        set_dry_run(True)
        log_warn("Running in DRY-RUN mode. No changes will be written to disk.")

    # Determine configuration file path
    config_file = args.config
    if args.profile:
        config_file = os.path.join(os.path.dirname(__file__), "profiles", f"{args.profile}.json")

    # Step 1: Pre-flight checks
    check_preflight(args.dry_run)

    # Step 2: Load and validate configuration
    log_info(f"Loading configuration from: {config_file}")
    try:
        cfg = load_config(config_file)
    except ConfigError as e:
        log_error(f"Configuration error: {e}")
        sys.exit(1)

    # Step 3: Resolve passwords (prompt interactively if null/empty)
    resolve_passwords(cfg, interactive=not args.unattended)

    # Step 3.5: Interactive TUI Setup Wizard (cfdisk, LVM, Filesystem/Mounts)
    if not args.unattended:
        tui = TUI()
        while True:
            choice = tui.menu(
                "Arch Linux Installation Wizard",
                "Choose a setup step or proceed to install:",
                [
                    ("1_cfdisk", "Partition Disk (cfdisk)"),
                    ("2_lvm", "LVM Setup (Volume Group & Logical Volumes)"),
                    ("3_format", "Filesystem & Mount Points (Btrfs/Ext4)"),
                    ("4_install", "Start Installation (Run Full Installer)"),
                    ("5_exit", "Exit to Shell")
                ]
            )
            if choice == "1_cfdisk":
                run_cfdisk_wizard(cfg, tui)
            elif choice == "2_lvm":
                run_lvm_wizard(cfg, tui)
            elif choice == "3_format":
                run_format_and_mount_wizard(cfg, tui)
            elif choice == "4_install":
                break
            elif choice in ["5_exit", None]:
                log_info("Exiting installer.")
                sys.exit(0)

    # Step 4: Explicit safety confirmation
    confirm_installation(cfg, args.unattended)

    total_steps = 9
    current_step = 1

    try:
        # Step 1: Pacman live mirrors and config
        log_step(current_step, total_steps, "Configuring Pacman and Mirrors")
        configure_pacman(cfg)
        update_mirrors(cfg)
        current_step += 1

        # Step 2: Storage Setup (Partition, LUKS, LVM, Format, Mount)
        log_step(current_step, total_steps, "Storage Partitioning, Encryption & Mounts")
        meta = setup_disk(cfg)
        current_step += 1

        # Step 3: Pacstrap
        log_step(current_step, total_steps, "Installing Base Packages (Pacstrap)")
        install_base_packages(cfg, meta)
        current_step += 1

        # Step 4: Fstab
        log_step(current_step, total_steps, "Generating File System Table (/etc/fstab)")
        generate_fstab()
        current_step += 1

        # Step 5: System Configuration
        log_step(current_step, total_steps, "Configuring System (Locale, Timezone, Hostname, Hooks)")
        configure_system(cfg, meta)
        current_step += 1

        # Step 6: Users & Sudoers
        log_step(current_step, total_steps, "Setting Up User Accounts and Passwords")
        configure_users(cfg)
        current_step += 1

        # Step 7: Bootloader
        log_step(current_step, total_steps, "Installing and Configuring Bootloader")
        install_bootloader(cfg, meta)
        current_step += 1

        # Step 8: Services & Post-install
        log_step(current_step, total_steps, "Enabling Systemd Services & Post-Install Tasks")
        enable_services(cfg)
        run_post_install_commands(cfg)
        current_step += 1

        # Step 9: Cleanup & Unmount
        log_step(current_step, total_steps, "Unmounting Partitions and Finalizing")
        cleanup_and_unmount()

        print(f"\n{BOLD}{GREEN}======================================================{RESET}")
        print(f"{BOLD}{GREEN}  ARCH LINUX INSTALLATION COMPLETED SUCCESSFULLY!  {RESET}")
        print(f"{BOLD}{GREEN}======================================================{RESET}")
        print("You can now safely reboot into your new Arch Linux system:")
        print(f"{CYAN}# reboot{RESET}\n")

    except Exception as e:
        log_error(f"Installation failed: {e}")
        log_warn("Attempting cleanup/unmounting before exit...")
        cleanup_and_unmount()
        sys.exit(1)


if __name__ == "__main__":
    main()

