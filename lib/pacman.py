"""
Pacman configuration, mirror ranking with reflector, microcode detection, and pacstrap.
"""

import os
from typing import Dict, Any, List
from .executor import run_cmd, log_info, log_warn, log_success, is_dry_run


def detect_cpu_ucode() -> str:
    """Detect CPU vendor from /proc/cpuinfo and return matching ucode package."""
    if is_dry_run():
        return "intel-ucode"

    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            if "GenuineIntel" in content:
                return "intel-ucode"
            elif "AuthenticAMD" in content:
                return "amd-ucode"
    except Exception as e:
        log_warn(f"Failed to detect CPU microcode: {e}")
    return "intel-ucode"


def configure_pacman(cfg: Dict[str, Any]):
    """Update /etc/pacman.conf with ParallelDownloads, Color, and Multilib."""
    p_cfg = cfg.get("pacman", {})
    downloads = p_cfg.get("parallel_downloads", 5)
    color = p_cfg.get("color", True)
    multilib = p_cfg.get("multilib", True)

    log_info("Configuring live system pacman.conf...")

    # Set ParallelDownloads
    run_cmd(f"sed -i 's/^#ParallelDownloads = .*/ParallelDownloads = {downloads}/' /etc/pacman.conf")
    run_cmd(f"sed -i 's/^ParallelDownloads = .*/ParallelDownloads = {downloads}/' /etc/pacman.conf")

    # Set Color
    if color:
        run_cmd("sed -i 's/^#Color/Color/' /etc/pacman.conf")

    # Enable Multilib
    if multilib:
        run_cmd("sed -i '/\\[multilib\\]/,/Include/ s/^#//' /etc/pacman.conf")

    run_cmd("pacman -Sy")


def update_mirrors(cfg: Dict[str, Any]):
    """Run reflector to rank fast mirrors if requested."""
    m_cfg = cfg.get("mirrors", {})
    if not m_cfg.get("reflector", False):
        log_info("Reflector disabled, using existing mirrorlist.")
        return

    countries = m_cfg.get("countries", ["Worldwide"])
    protocol = m_cfg.get("protocol", "https")
    latest = m_cfg.get("latest", 10)
    sort = m_cfg.get("sort", "rate")

    country_args = ""
    if countries and countries != ["Worldwide"]:
        country_args = " ".join([f"--country '{c}'" for c in countries])

    cmd = f"reflector {country_args} --protocol {protocol} --latest {latest} --sort {sort} --save /etc/pacman.d/mirrorlist"
    log_info("Ranking mirrors with reflector...")
    run_cmd(cmd)


def install_base_packages(cfg: Dict[str, Any], meta: Dict[str, Any]):
    """Assemble package list and invoke pacstrap."""
    pkg_cfg = cfg.get("packages", {})
    packages: List[str] = list(pkg_cfg.get("base", ["base", "base-devel", "linux", "linux-firmware"]))

    # Microcode
    ucode = pkg_cfg.get("ucode", "auto")
    if ucode == "auto":
        ucode_pkg = detect_cpu_ucode()
        log_info(f"Auto-detected microcode: {ucode_pkg}")
        packages.append(ucode_pkg)
        meta["ucode_pkg"] = ucode_pkg
    elif ucode in ["intel-ucode", "amd-ucode"]:
        packages.append(ucode)
        meta["ucode_pkg"] = ucode

    # Filesystem & storage tools
    fs_type = meta.get("fs_type", "ext4")
    if fs_type == "btrfs":
        packages.append("btrfs-progs")
    elif fs_type == "ext4":
        packages.append("e2fsprogs")

    if meta.get("is_luks"):
        packages.append("cryptsetup")

    if meta.get("is_lvm"):
        packages.append("lvm2")

    # Bootloader packages
    bl_type = cfg.get("bootloader", {}).get("type", "systemd-boot")
    if bl_type == "grub":
        packages.extend(["grub", "efibootmgr"])
        if cfg.get("dual_boot", {}).get("os_prober", False):
            packages.append("os-prober")
    elif bl_type == "systemd-boot":
        packages.append("efibootmgr")

    # System & Custom Packages
    packages.extend(pkg_cfg.get("system", []))
    packages.extend(pkg_cfg.get("additional", []))

    # Deduplicate while preserving order
    seen = set()
    deduped_pkgs = []
    for p in packages:
        if p not in seen:
            seen.add(p)
            deduped_pkgs.append(p)

    pkg_str = " ".join(deduped_pkgs)
    log_info(f"Running pacstrap for {len(deduped_pkgs)} packages...")
    run_cmd(f"pacstrap -K /mnt {pkg_str}")

    # Copy pacman.conf to installed system
    log_info("Syncing pacman.conf to installed target system...")
    run_cmd("cp /etc/pacman.conf /mnt/etc/pacman.conf")

