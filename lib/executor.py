"""
Command execution and logging utility for Arch Auto-Installer.
Supports dry-run simulation, colorized terminal output, and secure input handling.
"""

import subprocess
import sys
from typing import Optional, List, Union

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"

DRY_RUN = False


def set_dry_run(enabled: bool):
    global DRY_RUN
    DRY_RUN = enabled


def is_dry_run() -> bool:
    return DRY_RUN


def log_info(msg: str):
    print(f"{BLUE}[INFO]{RESET} {msg}")


def log_step(step_num: int, total_steps: int, title: str):
    print(f"\n{BOLD}{CYAN}=== Step {step_num}/{total_steps}: {title} ==={RESET}\n")


def log_success(msg: str):
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def log_warn(msg: str):
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def log_error(msg: str):
    print(f"{RED}[ERROR]{RESET} {msg}", file=sys.stderr)


def run_cmd(
    cmd: Union[str, List[str]],
    check: bool = True,
    chroot: bool = False,
    input_text: Optional[str] = None,
    capture_output: bool = False,
    sensitive_mask: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Execute a shell or chroot command.
    If DRY_RUN is enabled, prints the command and skips actual execution.
    """
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd

    if chroot:
        # arch-chroot /mnt bash -c '...'
        escaped = cmd_str.replace("'", "'\\''")
        final_cmd = f"arch-chroot /mnt bash -c '{escaped}'"
    else:
        final_cmd = cmd_str

    display_cmd = final_cmd
    if sensitive_mask and sensitive_mask in display_cmd:
        display_cmd = display_cmd.replace(sensitive_mask, "******")

    if DRY_RUN:
        print(f"{YELLOW}[DRY-RUN]{RESET} {display_cmd}")
        # Return a mock completed process
        return subprocess.CompletedProcess(
            args=final_cmd,
            returncode=0,
            stdout="",
            stderr=""
        )

    print(f"{CYAN}>> {display_cmd}{RESET}")

    stdin_data = input_text.encode("utf-8") if input_text is not None else None

    try:
        proc = subprocess.run(
            final_cmd,
            shell=True,
            check=check,
            input=stdin_data,
            capture_output=capture_output,
            text=capture_output
        )
        return proc
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed with exit code {e.returncode}: {display_cmd}")
        if capture_output and e.stderr:
            log_error(f"Error output: {e.stderr.strip()}")
        raise

