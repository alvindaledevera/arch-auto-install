"""
UEFI Bootloader installation and configuration (systemd-boot and GRUB).
Supports kernel parameters for LUKS, LVM, Btrfs subvolumes, and dual-booting.
"""

from typing import Dict, Any
from .executor import run_cmd, log_info, log_warn, log_success, is_dry_run


def get_device_uuid(dev_path: str) -> str:
    """Retrieve filesystem/device UUID using blkid."""
    if is_dry_run():
        return "12345678-1234-1234-1234-123456789abc"

    proc = run_cmd(f"blkid -s UUID -o value {dev_path}", capture_output=True)
    return proc.stdout.strip()


def install_bootloader(cfg: Dict[str, Any], meta: Dict[str, Any]):
    """Main bootloader installation dispatcher."""
    bl_cfg = cfg.get("bootloader", {})
    bl_type = bl_cfg.get("type", "systemd-boot").lower()

    # Build kernel cmdline
    kernel_params = []

    if meta.get("is_luks"):
        raw_luks = meta["raw_luks_dev"]
        luks_name = meta["luks_name"]
        raw_uuid = get_device_uuid(raw_luks)
        kernel_params.append(f"cryptdevice=UUID={raw_uuid}:{luks_name}")

    root_dev = meta["root_dev"]
    kernel_params.append(f"root={root_dev}")

    if meta.get("fs_type") == "btrfs":
        kernel_params.append("rootflags=subvol=@")

    kernel_params.extend(["rw", "quiet"])
    cmdline_str = " ".join(kernel_params)

    log_info(f"Target Kernel Command Line: {cmdline_str}")

    if bl_type == "systemd-boot":
        _install_systemd_boot(cfg, meta, cmdline_str)
    elif bl_type == "grub":
        _install_grub(cfg, meta, cmdline_str)


def _install_systemd_boot(cfg: Dict[str, Any], meta: Dict[str, Any], cmdline: str):
    log_info("Installing systemd-boot...")
    run_cmd("bootctl install --esp-path=/boot", chroot=True)

    loader_conf = """default arch.conf
timeout 4
console-mode max
editor no
"""
    log_info("Writing /boot/loader/loader.conf...")
    run_cmd(f"echo '{loader_conf.strip()}' > /mnt/boot/loader/loader.conf")

    ucode_pkg = meta.get("ucode_pkg", "intel-ucode")
    arch_conf = f"""title Arch Linux
linux /vmlinuz-linux
initrd /{ucode_pkg}.img
initrd /initramfs-linux.img
options {cmdline}
"""
    log_info("Writing /boot/loader/entries/arch.conf...")
    run_cmd("mkdir -p /mnt/boot/loader/entries")
    run_cmd(f"echo '{arch_conf.strip()}' > /mnt/boot/loader/entries/arch.conf")

    log_success("systemd-boot installed successfully.")


def _install_grub(cfg: Dict[str, Any], meta: Dict[str, Any], cmdline: str):
    log_info("Installing GRUB for UEFI...")
    run_cmd("grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB", chroot=True)

    # Configure GRUB cmdline in /etc/default/grub
    run_cmd(f"sed -i 's|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"{cmdline}\"|' /mnt/etc/default/grub")

    dual_boot = cfg.get("dual_boot", {})
    if dual_boot.get("os_prober", False):
        log_info("Enabling os-prober in GRUB for dual boot detection...")
        run_cmd("sed -i 's/^#\\?GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' /mnt/etc/default/grub")
        run_cmd("echo 'GRUB_DISABLE_OS_PROBER=false' >> /mnt/etc/default/grub")

    log_info("Generating grub.cfg...")
    run_cmd("grub-mkconfig -o /boot/grub/grub.cfg", chroot=True)
    log_success("GRUB installed and configured successfully.")

