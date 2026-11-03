"""
System configuration: fstab, timezone, locales, hostname, vconsole, and mkinitcpio hooks.
"""

from typing import Dict, Any
from .executor import run_cmd, log_info, log_warn, log_success


def generate_fstab():
    """Generate fstab using UUIDs."""
    log_info("Generating /etc/fstab with UUIDs...")
    run_cmd("genfstab -U /mnt >> /mnt/etc/fstab")


def configure_system(cfg: Dict[str, Any], meta: Dict[str, Any]):
    """Configure core system settings inside target installation."""
    sys_cfg = cfg["system"]
    hostname = sys_cfg["hostname"]
    timezone = sys_cfg["timezone"]
    locale = sys_cfg["locale"]
    keymap = sys_cfg["keymap"]

    # 1. Timezone
    log_info(f"Setting timezone to {timezone}...")
    run_cmd(f"ln -sf /usr/share/zoneinfo/{timezone} /mnt/etc/localtime")
    run_cmd("hwclock --systohc", chroot=True)

    # 2. Locale
    log_info(f"Configuring locale {locale}...")
    # Uncomment locale in locale.gen
    run_cmd(f"sed -i 's/^#{locale}/{locale}/' /mnt/etc/locale.gen")
    run_cmd(f"echo '{locale} UTF-8' >> /mnt/etc/locale.gen")
    run_cmd("locale-gen", chroot=True)
    run_cmd(f"echo 'LANG={locale}' > /mnt/etc/locale.conf")

    # 3. Keymap
    log_info(f"Setting console keymap to {keymap}...")
    run_cmd(f"echo 'KEYMAP={keymap}' > /mnt/etc/vconsole.conf")

    # 4. Hostname & Hosts
    log_info(f"Setting hostname to '{hostname}'...")
    run_cmd(f"echo '{hostname}' > /mnt/etc/hostname")

    hosts_content = f"""127.0.0.1   localhost
::1         localhost
127.0.1.1   {hostname}.localdomain {hostname}
"""
    run_cmd(f"echo '{hosts_content.strip()}' > /mnt/etc/hosts")

    # 5. mkinitcpio hooks
    _configure_mkinitcpio(meta)


def _configure_mkinitcpio(meta: Dict[str, Any]):
    """Assemble correct mkinitcpio HOOKS depending on LUKS, LVM, and Btrfs."""
    log_info("Configuring /etc/mkinitcpio.conf HOOKS...")

    hooks = ["base", "udev", "autodetect", "modconf", "kms", "keyboard", "keymap", "consolefont", "block"]

    if meta.get("is_luks"):
        hooks.append("encrypt")

    if meta.get("is_lvm"):
        hooks.append("lvm2")

    hooks.append("filesystems")

    if meta.get("fs_type") != "btrfs":
        hooks.append("fsck")

    hook_str = " ".join(hooks)
    log_info(f"Setting HOOKS=({hook_str})")
    run_cmd(f"sed -i 's/^HOOKS=(.*/HOOKS=({hook_str})/' /mnt/etc/mkinitcpio.conf")

    log_info("Regenerating initramfs images...")
    run_cmd("mkinitcpio -P", chroot=True)

