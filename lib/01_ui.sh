#!/usr/bin/env bash
# ==============================================================================
# UI & Dialog Helper Library for Arch Linux Installer
# Provides whiptail wrappers with fallback to standard terminal output.
# ==============================================================================

# ANSI Color Codes
BOLD="\033[1m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
MAGENTA="\033[35m"
CYAN="\033[36m"
RESET="\033[0m"

# Terminal check for Whiptail
HAS_WHIPTAIL=false
if command -v whiptail >/dev/null 2>&1 && [ -t 0 ] || [ -e /dev/tty ]; then
    HAS_WHIPTAIL=true
fi

info() {
    echo -e "${BLUE}[INFO]${RESET} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${RESET} $*"
}

error() {
    echo -e "${RED}[ERROR]${RESET} $*" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${RESET} $*"
}

step_header() {
    echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}\n"
}

pause_key() {
    local msg="${1:-Press [Enter] to continue...}"
    echo -e "\n${BOLD}${msg}${RESET}"
    read -r
}

# ------------------------------------------------------------------------------
# Whiptail Dialog Helpers
# ------------------------------------------------------------------------------

msgbox() {
    local title="$1"
    local text="$2"
    if [ "$HAS_WHIPTAIL" = true ]; then
        whiptail --title "$title" --msgbox "$text" 14 70 3>&1 1>&2 2>&3
    else
        echo -e "\n${BOLD}${CYAN}=== $title ===${RESET}\n$text\n"
        pause_key
    fi
}

yesno() {
    local title="$1"
    local prompt="$2"
    local default_yes="${3:-true}"

    if [ "$HAS_WHIPTAIL" = true ]; then
        if [ "$default_yes" = true ]; then
            whiptail --title "$title" --yesno "$prompt" 12 70 3>&1 1>&2 2>&3
        else
            whiptail --title "$title" --defaultno --yesno "$prompt" 12 70 3>&1 1>&2 2>&3
        fi
        return $?
    else
        local d_str="Y/n"
        [ "$default_yes" != true ] && d_str="y/N"
        echo -ne "\n${BOLD}$prompt${RESET} [$d_str]: "
        read -r ans
        ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]')"
        if [ -z "$ans" ]; then
            [ "$default_yes" = true ] && return 0 || return 1
        fi
        [[ "$ans" =~ ^(y|yes)$ ]] && return 0 || return 1
    fi
}

inputbox() {
    local title="$1"
    local prompt="$2"
    local default_val="$3"

    if [ "$HAS_WHIPTAIL" = true ]; then
        local res
        res=$(whiptail --title "$title" --inputbox "$prompt" 12 70 "$default_val" 3>&1 1>&2 2>&3)
        local code=$?
        if [ $code -eq 0 ]; then
            echo "$res"
        else
            echo "$default_val"
        fi
    else
        echo -ne "\n${BOLD}$prompt${RESET} (Default: '$default_val'): "
        read -r ans
        if [ -n "$ans" ]; then
            echo "$ans"
        else
            echo "$default_val"
        fi
    fi
}

passwordbox() {
    local title="$1"
    local prompt="$2"

    if [ "$HAS_WHIPTAIL" = true ]; then
        whiptail --title "$title" --passwordbox "$prompt" 12 70 3>&1 1>&2 2>&3
    else
        echo -ne "\n${BOLD}$prompt${RESET}: "
        read -rs ans
        echo ""
        echo "$ans"
    fi
}

# Display a selection menu.
# Syntax: menu "Title" "Prompt" "tag1" "item1" "tag2" "item2" ...
menu_dialog() {
    local title="$1"
    local prompt="$2"
    shift 2
    local items=("$@")
    local count=$((${#items[@]} / 2))

    if [ "$HAS_WHIPTAIL" = true ]; then
        whiptail --title "$title" --menu "$prompt" 18 75 "$count" "${items[@]}" 3>&1 1>&2 2>&3
    else
        echo -e "\n${BOLD}${CYAN}=== $title ===${RESET}"
        echo -e "$prompt\n"
        local i=0
        while [ $i -lt ${#items[@]} ]; do
            local tag="${items[$i]}"
            local desc="${items[$((i + 1))]}"
            echo -e "  ${BOLD}$tag)${RESET} $desc"
            i=$((i + 2))
        done
        echo -ne "\nEnter choice: "
        read -r ans
        echo "$ans"
    fi
}

show_lsblk() {
    local title="${1:-Current Disk & Partition Layout (lsblk)}"
    local output
    output="$(lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS)"

    if [ "$HAS_WHIPTAIL" = true ]; then
        whiptail --title "$title" --msgbox "$output" 20 78 3>&1 1>&2 2>&3
    else
        echo -e "\n${BOLD}${CYAN}=== $title ===${RESET}\n"
        echo "$output"
        pause_key
    fi
}

