#!/usr/bin/env bash
# ==============================================================================
# Bootloader Installation (systemd-boot / GRUB) & Services Enablement
# ==============================================================================

bootloader_is_uefi() {
    [ -d "/sys/firmware/efi/efivars" ]
}

bootloader_build_cmdline() {
    local cmdline=""

    # LUKS parameter
    if [ "$IS_LUKS" = true ]; then
        local raw_dev=""
        if [ -n "$LUKS_MAPPED_DEV" ]; then
            # Find backing device of cryptroot
            local map_name="${LUKS_NAME:-cryptroot}"
            raw_dev=$(cryptsetup status "$map_name" 2>/dev/null | awk '/device:/ {print $2}')
        fi

        if [ -n "$raw_dev" ]; then
            local raw_uuid
            raw_uuid=$(blkid -s UUID -o value "$raw_dev")
            cmdline="cryptdevice=UUID=$raw_uuid:${LUKS_NAME:-cryptroot} root=$ROOT_DEV"
        else
            cmdline="root=$ROOT_DEV"
        fi
    else
        cmdline="root=$ROOT_DEV"
    fi

    # Btrfs root flags
    if [ "$FS_TYPE" == "btrfs" ]; then
        cmdline="$cmdline rootflags=subvol=@"
    fi

    cmdline="$cmdline rw quiet"
    echo "$cmdline"
}

bootloader_install() {
    step_header "Installing and Configuring Bootloader"

    local bl_type="${BOOTLOADER:-systemd-boot}"
    local is_uefi=false
    bootloader_is_uefi && is_uefi=true

    # Fallback to GRUB if system is booted in Legacy BIOS
    if [ "$is_uefi" = false ]; then
        warn "Legacy BIOS detected! systemd-boot requires UEFI. Switching to GRUB."
        bl_type="grub"
    fi

    local cmdline
    cmdline=$(bootloader_build_cmdline)
    info "Kernel Command Line: $cmdline"

    if [ "$bl_type" == "systemd-boot" ]; then
        info "Installing systemd-boot to /boot..."
        arch-chroot /mnt bootctl install --esp-path=/boot

        info "Writing /boot/loader/loader.conf..."
        cat <<EOF > /mnt/boot/loader/loader.conf
default arch.conf
timeout 4
console-mode max
editor no
EOF

        local ucode
        ucode=$(detect_cpu_ucode)

        info "Writing /boot/loader/entries/arch.conf..."
        mkdir -p /mnt/boot/loader/entries
        cat <<EOF > /mnt/boot/loader/entries/arch.conf
title Arch Linux
linux /vmlinuz-linux
initrd /$ucode.img
initrd /initramfs-linux.img
options $cmdline
EOF
        success "systemd-boot installed successfully!"

    else
        # GRUB Installation
        if [ "$is_uefi" = true ]; then
            info "Installing GRUB for UEFI..."
            arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
        else
            local target_drive="${TARGET_DISK:-/dev/sda}"
            info "Installing GRUB for BIOS (MBR) on $target_drive..."
            arch-chroot /mnt grub-install --target=i386-pc "$target_drive"
        fi

        info "Configuring GRUB kernel command line in /etc/default/grub..."
        sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"$cmdline\"|" /mnt/etc/default/grub
        sed -i 's/^#\?GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' /mnt/etc/default/grub
        echo "GRUB_DISABLE_OS_PROBER=false" >> /mnt/etc/default/grub

        info "Generating grub.cfg..."
        arch-chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg
        success "GRUB installed and configured successfully!"
    fi

    # Enable requested Systemd services
    bootloader_enable_services

    msgbox "Bootloader Complete" "Bootloader ($bl_type) and services configured successfully!"
}

bootloader_enable_services() {
    step_header "Enabling Systemd Services"

    local svcs=(${SERVICES:-NetworkManager})

    # Auto-add VM guest agent services if detected
    if command -v systemd-detect-virt >/dev/null 2>&1; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null | tr '[:upper:]' '[:lower:]')
        case "$virt" in
            qemu|kvm|bochs) svcs+=("qemu-guest-agent") ;;
            oracle|vbox)    svcs+=("vboxservice") ;;
            vmware)         svcs+=("vmtoolsd") ;;
        esac
    fi

    for svc in "${svcs[@]}"; do
        info "Enabling service: $svc..."
        arch-chroot /mnt systemctl enable "$svc" 2>/dev/null || warn "Failed to enable service $svc (might not be installed)"
    done
}

