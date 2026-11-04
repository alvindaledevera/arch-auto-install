#!/usr/bin/env bash
# ==============================================================================
# Pre-Installation Tasks: Network, Time & Mirrors
# ==============================================================================

preinstall_connect_wifi() {
    if ! command -v iwctl >/dev/null 2>&1; then
        msgbox "Wi-Fi Tool Missing" "iwctl command not found. If on Ethernet, no Wi-Fi setup is needed."
        return
    fi

    clear
    step_header "Launching Interactive Wi-Fi Setup (iwctl)"
    echo -e "${YELLOW}Tip in iwctl:${RESET}"
    echo "  station wlan0 scan"
    echo "  station wlan0 get-networks"
    echo "  station wlan0 connect <Your-SSID>"
    echo "  exit"
    echo ""
    pause_key "Press [Enter] to launch iwctl..."
    iwctl
}

preinstall_check_internet() {
    step_header "Testing Internet Connectivity"
    info "Pinging archlinux.org..."
    if ping -c 2 -W 3 archlinux.org >/dev/null 2>&1 || ping -c 2 -W 3 1.1.1.1 >/dev/null 2>&1; then
        success "Internet connection is active!"
        msgbox "Internet Status" "Internet connection is ACTIVE and working!"
    else
        error "No internet connection detected!"
        msgbox "Internet Status" "ERROR: No internet connection! Please connect to Wi-Fi or plug in Ethernet."
    fi
}

preinstall_setup_time() {
    step_header "Configuring Timezone & NTP"
    local tz="${TIMEZONE:-Asia/Manila}"

    info "Enabling NTP synchronization..."
    timedatectl set-ntp true

    if [ -f "/usr/share/zoneinfo/$tz" ]; then
        info "Setting timezone to $tz..."
        timedatectl set-timezone "$tz"
    fi

    local cur_time
    cur_time="$(timedatectl status | grep -E 'Time zone|Local time|NTP service')"
    success "Clock synchronized!"
    msgbox "Time Synchronization" "Time configured successfully:\n\n$cur_time"
}

preinstall_configure_pacman() {
    step_header "Tuning Pacman & Mirrors"
    local downloads="${PARALLEL_DOWNLOADS:-5}"

    info "Setting ParallelDownloads = $downloads in /etc/pacman.conf..."
    sed -i "s/^#\?ParallelDownloads = .*/ParallelDownloads = $downloads/" /etc/pacman.conf
    sed -i 's/^#Color/Color/' /etc/pacman.conf

    if [ "$REFLECTOR_ENABLED" = true ] && command -v reflector >/dev/null 2>&1; then
        local country_arg=""
        if [ -n "$REFLECTOR_COUNTRY" ] && [ "$REFLECTOR_COUNTRY" != "Worldwide" ]; then
            country_arg="--country '$REFLECTOR_COUNTRY'"
        fi

        info "Ranking fast mirrors using reflector ($REFLECTOR_COUNTRY)..."
        eval reflector $country_arg --protocol https --latest 10 --sort rate --save /etc/pacman.d/mirrorlist
        success "Mirrorlist ranked and updated!"
    else
        info "Reflector skipped or disabled. Updating pacman database..."
    fi

    pacman -Sy --noconfirm
    success "Pacman configuration complete!"
    msgbox "Pacman Configured" "Pacman ParallelDownloads set to $downloads.\nLive mirrors updated and database refreshed!"
}

preinstall_menu() {
    while true; do
        local choice
        choice=$(menu_dialog "Pre-Installation Menu" "Choose a pre-installation action:" \
            "1" "Connect to Wi-Fi (iwctl)" \
            "2" "Test Internet Connection (ping)" \
            "3" "Set Timezone & Enable NTP (timedatectl)" \
            "4" "Configure Pacman & Fast Mirrors (ParallelDownloads)" \
            "5" "Run All Pre-Install Tasks in Sequence" \
            "0" "Back to Main Menu")

        case "$choice" in
            1) preinstall_connect_wifi ;;
            2) preinstall_check_internet ;;
            3) preinstall_setup_time ;;
            4) preinstall_configure_pacman ;;
            5)
                preinstall_check_internet
                preinstall_setup_time
                preinstall_configure_pacman
                ;;
            0|"") break ;;
        esac
    done
}

