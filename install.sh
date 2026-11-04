#!/usr/bin/env bash
# ==============================================================================
# Arch Linux Quick Installer (arch-installer)
# Modular bash installer with archfi-style TUI menu.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "\033[31m[ERROR]\033[0m This script must be run as root (or with sudo)." >&2
    exit 1
fi

# 1. Load configuration file
if [ -f "$SCRIPT_DIR/vars.conf" ]; then
    # shellcheck source=vars.conf
    source "$SCRIPT_DIR/vars.conf"
else
    echo -e "\033[33m[WARN]\033[0m vars.conf not found! Using built-in defaults."
fi

# 2. Source modular libraries
source "$SCRIPT_DIR/lib/01_ui.sh"
source "$SCRIPT_DIR/lib/02_preinstall.sh"
source "$SCRIPT_DIR/lib/03_disk.sh"
source "$SCRIPT_DIR/lib/04_pacstrap.sh"
source "$SCRIPT_DIR/lib/05_system.sh"
source "$SCRIPT_DIR/lib/06_users.sh"
source "$SCRIPT_DIR/lib/bootloader.sh"

install_system_pipeline() {
    step_header "Starting System Installation"

    if ! mountpoint -q /mnt; then
        msgbox "Mount Missing" "Error: /mnt is not mounted!\nPlease format and mount your partitions in Disk Setup first."
        return 1
    fi

    # 1. pacstrap packages from pkglist.txt
    pacstrap_install_packages "$SCRIPT_DIR/pkglist.txt" || return 1

    # 2. System configurations (Timezone, Locales, Keymap, Hostname, initramfs)
    system_configure_core || return 1

    # 3. Users and Passwords
    users_setup_accounts || return 1

    # 4. Bootloader and Services
    bootloader_install || return 1

    # Final cleanup
    step_header "Installation Completed Successfully!"
    echo -e "${BOLD}${GREEN}======================================================${RESET}"
    echo -e "${BOLD}${GREEN}  ARCH LINUX HAS BEEN SUCCESSFULLY INSTALLED!         ${RESET}"
    echo -e "${BOLD}${GREEN}======================================================${RESET}"
    echo -e "You can now safely unmount and reboot into your new system:"
    echo -e "  ${CYAN}# umount -R /mnt && reboot${RESET}\n"

    msgbox "Installation Complete" "Arch Linux installation is complete!\n\nYou can now reboot into your new system."
}

main_menu() {
    while true; do
        local choice
        choice=$(menu_dialog "Arch Linux Installer" "Welcome to Arch Linux Installer! Choose a step:" \
            "1" "Pre-Installation (Wi-Fi, Internet Test, Time & Mirrors)" \
            "2" "Disk Setup (cfdisk, LUKS, LVM, Format & Mount, lsblk)" \
            "3" "Install System (Pacstrap, Config, Users, Bootloader)" \
            "4" "View Disk & Mount Layout (lsblk)" \
            "5" "Reboot System" \
            "0" "Exit to Shell")

        case "$choice" in
            1) preinstall_menu ;;
            2) disk_menu ;;
            3) install_system_pipeline ;;
            4) show_lsblk ;;
            5)
                if yesno "Reboot" "Are you sure you want to unmount and reboot now?"; then
                    clear
                    info "Unmounting /mnt and rebooting..."
                    umount -R /mnt 2>/dev/null || true
                    swapoff -a 2>/dev/null || true
                    reboot
                fi
                ;;
            0|"")
                clear
                info "Exiting Arch Linux Installer."
                break
                ;;
        esac
    done
}

# Parse command line flags
UNATTENDED=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--unattended)
            UNATTENDED=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

if [ "$UNATTENDED" = true ]; then
    info "Running unattended installation..."
    preinstall_check_internet || true
    preinstall_setup_time || true
    preinstall_configure_pacman || true
    install_system_pipeline
else
    main_menu
fi

