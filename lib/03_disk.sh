#!/usr/bin/env bash
# ==============================================================================
# Disk Setup: Partitioning (cfdisk), LUKS, LVM, Formatting & Mounting
# ==============================================================================

# Internal state variables
TARGET_DISK=""
EFI_PART=""
ROOT_DEV=""
HOME_DEV=""
SWAP_DEV=""
IS_LUKS=false
LUKS_MAPPED_DEV=""
IS_LVM=false

# Helper to get list of disk devices for menu
get_disks_menu_items() {
    local items=()
    while read -r name size type model; do
        items+=("$name" "$size - $model")
    done < <(lsblk -dp -n -o NAME,SIZE,TYPE,MODEL | grep -E "disk")
    echo "${items[@]}"
}

# Helper to get list of partition devices for menu
get_parts_menu_items() {
    local items=()
    while read -r name size type fstype; do
        items+=("$name" "$size ($type $fstype)")
    done < <(lsblk -lp -n -o NAME,SIZE,TYPE,FSTYPE | grep -E "part|lvm|crypt")
    echo "${items[@]}"
}

disk_run_cfdisk() {
    local disks_args
    read -r -a disks_args < <(get_disks_menu_items)

    if [ ${#disks_args[@]} -eq 0 ]; then
        msgbox "No Disks Found" "No storage disks were detected on this machine."
        return
    fi

    local chosen
    chosen=$(menu_dialog "Partition Disk (cfdisk)" "Select a storage drive to partition with cfdisk:" "${disks_args[@]}")
    [ -z "$chosen" ] && return

    TARGET_DISK="$chosen"
    clear
    info "Launching cfdisk on $TARGET_DISK..."
    pause_key "Press [Enter] to launch cfdisk..."
    cfdisk "$TARGET_DISK"

    info "Reloading partition table with partprobe..."
    partprobe "$TARGET_DISK" >/dev/null 2>&1 || true

    show_lsblk "Updated Disk & Partition Layout"
}

disk_setup_luks() {
    local parts_args
    read -r -a parts_args < <(get_parts_menu_items)

    if [ ${#parts_args[@]} -eq 0 ]; then
        msgbox "No Partitions" "Please partition your disk using cfdisk first."
        return
    fi

    local target_part
    target_part=$(menu_dialog "LUKS Encryption" "Select the partition you want to encrypt:" "${parts_args[@]}")
    [ -z "$target_part" ] && return

    if ! yesno "Confirm LUKS Encryption" "Are you sure you want to encrypt $target_part with LUKS2?\n\nWARNING: All existing data on $target_part will be destroyed!"; then
        return
    fi

    local pass1 pass2
    while true; do
        pass1=$(passwordbox "LUKS Passphrase" "Enter encryption passphrase for $target_part:")
        [ -z "$pass1" ] && { msgbox "Error" "Passphrase cannot be empty."; continue; }
        pass2=$(passwordbox "Confirm Passphrase" "Re-enter encryption passphrase:")
        if [ "$pass1" == "$pass2" ]; then
            break
        fi
        msgbox "Mismatch" "Passphrases do not match. Please try again."
    done

    local map_name="${LUKS_NAME:-cryptroot}"
    info "Formatting $target_part with LUKS2..."
    echo -n "$pass1" | cryptsetup luksFormat --type luks2 --batch-mode "$target_part" -
    
    info "Opening LUKS container as /dev/mapper/$map_name..."
    echo -n "$pass1" | cryptsetup open "$target_part" "$map_name" -

    IS_LUKS=true
    LUKS_MAPPED_DEV="/dev/mapper/$map_name"
    ROOT_DEV="$LUKS_MAPPED_DEV"

    success "LUKS encrypted container opened at $LUKS_MAPPED_DEV!"
    msgbox "LUKS Complete" "LUKS container successfully created and opened at:\n$LUKS_MAPPED_DEV"
}

disk_setup_lvm() {
    local parts_args
    read -r -a parts_args < <(get_parts_menu_items)

    local base_pv=""
    if [ "$IS_LUKS" = true ] && [ -n "$LUKS_MAPPED_DEV" ]; then
        base_pv="$LUKS_MAPPED_DEV"
    else
        base_pv=$(menu_dialog "LVM Physical Volume" "Select partition for LVM Physical Volume (PV):" "${parts_args[@]}")
        [ -z "$base_pv" ] && return
    fi

    local vg="${LVM_VG:-vg0}"
    vg=$(inputbox "LVM Volume Group" "Enter Volume Group name:" "$vg")
    [ -z "$vg" ] && vg="vg0"

    info "Initializing LVM on $base_pv (VG: $vg)..."
    pvcreate -f "$base_pv"
    vgcreate -f "$vg" "$base_pv"

    # Swap in LVM
    if yesno "LVM Swap Volume" "Do you want to create a Swap Logical Volume in LVM?"; then
        local swap_sz
        swap_sz=$(inputbox "Swap Size" "Enter swap volume size:" "8G")
        info "Creating swap LV ($swap_sz)..."
        lvcreate -L "$swap_sz" -n swap "$vg"
        SWAP_DEV="/dev/mapper/$vg-swap"
        mkswap "$SWAP_DEV"
        swapon "$SWAP_DEV"
    fi

    # Combined vs Separate /home
    local layout
    layout=$(menu_dialog "Root & Home Layout" "Choose allocation for root (/) and /home in LVM:" \
        "combined" "Magkasama sa iisang volume" \
        "separate" "Hiwalay na Logical Volume para sa /home")

    # 1. Tanungin ang Root LV Size para sa parehong layout
    local default_r_size="${ROOT_SIZE:-40G}"
    local r_size
    r_size=$(inputbox "Root LV Size" "Enter size for root LV (e.g., 40G):" "$default_r_size")
    [ -z "$r_size" ] && r_size="$default_r_size"

    if [ "$layout" == "separate" ]; then
        # 2. Tanungin ang Home LV Size kung separate, na may 100%FREE bilang default/opsyon
        local home_sz
        home_sz=$(inputbox "Home LV Size" "Enter size for /home LV (e.g., 100G or type 100%FREE):" "100%FREE")
        [ -z "$home_sz" ] && home_sz="100%FREE"

        info "Creating separate root LV ($r_size) and home LV ($home_sz)..."
        lvcreate -L "$r_size" -n root "$vg"
        
        if [[ "$home_sz" == *"%"* ]]; then
            lvcreate -l "$home_sz" -n home "$vg"
        else
            lvcreate -L "$home_sz" -n home "$vg"
        fi

        ROOT_DEV="/dev/mapper/$vg-root"
        HOME_DEV="/dev/mapper/$vg-home"
        SEPARATE_HOME=true
    else
        info "Creating combined root LV with size ($r_size)..."
        lvcreate -L "$r_size" -n root "$vg"
        ROOT_DEV="/dev/mapper/$vg-root"
        HOME_DEV=""
        SEPARATE_HOME=false
    fi

    IS_LVM=true
    success "LVM configured on $vg!"
    msgbox "LVM Ready" "LVM setup completed successfully on $vg!\n\nRoot: $ROOT_DEV\nHome: ${HOME_DEV:-Combined in root}\nSwap: ${SWAP_DEV:-None}"
}

disk_format_and_mount() {
    local parts_args
    read -r -a parts_args < <(get_parts_menu_items)

    # 1. Choose Filesystem Type
    local fs_choice
    fs_choice=$(menu_dialog "Filesystem Format" "Choose filesystem for Arch Linux:" \
        "btrfs" "Btrfs (Modern, snapshots, subvolumes @, @home, zstd compress)" \
        "ext4"  "Ext4 (Classic, rock-solid, simplest)")
    [ -n "$fs_choice" ] && FS_TYPE="$fs_choice"

    # 2. Select EFI Partition
    if [ -z "$EFI_PART" ]; then
        EFI_PART=$(menu_dialog "EFI Partition" "Select your EFI System Partition (/boot):" "${parts_args[@]}")
        [ -z "$EFI_PART" ] && return
    fi

    # 3. Select Root Device if not already assigned by LUKS/LVM
    if [ -z "$ROOT_DEV" ]; then
        ROOT_DEV=$(menu_dialog "Root Partition" "Select target partition for Arch Root (/):" "${parts_args[@]}")
        [ -z "$ROOT_DEV" ] && return
    fi

    # Confirmation
    if ! yesno "Confirm Formatting" "Target devices to format and mount:\n\n • EFI:  $EFI_PART\n • Root: $ROOT_DEV (${FS_TYPE})\n • Home: ${HOME_DEV:-Combined}\n • Swap: ${SWAP_DEV:-None}\n\nProceed with formatting and mounting to /mnt?"; then
        return
    fi

    clear
    step_header "Formatting and Mounting Filesystems"

    # Format EFI (FAT32)
    info "Formatting EFI partition $EFI_PART..."
    mkfs.fat -F32 -n EFI "$EFI_PART"

    # Unmount /mnt if previously mounted
    umount -R /mnt 2>/dev/null || true

    # Format & Mount Root
    if [ "$FS_TYPE" == "btrfs" ]; then
        info "Formatting $ROOT_DEV as Btrfs..."
        mkfs.btrfs -f -L archroot "$ROOT_DEV"

        info "Creating Btrfs subvolumes..."
        mkdir -p /mnt
        mount "$ROOT_DEV" /mnt
        btrfs subvolume create /mnt/@
        [ "$SEPARATE_HOME" != true ] && btrfs subvolume create /mnt/@home
        btrfs subvolume create /mnt/@snapshots
        btrfs subvolume create /mnt/@var_log
        umount /mnt

        info "Mounting root subvolume (@) to /mnt..."
        mount -o noatime,compress=zstd:1,subvol=@ "$ROOT_DEV" /mnt
        mkdir -p /mnt/{boot,.snapshots,var/log}
        mount -o noatime,compress=zstd:1,subvol=@snapshots "$ROOT_DEV" /mnt/.snapshots
        mount -o noatime,compress=zstd:1,subvol=@var_log "$ROOT_DEV" /mnt/var/log

        if [ "$SEPARATE_HOME" != true ]; then
            mkdir -p /mnt/home
            mount -o noatime,compress=zstd:1,subvol=@home "$ROOT_DEV" /mnt/home
        fi
    else
        info "Formatting $ROOT_DEV as Ext4..."
        mkfs.ext4 -F -L archroot "$ROOT_DEV"
        mkdir -p /mnt
        mount -o noatime "$ROOT_DEV" /mnt
        mkdir -p /mnt/boot
    fi

    # Mount EFI
    info "Mounting EFI $EFI_PART to /mnt/boot..."
    mkdir -p /mnt/boot
    mount "$EFI_PART" /mnt/boot

    # Format & Mount Separate Home if requested
    if [ "$SEPARATE_HOME" = true ] && [ -n "$HOME_DEV" ]; then
        info "Formatting and mounting separate /home on $HOME_DEV..."
        if [ "$FS_TYPE" == "btrfs" ]; then
            mkfs.btrfs -f -L archhome "$HOME_DEV"
            mkdir -p /mnt/home
            mount -o noatime,compress=zstd:1 "$HOME_DEV" /mnt/home
        else
            mkfs.ext4 -F -L archhome "$HOME_DEV"
            mkdir -p /mnt/home
            mount -o noatime "$HOME_DEV" /mnt/home
        fi
    fi

    success "Filesystems successfully formatted and mounted to /mnt!"
    show_lsblk "Current Mount Status (/mnt)"
}

disk_menu() {
    while true; do
        local choice
        choice=$(menu_dialog "Disk Setup Menu" "Choose a disk preparation step:" \
            "1" "Partition Disk (cfdisk)" \
            "2" "Setup LUKS Disk Encryption (Optional)" \
            "3" "Setup LVM (Optional)" \
            "4" "Format & Mount Filesystems (/mnt)" \
            "5" "Open Encrypted LUKS Partition" \
            "6" "View Current Disk & Mount Layout (lsblk)" \
            "0" "Back to Main Menu")

        case "$choice" in
            1) disk_run_cfdisk ;;
            2) disk_setup_luks ;;
            3) disk_setup_lvm ;;
            4) disk_format_and_mount ;;
            5) open_luks_partition ;;
            6) show_lsblk ;;
            0|"") break ;;
        esac
    done
}