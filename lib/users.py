"""
User account creation, passwords, and sudoers configuration.
"""

from typing import Dict, Any
from .executor import run_cmd, log_info, log_warn, log_success


def configure_users(cfg: Dict[str, Any]):
    """Set root password and configure user accounts and sudoers."""
    users_cfg = cfg.get("users", {})

    # 1. Root password
    root_pw = users_cfg.get("root_password")
    if root_pw:
        log_info("Setting root password...")
        run_cmd(
            "chpasswd",
            chroot=True,
            input_text=f"root:{root_pw}\n",
            sensitive_mask=root_pw
        )

    # 2. Configure sudoers directory
    run_cmd("mkdir -p /mnt/etc/sudoers.d")
    run_cmd("echo '%wheel ALL=(ALL:ALL) ALL' > /mnt/etc/sudoers.d/wheel")
    run_cmd("chmod 440 /mnt/etc/sudoers.d/wheel")

    # 3. Create user accounts
    for acc in users_cfg.get("accounts", []):
        uname = acc["username"]
        pw = acc.get("password")
        groups = ",".join(acc.get("groups", ["wheel"]))
        shell = acc.get("shell", "/bin/bash")
        nopasswd = acc.get("sudo_nopasswd", False)

        log_info(f"Creating user '{uname}' (groups: {groups}, shell: {shell})...")
        # Ensure shell exists or fallback to /bin/bash
        run_cmd(f"useradd -m -G {groups} -s {shell} {uname}", chroot=True)

        if pw:
            log_info(f"Setting password for user '{uname}'...")
            run_cmd(
                "chpasswd",
                chroot=True,
                input_text=f"{uname}:{pw}\n",
                sensitive_mask=pw
            )

        if nopasswd:
            log_info(f"Configuring passwordless sudo for '{uname}'...")
            run_cmd(f"echo '{uname} ALL=(ALL:ALL) NOPASSWD: ALL' > /mnt/etc/sudoers.d/{uname}")
            run_cmd(f"chmod 440 /mnt/etc/sudoers.d/{uname}")

