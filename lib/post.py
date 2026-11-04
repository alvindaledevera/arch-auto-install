"""
Post-installation tasks: services enablement, custom commands, and unmounting.
"""

from typing import Dict, Any
from .executor import run_cmd, log_info, log_warn, log_success


def enable_services(cfg: Dict[str, Any]):
    """Enable requested systemd services and VM guest services."""
    services = list(cfg.get("services", []))

    # Auto-enable VM guest services if installed
    try:
        proc = run_cmd("systemd-detect-virt", capture_output=True, check=False)
        virt = proc.stdout.strip().lower()
        if virt in ["qemu", "kvm", "bochs"]:
            services.append("qemu-guest-agent")
        elif virt in ["oracle", "vbox"]:
            services.append("vboxservice")
        elif virt in ["vmware"]:
            services.append("vmtoolsd")
    except Exception:
        pass

    if not services:
        return

    # Deduplicate services
    seen = set()
    deduped = [s for s in services if not (s in seen or seen.add(s))]

    log_info("Enabling systemd services...")
    for svc in deduped:
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

