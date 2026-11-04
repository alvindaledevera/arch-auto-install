#!/usr/bin/env bash
# ==============================================================================
# System Configuration: Timezone, Locale, Keymap, Hostname, Initramfs (mkinitcpio)
# ==============================================================================

system_configure_core() {
    step_header "Configuring Target System (Chroot)"

    local tz="${TIMEZONE:-Asia/Manila}"
    local loc="${LOCALE:-en_US.UTF-8}"
    local km="${KEYMAP:-us}"
    local host="${HOSTNAME:-arch}"

    # 1. Timezone
    info "Setting timezone to $tz..."
    arch-chroot /mnt ln -sf "/usr/share/zoneinfo/$tz" /etc/localtime
    arch-chroot /mnt hwclock --systohc

    # 2. Locale
    info "Configuring locale $loc..."
    sed -i "s/^#\?$loc/$loc/" /mnt/etc/locale.gen
    echo "$loc UTF-8" >> /mnt/etc/locale.gen
    arch-chroot /mnt locale-gen
    echo "LANG=$loc" > /mnt/etc/locale.conf

    # 3. Keymap
    info "Setting console keymap to $km..."
    echo "KEYMAP=$km" > /mnt/etc/vconsole.conf

    # 4. Hostname & Hosts
    info "Setting hostname to '$host'..."
    echo "$host" > /mnt/etc/hostname
    cat <<EOF > /mnt/etc/hosts
127.0.0.1   localhost
::1         localhost
127.0.1.1   $host.localdomain $host
EOF

    # 5. mkinitcpio HOOKS
    system_configure_mkinitcpio

    success "Core system settings configured successfully!"
}

system_configure_mkinitcpio() {
    info "Configuring /etc/mkinitcpio.conf hooks..."

    local hooks="base udev autodetect modconf kms keyboard keymap consolefont block"

    # Add encrypt hook if LUKS is enabled
    [ "$IS_LUKS" = true ] && hooks="$hooks encrypt"

    # Add lvm2 hook if LVM is enabled
    [ "$IS_LVM" = true ] && hooks="$hooks lvm2"

    hooks="$hooks filesystems"

    # Btrfs does not require fsck
    [ "$FS_TYPE" != "btrfs" ] && hooks="$hooks fsck"

    info "Setting HOOKS=($hooks)"
    sed -i "s/^HOOKS=(.*/HOOKS=($hooks)/" /mnt/etc/mkinitcpio.conf

    info "Regenerating initramfs images (mkinitcpio -P)..."
    arch-chroot /mnt mkinitcpio -P
}

