#!/usr/bin/env bash
# ==============================================================================
# Users & Passwords Management
# Sets root password, creates regular user with sudo, and handles masked prompts.
# ==============================================================================

users_setup_accounts() {
    step_header "Setting Up Root and User Accounts"

    # 1. Root Password
    local r_pass="$ROOT_PASSWORD"
    if [ -z "$r_pass" ]; then
        info "Root password is empty in vars.conf. Prompting interactively..."
        while true; do
            local p1 p2
            p1=$(passwordbox "Root Password" "Enter new password for ROOT:")
            [ -z "$p1" ] && { msgbox "Error" "Root password cannot be empty."; continue; }
            p2=$(passwordbox "Confirm Password" "Confirm ROOT password:")
            if [ "$p1" == "$p2" ]; then
                r_pass="$p1"
                break
            fi
            msgbox "Mismatch" "Passwords do not match. Try again."
        done
    fi

    info "Setting root password..."
    echo "root:$r_pass" | arch-chroot /mnt chpasswd
    success "Root password set!"

    # 2. Configure Sudoers for wheel group
    mkdir -p /mnt/etc/sudoers.d
    echo "%wheel ALL=(ALL:ALL) ALL" > /mnt/etc/sudoers.d/wheel
    chmod 440 /mnt/etc/sudoers.d/wheel

    # 3. Regular User Account
    local u_name="${USERNAME:-alvin}"
    if [ -n "$u_name" ]; then
        local u_groups="${USER_GROUPS:-wheel,storage,power}"
        local u_shell="${USER_SHELL:-/bin/bash}"

        info "Creating user account '$u_name' (groups: $u_groups, shell: $u_shell)..."
        arch-chroot /mnt useradd -m -G "$u_groups" -s "$u_shell" "$u_name" 2>/dev/null || true

        local u_pass="$USER_PASSWORD"
        if [ -z "$u_pass" ]; then
            info "Password for '$u_name' is empty in vars.conf. Prompting interactively..."
            while true; do
                local p1 p2
                p1=$(passwordbox "User Password" "Enter password for '$u_name':")
                [ -z "$p1" ] && { msgbox "Error" "Password cannot be empty."; continue; }
                p2=$(passwordbox "Confirm Password" "Confirm password for '$u_name':")
                if [ "$p1" == "$p2" ]; then
                    u_pass="$p1"
                    break
                fi
                msgbox "Mismatch" "Passwords do not match. Try again."
            done
        fi

        info "Setting password for user '$u_name'..."
        echo "$u_name:$u_pass" | arch-chroot /mnt chpasswd
        success "User account '$u_name' created with sudo access!"

        if [ "$SUDO_NOPASSWD" = true ]; then
            info "Enabling passwordless sudo for $u_name..."
            echo "$u_name ALL=(ALL:ALL) NOPASSWD: ALL" > "/mnt/etc/sudoers.d/$u_name"
            chmod 440 "/mnt/etc/sudoers.d/$u_name"
        fi
    fi

    msgbox "Users Configured" "Root and user accounts configured successfully!"
}

