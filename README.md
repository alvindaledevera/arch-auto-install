# Arch Linux Automated Installer

A declarative, transparent, and modular Arch Linux installer driven by a single JSON configuration file (similar to `docker-compose.yml`). Designed for easy disaster recovery, system re-installation, and reproducible deployments across multiple machines.

---

## Features

- **Declarative Configuration**: Define everything in `config.json` (hostname, timezone, locale, partitions, filesystems, packages, users).
- **Zero External Dependencies**: Written in Python 3 using **only standard library modules** (pre-installed out of the box on official Arch Linux ISOs). No compilation, build step, or `pip install` required.
- **Dual-Boot & Format Protection**:
  - `clean_install` mode: Automatically creates partitions and formats a dedicated drive.
  - `dual_boot` mode: Reuses your existing EFI partition without wiping or formatting it, preserving Windows or other operating systems.
- **Full `--dry-run` Mode**: Simulates every single command (`sgdisk`, `cryptsetup`, `mkfs`, `pacstrap`, `arch-chroot`) in the terminal with zero changes written to disk.
- **LUKS2 Encryption**: Optional full-disk or partition encryption with automatic `mkinitcpio` hooks and bootloader kernel arguments.
- **LVM Support**: Logical Volume Management for swap, root, and home volumes.
- **Btrfs Subvolumes & Ext4**: Pre-configured subvolumes (`@`, `@home`, `@snapshots`, `@var_log`) with zstd compression, or traditional Ext4.
- **Interactive Password Safeguard**: If passwords are omitted or set to `null`, the installer prompts with masked input (`getpass`) so secrets are never stored in plain text.
- **Fast Mirror Ranking & Pacman Tuning**: Automatic `reflector` ranking and enabled `ParallelDownloads` on both the live installer and the installed system.

---

## Quickstart (Arch Linux Live ISO)

### 1. Boot the Official Arch Linux Live USB
Boot your machine into UEFI mode using the latest official Arch Linux installation media.

### 2. Connect to the Internet
- **Ethernet**: Usually connects automatically via DHCP.
- **Wi-Fi**:
  ```bash
  iwctl
  # station wlan0 scan
  # station wlan0 get-networks
  # station wlan0 connect "Your-SSID"
  # exit
  ```

### 3. Clone or Download This Repository
```bash
git clone https://github.com/your-username/arch-auto-install.git
cd arch-auto-install
```

*(Alternatively, if you don't have git installed on the live image or just want a single script, you can clone or copy it via USB/wget).*

### 4. Choose or Edit Your Configuration
Copy the example configuration or choose a pre-made profile:
```bash
# Option A: Start from the complete example
cp config.example.json config.json
nano config.json

# Option B: Use a preset profile
cp profiles/btrfs-luks.json config.json
nano config.json
```

### 5. Preview with Dry-Run
Run a safe simulation to inspect every command that will execute on your system:
```bash
python3 install.py --dry-run
```

### 6. Run the Installation
Once verified, run the installer:
```bash
python3 install.py
```
After completion, simply unmount and reboot:
```bash
reboot
```

---

## Pre-Made Profiles

| Profile | File | Description |
| :--- | :--- | :--- |
| **Btrfs + LUKS2** | [`profiles/btrfs-luks.json`](profiles/btrfs-luks.json) | Modern UEFI setup with LUKS2 encryption and Btrfs subvolumes (`@`, `@home`, `@snapshots`, `@var_log`), zstd compression, and systemd-boot. |
| **LVM + LUKS2** | [`profiles/lvm-luks.json`](profiles/lvm-luks.json) | Enterprise-style setup with LUKS2 encryption, LVM volume group, Ext4 root/home, and GRUB. |
| **Dual Boot** | [`profiles/dual-boot.json`](profiles/dual-boot.json) | Reuses existing Windows EFI without formatting, installs Arch onto target partition, and enables `os-prober` in GRUB. |
| **Simple Ext4** | [`profiles/simple-ext4.json`](profiles/simple-ext4.json) | Minimalist UEFI setup with Ext4 filesystem and systemd-boot (no encryption). |

You can invoke any profile directly without copying:
```bash
python3 install.py --profile btrfs-luks --dry-run
```

---

## Configuration Reference (`config.json`)

### 1. System Settings
```json
"system": {
  "hostname": "archlinux",
  "timezone": "Asia/Manila",
  "locale": "en_US.UTF-8",
  "keymap": "us"
}
```

### 2. Storage Modes

#### Mode A: Clean Install (Dedicated Drive)
Wipes and automatically partitions the specified drive:
```json
"storage": {
  "mode": "clean_install",
  "device": "/dev/nvme0n1",
  "wipe": true,
  "efi_size": "1024M",
  "swap_size": "8G",
  "encryption": {
    "enabled": true,
    "type": "luks2",
    "device_name": "cryptroot",
    "password": null
  },
  "filesystem": {
    "type": "btrfs",
    "btrfs_subvolumes": [
      { "name": "@", "mount": "/" },
      { "name": "@home", "mount": "/home" },
      { "name": "@snapshots", "mount": "/.snapshots" },
      { "name": "@var_log", "mount": "/var/log" }
    ],
    "mount_options": ["noatime", "compress=zstd:1"]
  }
}
```

#### Mode B: Dual Boot (Preserves Existing Partitions)
Never wipes the disk. Specifies individual partition targets and whether to format them:
```json
"storage": {
  "mode": "dual_boot",
  "partitions": {
    "efi": {
      "device": "/dev/nvme0n1p1",
      "format": false,
      "mount": "/boot"
    },
    "root": {
      "device": "/dev/nvme0n1p5",
      "format": true
    },
    "swap": {
      "device": "/dev/nvme0n1p6",
      "format": true
    }
  },
  "filesystem": {
    "type": "ext4",
    "mount_options": ["noatime"]
  }
},
"dual_boot": {
  "enabled": true,
  "os_prober": true
}
```

### 3. Pacman & Mirrors
```json
"pacman": {
  "parallel_downloads": 5,
  "multilib": true,
  "color": true
},
"mirrors": {
  "reflector": true,
  "countries": ["Worldwide"],
  "protocol": "https",
  "latest": 10,
  "sort": "rate"
}
```

### 4. Packages
```json
"packages": {
  "base": ["base", "base-devel", "linux", "linux-firmware", "linux-headers"],
  "ucode": "auto",
  "system": ["networkmanager", "git", "vim", "sudo", "openssh", "curl", "zsh"],
  "additional": ["docker", "docker-compose", "htop", "neovim", "tmux", "rsync"]
}
```
*Note: `ucode: "auto"` inspects `/proc/cpuinfo` and installs either `intel-ucode` or `amd-ucode` automatically.*

### 5. Bootloader
Choose between `"systemd-boot"` or `"grub"`.
```json
"bootloader": {
  "type": "systemd-boot"
}
```

### 6. Users & Passwords
```json
"users": {
  "root_password": null,
  "accounts": [
    {
      "username": "alvin",
      "password": null,
      "groups": ["wheel", "storage", "power", "docker"],
      "shell": "/bin/bash",
      "sudo_nopasswd": false
    }
  ]
}
```
> [!TIP]
> If `password` is set to `null` or `""`, the installer will interactively prompt you with masked input (`getpass`) during the run.

### 7. Services & Post-Install Commands
```json
"services": [
  "NetworkManager",
  "docker",
  "sshd"
],
"post_install": {
  "commands": [
    "systemctl enable fstrim.timer"
  ]
}
```

---

## Project Structure

```
arch-auto-install/
├── install.py                 # Main CLI installer engine (executable)
├── config.example.json        # Comprehensive reference configuration
├── profiles/                  # Pre-configured installation profiles
│   ├── btrfs-luks.json        # LUKS2 + Btrfs subvolumes
│   ├── lvm-luks.json          # LUKS2 + LVM + Ext4
│   ├── dual-boot.json         # Dual-boot with Windows
│   └── simple-ext4.json       # Simple unencrypted Ext4
├── lib/
│   ├── config.py              # Configuration validation and credential resolver
│   ├── executor.py            # Command runner with dry-run support & color logging
│   ├── disk.py                # Disk partitioning (sgdisk), LUKS, LVM, formatting & mounts
│   ├── pacman.py              # Reflector, pacman.conf, microcode detection, pacstrap
│   ├── system.py              # Timezone, locale-gen, console keymap, hostname, mkinitcpio
│   ├── users.py               # User accounts, passwords, sudoers
│   ├── bootloader.py          # systemd-boot and GRUB bootloader setup
│   └── post.py                # Systemd services and unmounting
└── tests/
    └── test_config.py         # Unit tests validating schema and profiles
```

---

## Running Unit Tests

To verify that your configuration files are syntactically valid before running an install:
```bash
python3 -m unittest discover tests
```

