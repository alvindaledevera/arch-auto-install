"""
Post-installation tasks: services enablement, custom commands, and unmounting.
"""

from typing import Dict, Any
from .executor import run_cmd, log_info, log_warn, log_success


def enable_services(cfg: Dict[str, Any]):
    """Enable requested systemd services."""
    services = cfg.get("services", [])
    if not services:
        return

    log_info("Enabling systemd services...")
    for svc in services:
        log_info(f"Enabling service: {svc}")
        run_cmd(f"systemctl enable {svc}", chroot=True)


def run_post_install_commands(cfg: Dict[str, Any]):
    """Execute optional user-specified custom commands or scripts."""
    post_cfg = cfg.get("post_install", {})
    commands = post_cfg.get("commands", [])

    if not commands:
        return

    log_info("Executing post-installation custom commands...")
    for cmd in commands:
        log_info(f"Post command: {cmd}")
        run_cmd(cmd, chroot=True)


def cleanup_and_unmount():
    """Cleanly unmount /mnt partitions."""
    log_info("Unmounting filesystems and cleaning up...")
    run_cmd("swapoff -a", check=False)
    run_cmd("umount -R /mnt", check=False)
    log_success("All filesystems unmounted cleanly.")

