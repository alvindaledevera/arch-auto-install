"""
Disk partitioning, LUKS encryption, LVM configuration, formatting, and mounting.
"""

import os
from typing import Dict, Any, Tuple
from .executor import run_cmd, log_info, log_warn, log_success, is_dry_run


def get_partition_path(device: str, part_num: int) -> str:
    """Return device partition path, e.g. /dev/nvme0n1p1 or /dev/sda1."""
    if device[-1].isdigit():
        return f"{device}p{part_num}"
    return f"{device}{part_num}"


def is_uefi() -> bool:
    """Check if system is booted in UEFI mode."""
    if is_dry_run():
        return True
    return os.path.exists("/sys/firmware/efi/efivars")


def get_swap_config(storage: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Determine if swap partition should be created and its size.
    Supports:
      "swap": { "enabled": true/false, "size": "8G" }
    or:
      "swap_size": "8G" / "none"
    """
    if "swap" in storage:
        s = storage["swap"]
        if isinstance(s, dict):
            enabled = s.get("enabled", True)
            size = s.get("size", "8G")
            return (bool(enabled), size if enabled else "")
        elif isinstance(s, bool):
            return (s, "8G" if s else "")

    swap_size = storage.get("swap_size")
    if swap_size is None or str(swap_size).lower() in ["none", "false", "0", "no"]:
        return (False, "")
    return (True, str(swap_size))


def setup_disk(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main disk setup entrypoint.
    Returns metadata dict containing root_device, efi_device, is_luks, luks_name, uuid, etc.
    """
    storage = cfg["storage"]
    mode = storage.get("mode", "clean_install")
    uefi_mode = is_uefi()

    meta = {
        "mode": mode,
        "is_uefi": uefi_mode,
        "is_luks": False,
        "luks_name": "",
        "root_dev": "",
        "efi_dev": "",
        "fs_type": storage.get("filesystem", {}).get("type", "ext4").lower(),
        "btrfs_subvols": storage.get("filesystem", {}).get("btrfs_subvolumes", [])
    }

    if mode == "clean_install":
        _setup_clean_install(cfg, meta)
    else:
        _setup_dual_boot(cfg, meta)

    return meta


def _setup_clean_install(cfg: Dict[str, Any], meta: Dict[str, Any]):
    storage = cfg["storage"]
    device = storage["device"]
    uefi = meta["is_uefi"]
    has_swap_part, swap_size = get_swap_config(storage)
    if storage.get("lvm", {}).get("enabled"):
        has_swap_part = False

    log_info(f"Wiping and partitioning {device} (Boot mode: {'UEFI' if uefi else 'BIOS/Legacy'})...")
    run_cmd(f"wipefs -af {device}")
    run_cmd(f"sgdisk -Z {device}")

    part_idx = 1
    if uefi:
        # Partition 1: EFI System Partition (type ef00)
        efi_size = storage.get("efi_size", "1024M")
        run_cmd(f"sgdisk -n 1:0:+{efi_size} -t 1:ef00 -c 1:'EFI System Partition' {device}")
        meta["efi_dev"] = get_partition_path(device, 1)
        part_idx += 1
    else:
        # Partition 1: BIOS Boot Partition for GRUB on GPT (type ef02, 1MB)
        run_cmd(f"sgdisk -n 1:0:+1M -t 1:ef02 -c 1:'BIOS Boot Partition' {device}")
        part_idx += 1

    swap_part = None
    if has_swap_part:
        run_cmd(f"sgdisk -n {part_idx}:0:+{swap_size} -t {part_idx}:8200 -c {part_idx}:'Linux Swap' {device}")
        swap_part = get_partition_path(device, part_idx)
        part_idx += 1

    # Check separate home configuration
    sep_home = storage.get("separate_home", {})
    has_sep_home = sep_home.get("enabled", False)
    root_size = sep_home.get("root_size", "50G")
    is_lvm = storage.get("lvm", {}).get("enabled", False)

    if is_lvm:
        # For LVM, a single partition hosts the PV (LVM will allocate root and optional home)
        run_cmd(f"sgdisk -n {part_idx}:0:0 -t {part_idx}:8e00 -c {part_idx}:'LVM PV' {device}")
        raw_root_part = get_partition_path(device, part_idx)
    elif has_sep_home:
        # Non-LVM with separate /home partition
        run_cmd(f"sgdisk -n {part_idx}:0:+{root_size} -t {part_idx}:8300 -c {part_idx}:'Arch Root' {device}")
        raw_root_part = get_partition_path(device, part_idx)
        part_idx += 1
        run_cmd(f"sgdisk -n {part_idx}:0:0 -t {part_idx}:8300 -c {part_idx}:'Arch Home' {device}")
        meta["home_dev"] = get_partition_path(device, part_idx)
    else:
        # Non-LVM combined root and home (DEFAULT)
        run_cmd(f"sgdisk -n {part_idx}:0:0 -t {part_idx}:8300 -c {part_idx}:'Arch Linux' {device}")
        raw_root_part = get_partition_path(device, part_idx)

    # Inform kernel of partition changes
    run_cmd(f"partprobe {device}")

    # Format EFI if in UEFI mode
    if uefi and meta["efi_dev"]:
        log_info(f"Formatting EFI partition {meta['efi_dev']} as FAT32...")
        run_cmd(f"mkfs.fat -F32 -n EFI {meta['efi_dev']}")

    # Setup Swap
    if swap_part:
        log_info(f"Setting up swap on {swap_part}...")
        run_cmd(f"mkswap {swap_part}")
        run_cmd(f"swapon {swap_part}")

    # LUKS setup if enabled
    target_root = _handle_encryption(storage, raw_root_part, meta)

    # LVM setup if enabled
    target_root = _handle_lvm(storage, target_root, meta)

    meta["root_dev"] = target_root

    # Format & Mount Root
    _format_and_mount_root(storage, target_root, meta)

    # Mount EFI to /mnt/boot if in UEFI mode
    if uefi and meta["efi_dev"]:
        log_info(f"Mounting EFI partition {meta['efi_dev']} to /mnt/boot...")
        run_cmd("mkdir -p /mnt/boot")
        run_cmd(f"mount {meta['efi_dev']} /mnt/boot")


def _setup_dual_boot(cfg: Dict[str, Any], meta: Dict[str, Any]):
    storage = cfg["storage"]
    parts = storage.get("partitions", {})

    efi_info = parts["efi"]
    root_info = parts["root"]
    swap_info = parts.get("swap")

    meta["efi_dev"] = efi_info["device"]
    raw_root_part = root_info["device"]

    log_info(f"Dual-Boot mode selected. Using existing partitions: EFI={meta['efi_dev']}, Root={raw_root_part}")

    # Check if user requested EFI formatting (usually False in dual boot)
    if efi_info.get("format", False):
        log_warn(f"Formatting EFI partition {meta['efi_dev']} as FAT32! Existing bootloader files will be erased.")
        run_cmd(f"mkfs.fat -F32 -n EFI {meta['efi_dev']}")
    else:
        log_info(f"Preserving existing EFI partition {meta['efi_dev']} without formatting.")

    # Swap
    if swap_info and swap_info.get("device"):
        if swap_info.get("enabled", True):
            s_dev = swap_info["device"]
            if swap_info.get("format", False):
                log_info(f"Formatting and enabling swap on {s_dev}...")
                run_cmd(f"mkswap {s_dev}")
            run_cmd(f"swapon {s_dev}")
        else:
            log_info("Swap partition is disabled in dual-boot config. Skipping.")

    # Encryption
    target_root = _handle_encryption(storage, raw_root_part, meta)
    meta["root_dev"] = target_root

    # Format & Mount Root
    _format_and_mount_root(storage, target_root, meta)

    # Mount EFI to /mnt/boot
    log_info(f"Mounting EFI partition {meta['efi_dev']} to /mnt/boot...")
    run_cmd("mkdir -p /mnt/boot")
    run_cmd(f"mount {meta['efi_dev']} /mnt/boot")


def _handle_encryption(storage: Dict[str, Any], raw_dev: str, meta: Dict[str, Any]) -> str:
    enc = storage.get("encryption", {})
    if not enc.get("enabled", False):
        return raw_dev

    luks_name = enc.get("device_name", "cryptroot")
    password = enc.get("password", "")
    enc_type = enc.get("type", "luks2")

    meta["is_luks"] = True
    meta["luks_name"] = luks_name
    meta["raw_luks_dev"] = raw_dev

    log_info(f"Encrypting {raw_dev} with LUKS ({enc_type})...")
    # cryptsetup luksFormat accepts passphrase from stdin
    run_cmd(
        f"cryptsetup luksFormat --type {enc_type} --batch-mode {raw_dev}",
        input_text=f"{password}\n",
        sensitive_mask=password
    )

    log_info(f"Opening LUKS container as /dev/mapper/{luks_name}...")
    run_cmd(
        f"cryptsetup open {raw_dev} {luks_name}",
        input_text=f"{password}\n",
        sensitive_mask=password
    )

    return f"/dev/mapper/{luks_name}"


def _handle_lvm(storage: Dict[str, Any], base_dev: str, meta: Dict[str, Any]) -> str:
    lvm_cfg = storage.get("lvm", {})
    if not lvm_cfg.get("enabled", False):
        return base_dev

    vg_name = lvm_cfg.get("vg_name", "vg0")
    meta["is_lvm"] = True
    meta["vg_name"] = vg_name

    log_info(f"Setting up LVM on {base_dev} with VG '{vg_name}'...")
    run_cmd(f"pvcreate -f {base_dev}")
    run_cmd(f"vgcreate -f {vg_name} {base_dev}")

    # 1. Swap in LVM if enabled
    has_swap, swap_size = get_swap_config(storage)
    if has_swap and swap_size:
        log_info(f"Creating LVM swap volume ({swap_size})...")
        run_cmd(f"lvcreate -L {swap_size} -n swap {vg_name}")
        swap_lv = f"/dev/mapper/{vg_name}-swap"
        run_cmd(f"mkswap {swap_lv}")
        run_cmd(f"swapon {swap_lv}")

    # 2. Check if separate /home is requested
    sep_home = storage.get("separate_home", {})
    has_sep_home = sep_home.get("enabled", False)
    root_size = sep_home.get("root_size", "50G")

    if has_sep_home:
        log_info(f"Creating separate LVM root volume ({root_size}) and home volume (remainder)...")
        run_cmd(f"lvcreate -L {root_size} -n root {vg_name}")
        run_cmd(f"lvcreate -l 100%FREE -n home {vg_name}")
        meta["home_dev"] = f"/dev/mapper/{vg_name}-home"
    else:
        log_info("Creating single combined LVM root volume taking all remaining space...")
        run_cmd(f"lvcreate -l 100%FREE -n root {vg_name}")

    return f"/dev/mapper/{vg_name}-root"


def _format_and_mount_root(storage: Dict[str, Any], root_dev: str, meta: Dict[str, Any]):
    fs_cfg = storage.get("filesystem", {})
    fs_type = fs_cfg.get("type", "ext4").lower()
    mount_opts = ",".join(fs_cfg.get("mount_options", ["noatime"]))
    has_separate_home = bool(meta.get("home_dev"))

    if fs_type == "ext4":
        log_info(f"Formatting {root_dev} as ext4...")
        run_cmd(f"mkfs.ext4 -F -L archroot {root_dev}")
        log_info(f"Mounting root {root_dev} to /mnt with options '{mount_opts}'...")
        run_cmd("mkdir -p /mnt")
        run_cmd(f"mount -o {mount_opts} {root_dev} /mnt")

    elif fs_type == "btrfs":
        log_info(f"Formatting {root_dev} as Btrfs...")
        run_cmd(f"mkfs.btrfs -f -L archroot {root_dev}")

        # Temporary mount to create subvolumes
        run_cmd("mkdir -p /mnt")
        run_cmd(f"mount {root_dev} /mnt")

        subvols = fs_cfg.get("btrfs_subvolumes", [
            {"name": "@", "mount": "/"},
            {"name": "@home", "mount": "/home"},
            {"name": "@snapshots", "mount": "/.snapshots"},
            {"name": "@var_log", "mount": "/var/log"}
        ])

        # If separate home partition/volume exists, do not create @home subvolume on root
        if has_separate_home:
            subvols = [sv for sv in subvols if sv.get("mount") != "/home"]

        for sv in subvols:
            sv_name = sv["name"]
            log_info(f"Creating Btrfs subvolume: {sv_name}")
            run_cmd(f"btrfs subvolume create /mnt/{sv_name}")

        run_cmd("umount /mnt")

        # Mount root subvolume (@)
        btrfs_opts = f"{mount_opts},subvol=@" if mount_opts else "subvol=@"
        log_info(f"Mounting root subvolume '@' to /mnt (opts: {btrfs_opts})...")
        run_cmd(f"mount -o {btrfs_opts} {root_dev} /mnt")

        # Mount other subvolumes
        for sv in subvols:
            sv_name = sv["name"]
            sv_mount = sv["mount"]
            if sv_mount == "/":
                continue

            target_dir = f"/mnt{sv_mount}"
            sub_opts = f"{mount_opts},subvol={sv_name}" if mount_opts else f"subvol={sv_name}"
            log_info(f"Mounting subvolume '{sv_name}' to {target_dir}...")
            run_cmd(f"mkdir -p {target_dir}")
            run_cmd(f"mount -o {sub_opts} {root_dev} {target_dir}")

    # If separate home partition or LV exists, format and mount it to /mnt/home
    if has_separate_home:
        home_dev = meta["home_dev"]
        log_info(f"Setting up separate /home on {home_dev} ({fs_type})...")
        if fs_type == "ext4":
            run_cmd(f"mkfs.ext4 -F -L archhome {home_dev}")
        elif fs_type == "btrfs":
            run_cmd(f"mkfs.btrfs -f -L archhome {home_dev}")

        run_cmd("mkdir -p /mnt/home")
        run_cmd(f"mount -o {mount_opts} {home_dev} /mnt/home")

