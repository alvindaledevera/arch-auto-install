"""
TUI (Text User Interface) Wizard for Arch Linux Auto-Installer.
Provides cfdisk launcher, LVM setup menu, formatting/mounting wizard,
using whiptail (identical visual look to cfdisk) with ANSI CLI fallback.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from .executor import run_cmd, log_info, log_warn, log_success, is_dry_run, BOLD, GREEN, CYAN, YELLOW, RESET


class TUI:
    """Wrapper for whiptail dialogs with fallback to interactive CLI."""

    def __init__(self):
        self.has_whiptail = shutil.which("whiptail") is not None and os.path.exists("/dev/tty")

    def _run_whiptail(self, cmd_args: List[str]) -> Tuple[int, str]:
        """Execute whiptail connected to /dev/tty."""
        try:
            with open("/dev/tty", "r+") as tty:
                proc = subprocess.run(
                    ["whiptail"] + cmd_args,
                    stdin=tty,
                    stdout=tty,
                    stderr=subprocess.PIPE,
                    text=True
                )
                return proc.returncode, proc.stderr.strip()
        except Exception:
            return 1, ""

    def msgbox(self, title: str, text: str):
        if self.has_whiptail:
            self._run_whiptail(["--title", title, "--msgbox", text, "14", "65"])
        else:
            print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}\n{text}\n")
            input(f"Press {BOLD}[Enter]{RESET} to continue...")

    def yesno(self, title: str, prompt: str, default_yes: bool = True) -> bool:
        if self.has_whiptail:
            args = ["--title", title, "--yesno", prompt, "12", "65"]
            if not default_yes:
                args.append("--defaultno")
            code, _ = self._run_whiptail(args)
            return code == 0
        else:
            d_str = "Y/n" if default_yes else "y/N"
            ans = input(f"\n{BOLD}{prompt}{RESET} [{d_str}]: ").strip().lower()
            if not ans:
                return default_yes
            return ans in ["y", "yes"]

    def inputbox(self, title: str, prompt: str, default_val: str = "") -> str:
        if self.has_whiptail:
            code, val = self._run_whiptail(["--title", title, "--inputbox", prompt, "12", "65", default_val])
            if code == 0 and val:
                return val
            return default_val
        else:
            ans = input(f"\n{BOLD}{prompt}{RESET} (Default: '{default_val}'): ").strip()
            return ans if ans else default_val

    def menu(self, title: str, prompt: str, items: List[Tuple[str, str]]) -> Optional[str]:
        if self.has_whiptail:
            args = ["--title", title, "--menu", prompt, "16", "65", str(len(items))]
            for tag, desc in items:
                args.extend([str(tag), str(desc)])
            code, tag = self._run_whiptail(args)
            return tag if code == 0 else None
        else:
            print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")
            print(f"{prompt}\n")
            for idx, (tag, desc) in enumerate(items, 1):
                print(f"  {BOLD}{idx}.{RESET} [{tag}] {desc}")
            ans = input(f"\nChoose option (1-{len(items)}) or tag: ").strip()
            if not ans:
                return None
            if ans.isdigit():
                num = int(ans)
                if 1 <= num <= len(items):
                    return items[num - 1][0]
            for tag, _ in items:
                if ans.lower() == tag.lower():
                    return tag
            return None


def list_disks() -> List[Dict[str, str]]:
    """Return available block devices of type 'disk'."""
    if is_dry_run():
        return [{"device": "/dev/nvme0n1", "size": "1000G", "model": "Test NVMe Drive"}]
    disks = []
    try:
        proc = run_cmd("lsblk -dp -n -o NAME,SIZE,TYPE,MODEL", capture_output=True, check=False)
        for line in proc.stdout.strip().splitlines():
            parts = line.split(None, 3)
            if len(parts) >= 3 and parts[2] == "disk":
                model = parts[3] if len(parts) > 3 else "Storage Disk"
                disks.append({"device": parts[0], "size": parts[1], "model": model})
    except Exception:
        pass
    return disks


def list_partitions(disk_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """Return partitions and logical volumes."""
    if is_dry_run():
        return [
            {"device": "/dev/nvme0n1p1", "size": "1G", "type": "part", "fstype": "vfat"},
            {"device": "/dev/nvme0n1p2", "size": "999G", "type": "part", "fstype": ""}
        ]
    parts = []
    try:
        proc = run_cmd("lsblk -lp -n -o NAME,SIZE,TYPE,FSTYPE", capture_output=True, check=False)
        for line in proc.stdout.strip().splitlines():
            tokens = line.split()
            if len(tokens) >= 3 and tokens[2] in ["part", "lvm", "crypt"]:
                dev = tokens[0]
                if disk_filter and not dev.startswith(disk_filter):
                    continue
                size = tokens[1]
                fstype = tokens[3] if len(tokens) > 3 else ""
                parts.append({"device": dev, "size": size, "type": tokens[2], "fstype": fstype})
    except Exception:
        pass
    return parts


def run_cfdisk_wizard(cfg: Dict[str, Any], tui: TUI):
    """Step 1: Partition Disk using cfdisk."""
    disks = list_disks()
    if not disks:
        tui.msgbox("No Disks Found", "No storage disks were detected on this machine.")
        return

    items = [(d["device"], f"{d['size']} - {d['model']}") for d in disks]
    chosen = tui.menu("Partition Setup (cfdisk)", "Select a storage drive to partition with cfdisk:", items)
    if not chosen:
        return

    cfg["storage"]["device"] = chosen

    if is_dry_run():
        tui.msgbox("DRY-RUN", f"Dry-run active. Would launch: cfdisk {chosen}")
        return

    # Launch cfdisk
    log_info(f"Opening cfdisk on {chosen}...")
    try:
        subprocess.run(["cfdisk", chosen])
        run_cmd(f"partprobe {chosen}", check=False)
    except Exception as e:
        tui.msgbox("Error", f"Failed to run cfdisk: {e}")
        return

    # Show new partitions
    parts = list_partitions(chosen)
    part_summary = "\n".join([f"  {p['device']} ({p['size']} {p['type']} {p['fstype']})" for p in parts])
    tui.msgbox("Partitions Updated", f"Partitions on {chosen}:\n\n{part_summary or 'No partitions created.'}")


def run_lvm_wizard(cfg: Dict[str, Any], tui: TUI):
    """Step 2: LVM Setup TUI."""
    storage = cfg["storage"]
    lvm_cfg = storage.setdefault("lvm", {})

    enable_lvm = tui.yesno(
        "LVM Configuration",
        "Do you want to put your filesystem inside LVM (Logical Volume Management)?",
        default_yes=lvm_cfg.get("enabled", False)
    )

    lvm_cfg["enabled"] = enable_lvm
    if not enable_lvm:
        tui.msgbox("LVM Disabled", "LVM is disabled. Standard partitions will be used.")
        return

    # VG Name
    vg_name = tui.inputbox("Volume Group Name", "Enter LVM Volume Group Name:", lvm_cfg.get("vg_name", "vg0"))
    lvm_cfg["vg_name"] = vg_name

    # Swap in LVM
    swap_cfg = storage.setdefault("swap", {})
    add_swap = tui.yesno("LVM Swap", "Create a Swap Logical Volume in LVM?", default_yes=swap_cfg.get("enabled", True))
    swap_cfg["enabled"] = add_swap
    if add_swap:
        swap_size = tui.inputbox("Swap Size", "Enter Swap size (e.g. 4G, 8G, 16G):", swap_cfg.get("size", "8G"))
        swap_cfg["size"] = swap_size

    # Combined vs Separate /home
    sep_home = storage.setdefault("separate_home", {})
    layout = tui.menu(
        "Root & Home Layout",
        "Choose how root (/) and /home should be allocated in LVM:",
        [
            ("combined", "Magkasama sa iisang volume (DEFAULT - Recommended)"),
            ("separate", "Hiwalay na Logical Volume para sa /home")
        ]
    )

    if layout == "separate":
        sep_home["enabled"] = True
        root_size = tui.inputbox("Root LV Size", "Enter size for root LV (home takes remainder):", sep_home.get("root_size", "50G"))
        sep_home["root_size"] = root_size
    else:
        sep_home["enabled"] = False

    tui.msgbox(
        "LVM Configured",
        f"LVM Configuration Ready:\n"
        f" • Volume Group: {vg_name}\n"
        f" • Swap LV:      {'Enabled (' + swap_cfg.get('size', '8G') + ')' if add_swap else 'Disabled'}\n"
        f" • Layout:       {'Separate (/home)' if sep_home.get('enabled') else 'Combined (root only)'}"
    )


def run_format_and_mount_wizard(cfg: Dict[str, Any], tui: TUI) -> bool:
    """Step 3: Filesystem, Mounting and Formatting TUI."""
    storage = cfg["storage"]
    fs_cfg = storage.setdefault("filesystem", {})

    # Choose Filesystem
    chosen_fs = tui.menu(
        "Filesystem Selection",
        "Select filesystem format for Arch Linux:",
        [
            ("btrfs", "Btrfs (Modern, snapshots, subvolumes @, @home, zstd compress)"),
            ("ext4", "Ext4 (Classic, rock-solid, simplest)")
        ]
    )
    if chosen_fs:
        fs_cfg["type"] = chosen_fs

    # Select Mode: Clean Install or Dual Boot/Manual Partitions
    mode_choice = tui.menu(
        "Storage Mode",
        "Choose storage installation mode:",
        [
            ("clean_install", "Clean Install (Wipes & formats target disk automatically)"),
            ("dual_boot", "Manual / Dual-Boot (Assign existing partitions without wiping disk)")
        ]
    )
    if mode_choice:
        storage["mode"] = mode_choice

    if storage["mode"] == "dual_boot":
        parts = list_partitions()
        part_items = [(p["device"], f"{p['size']} {p['fstype']}") for p in parts]
        if not part_items:
            tui.msgbox("Notice", "No existing partitions detected. Please partition with cfdisk first.")
            return False

        # Select EFI
        efi_dev = tui.menu("EFI System Partition", "Select your existing EFI partition (/boot):", part_items)
        if efi_dev:
            storage.setdefault("partitions", {})["efi"] = {"device": efi_dev, "format": False, "mount": "/boot"}

        # Select Root
        root_dev = tui.menu("Root Partition", "Select target partition for Arch Root (/):", part_items)
        if root_dev:
            storage["partitions"]["root"] = {"device": root_dev, "format": True}

        # Select Swap
        if storage.get("swap", {}).get("enabled", True):
            swap_items = [("none", "Do not use a swap partition")] + part_items
            swap_dev = tui.menu("Swap Partition", "Select swap partition (or none):", swap_items)
            if swap_dev and swap_dev != "none":
                storage["partitions"]["swap"] = {"device": swap_dev, "format": True, "enabled": True}
            else:
                storage["partitions"]["swap"] = {"enabled": False}

    tui.msgbox(
        "Mount Setup Ready",
        f"Storage Setup Summary:\n"
        f" • Mode:       {storage['mode']}\n"
        f" • Filesystem: {fs_cfg['type']}\n"
        f" • Target:     {storage.get('device') or storage.get('partitions', {}).get('root', {}).get('device')}\n"
        f" • LVM:        {storage.get('lvm', {}).get('enabled', False)}\n"
        f" • Swap:       {storage.get('swap', {}).get('enabled', True)}"
    )
    return True

