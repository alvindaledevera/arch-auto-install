#!/usr/bin/env bash
# ==============================================================================
# Pacstrap & Fstab Generation
# ==============================================================================

detect_cpu_ucode() {
    if grep -q "GenuineIntel" /proc/cpuinfo 2>/dev/null; then
        echo "intel-ucode"
    elif grep -q "AuthenticAMD" /proc/cpuinfo 2>/dev/null; then
        echo "amd-ucode"
    else
        echo "intel-ucode"
    fi
}

detect_vm_guest_pkgs() {
    if command -v systemd-detect-virt >/dev/null 2>&1; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null | tr '[:upper:]' '[:lower:]')
        case "$virt" in
            qemu|kvm|bochs) echo "qemu-guest-agent" ;;
            oracle|vbox)    echo "virtualbox-guest-utils" ;;
            vmware)         echo "open-vm-tools" ;;
        esac
    fi
}

pacstrap_install_packages() {
    step_header "Installing Packages to /mnt (pacstrap)"

    # Verify /mnt is mounted
    if ! mountpoint -q /mnt; then
        error "/mnt is not mounted! Please format and mount your partitions in Disk Setup first."
        msgbox "Mount Error" "/mnt is not mounted!\nPlease complete Step 2 (Disk Setup) before installing."
        return 1
    fi

    local pkg_file="${1:-pkglist.txt}"
    if [ ! -f "$pkg_file" ]; then
        error "Package list file '$pkg_file' not found!"
        msgbox "Error" "Package list file '$pkg_file' not found!"
        return 1
    fi

    # 1. Parse pkglist.txt (strip comments and blank lines)
    local packages=()
    while read -r line; do
        # Ignore comments (#) and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$line" ]] && continue
        packages+=("$line")
    done < "$pkg_file"

    # 2. Add CPU microcode
    local ucode
    ucode=$(detect_cpu_ucode)
    info "Detected CPU microcode: $ucode"
    packages+=("$ucode")

    # 3. Add VM tools if inside a VM
    local vm_pkg
    vm_pkg=$(detect_vm_guest_pkgs)
    if [ -n "$vm_pkg" ]; then
        info "Virtual machine detected, adding $vm_pkg"
        packages+=("$vm_pkg")
    fi

    # 4. Add storage & filesystem packages
    [ "$FS_TYPE" == "btrfs" ] && packages+=("btrfs-progs")
    [ "$IS_LUKS" = true ] && packages+=("cryptsetup")
    [ "$IS_LVM" = true ] && packages+=("lvm2")

    # 5. Add bootloader packages
    if [ "$BOOTLOADER" == "grub" ]; then
        packages+=("grub" "efibootmgr" "os-prober")
    else
        packages+=("efibootmgr")
    fi

    # Deduplicate package list
    local deduped_pkgs=()
    read -r -a deduped_pkgs < <(echo "${packages[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' ')

    info "Installing ${#deduped_pkgs[@]} packages to /mnt with pacstrap..."
    echo -e "${CYAN}Packages:${RESET} ${deduped_pkgs[*]}"
    echo ""

    pacstrap -K /mnt "${deduped_pkgs[@]}"
    local code=$?

    if [ $code -ne 0 ]; then
        error "pacstrap failed with exit code $code!"
        msgbox "Pacstrap Error" "Package installation failed. Please check your internet connection and try again."
        return $code
    fi

    success "Base system installed successfully!"

    # Copy pacman.conf to installed system
    info "Copying /etc/pacman.conf to installed target system..."
    cp /etc/pacman.conf /mnt/etc/pacman.conf

    # Generate fstab
    info "Generating /etc/fstab with UUIDs..."
    genfstab -U /mnt >> /mnt/etc/fstab

    success "Generated /etc/fstab:"
    cat /mnt/etc/fstab

    msgbox "Pacstrap & Fstab Complete" "Packages installed successfully and /etc/fstab generated with UUIDs!"
    return 0
}

