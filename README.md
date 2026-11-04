# Arch Linux Automated Installer

A declarative, transparent, and modular Arch Linux installer driven by a single JSON configuration file (similar to `docker-compose.yml`). Designed for easy disaster recovery, system re-installation, and reproducible deployments across physical machines (NVMe, SSD, HDD) and Virtual Machines (QEMU, KVM, VirtualBox, VMware).

---

## Key Features

- **JSON with Comments (JSONC)**: You can freely write comments (`//` or `#`) and trailing commas directly inside `config.json` without syntax errors!
- **Universal Drive Support**: Works out of the box with NVMe SSDs (`/dev/nvme0n1`), SATA SSDs & HDDs (`/dev/sda`), VirtIO VM disks (`/dev/vda`), and SD cards (`/dev/mmcblk0`).
- **Full VM Support**:
  - Automatically detects if running inside **QEMU / KVM**, **VirtualBox**, or **VMware** and auto-installs guest agents (`qemu-guest-agent`, `virtualbox-guest-utils`, `open-vm-tools`).
  - Supports both **UEFI (OVMF)** and **Legacy BIOS** boot modes.
- **Dual-Boot & Format Protection**:
  - `clean_install` mode: Automatically creates partitions and formats a dedicated drive.
  - `dual_boot` mode: Reuses your existing EFI partition without wiping or formatting it, preserving Windows or other operating systems.
- **Full `--dry-run` Simulation**: Simulates every single command (`sgdisk`, `cryptsetup`, `mkfs`, `pacstrap`, `arch-chroot`) in the terminal with zero changes written to disk.
- **LUKS2 Encryption & LVM**: Optional full-disk encryption with automatic `mkinitcpio` hooks and bootloader kernel arguments.
- **Btrfs Subvolumes & Ext4**: Pre-configured subvolumes (`@`, `@home`, `@snapshots`, `@var_log`) with zstd compression, or traditional Ext4.
- **Interactive Password Safeguard**: If passwords are set to `null`, the installer prompts with masked input (`getpass`) so secrets are never stored in plain text.
- **Zero Compilation**: Written in Python 3 using **only standard library modules** (pre-installed on the official Arch Linux ISO).

---

## Drive Types & Compatibility Reference

The installer dynamically detects drive naming schemes and handles partition numbers accordingly:

| Drive Type | Device Example | Generated Partition Example | Common Use Case |
| :--- | :--- | :--- | :--- |
| **NVMe M.2 SSD** | `/dev/nvme0n1` | `/dev/nvme0n1p1`, `p2`, `p3` | Modern laptops and desktop PCs |
| **SATA SSD / HDD** | `/dev/sda` | `/dev/sda1`, `/dev/sda2`, `/dev/sda3` | 2.5" / 3.5" SATA drives & VirtualBox |
| **VirtIO VM Disk** | `/dev/vda` | `/dev/vda1`, `/dev/vda2`, `/dev/vda3` | QEMU / KVM / Proxmox Virtual Machines |
| **Xen VM Disk** | `/dev/xvda` | `/dev/xvda1`, `/dev/xvda2`, `/dev/xvda3` | AWS EC2 / Xen hypervisors |
| **eMMC / SD Card** | `/dev/mmcblk0` | `/dev/mmcblk0p1`, `p2`, `p3` | Single Board Computers & SD cards |

To view your exact drive name in the Arch Live ISO:
```bash
lsblk
```

---

## Quickstart Guide

### 1. Boot the Arch Linux Live ISO
Boot your computer or Virtual Machine from the official Arch Linux ISO.

### 2. Connect to the Internet
- **Ethernet / VM NAT**: Connected automatically via DHCP.
- **Wi-Fi**:
  ```bash
  iwctl station wlan0 connect "Your-Wi-Fi-SSID"
  ```

### 3. Clone or Download the Installer
```bash
git clone https://github.com/your-username/arch-auto-install.git
cd arch-auto-install
```

### 4. Choose a Configuration
You can copy the heavily commented reference file or use a preset profile:

```bash
# Option A: Self-documenting config with comments
cp config.annotated.jsonc config.json
nano config.json

# Option B: Preset for Virtual Machines (QEMU/KVM with /dev/vda)
cp profiles/vm-qemu.json config.json
nano config.json

# Option C: Preset for Physical PC (Btrfs + LUKS encryption)
cp profiles/btrfs-luks.json config.json
nano config.json
```

### 5. Preview with Dry-Run
Always test first! This prints every command without making any changes to your drive:
```bash
python3 install.py --dry-run
```

### 6. Run the Installation
```bash
python3 install.py
```
When complete, unmount and reboot into your new Arch Linux system:
```bash
reboot
```

---

## Pre-Made Profiles

| Profile | Command Shortcut | Description |
| :--- | :--- | :--- |
| **QEMU / KVM VM** | `python3 install.py --profile vm-qemu` | Optimized for VMs using `/dev/vda`, includes `qemu-guest-agent`, ext4. |
| **Btrfs + LUKS2** | `python3 install.py --profile btrfs-luks` | LUKS2 encryption, Btrfs subvolumes (`@`, `@home`, `@snapshots`, `@var_log`), zstd. |
| **LVM + LUKS2** | `python3 install.py --profile lvm-luks` | LUKS2 + LVM (`root`, `swap`, `home`), Ext4, GRUB. |
| **Dual Boot** | `python3 install.py --profile dual-boot` | Preserves existing Windows EFI partition, formats only Arch root, enables `os-prober`. |
| **Simple Ext4** | `python3 install.py --profile simple-ext4` | Clean install on `/dev/sda` with Ext4 and systemd-boot (unencrypted). |

---

## Configuration Wiki & Field Reference

Every configurable field in `config.json` (or `config.annotated.jsonc`) is documented below:

### `system`
| Field | Type | Possible Values | Description |
| :--- | :--- | :--- | :--- |
| `hostname` | String | e.g. `"archlinux"`, `"my-vm"`, `"workstation"` | System hostname assigned to `/etc/hostname` and `/etc/hosts`. |
| `timezone` | String | e.g. `"Asia/Manila"`, `"UTC"`, `"America/New_York"` | Timezone from `/usr/share/zoneinfo/`. |
| `locale` | String | e.g. `"en_US.UTF-8"`, `"fil_PH.UTF-8"`, `"ja_JP.UTF-8"` | Generated in `/etc/locale.gen` and set in `/etc/locale.conf`. |
| `keymap` | String | e.g. `"us"`, `"uk"`, `"de-latin1"` | Console keyboard layout in `/etc/vconsole.conf`. |

### `storage`
| Field | Type | Possible Values | Description |
| :--- | :--- | :--- | :--- |
| `mode` | String | `"clean_install"` or `"dual_boot"` | `"clean_install"` wipes and partitions the target drive automatically. `"dual_boot"` reuses existing partitions without wiping the disk. |
| `device` | String | `"/dev/nvme0n1"`, `"/dev/sda"`, `"/dev/vda"` | Target storage disk (used in `clean_install` mode). |
| `wipe` | Boolean | `true` or `false` | Confirmation safeguard to wipe partition tables. |
| `efi_size` | String | `"512M"`, `"1024M"`, `"1G"` | Size of the EFI System Partition (UEFI mode). |
| `swap_size` | String | `"4G"`, `"8G"`, `"none"` | Size of the dedicated swap partition. Set to `"none"` to skip. |
| `encryption.enabled` | Boolean | `true` or `false` | Enable LUKS2 encryption for root storage. |
| `encryption.type` | String | `"luks2"` (recommended) or `"luks1"` | LUKS format specification. |
| `encryption.password` | String / `null` | `null` (recommended) or `"mypassword"` | If `null`, securely prompts with masked input during install. |
| `filesystem.type` | String | `"btrfs"` or `"ext4"` | Filesystem format for root. |
| `filesystem.btrfs_subvolumes`| Array | e.g. `[{"name": "@", "mount": "/"}]` | Subvolumes created on Btrfs root. |
| `filesystem.mount_options` | Array | `["noatime", "compress=zstd:1"]` | Mount options passed to `mount` and written to `fstab`. |

### `storage.partitions` *(Dual Boot Mode Only)*
| Field | Type | Description |
| :--- | :--- | :--- |
| `partitions.efi.device` | String | Existing EFI partition (e.g. `"/dev/nvme0n1p1"`). |
| `partitions.efi.format` | Boolean | **Keep `false`** so Windows boot files are preserved! |
| `partitions.root.device`| String | Target partition for Arch Linux root (e.g. `"/dev/nvme0n1p5"`). |
| `partitions.root.format`| Boolean | `true` to format the Arch root partition. |

### `pacman` & `mirrors`
| Field | Type | Possible Values | Description |
| :--- | :--- | :--- | :--- |
| `pacman.parallel_downloads` | Integer | `1` to `10` (default: `5`) | Simultaneous parallel package downloads. |
| `pacman.multilib` | Boolean | `true` or `false` | Enables 32-bit `[multilib]` repository (needed for Steam, Wine). |
| `pacman.color` | Boolean | `true` or `false` | Enables colored pacman output. |
| `mirrors.reflector` | Boolean | `true` or `false` | Automatically ranks the fastest live Arch mirrors. |
| `mirrors.countries` | Array | `["Worldwide"]` or `["Philippines", "Singapore"]` | Filter reflector by mirror country. |
| `mirrors.sort` | String | `"rate"`, `"score"`, `"delay"` | Sort algorithm for reflector. |

### `packages`
| Field | Type | Description |
| :--- | :--- | :--- |
| `packages.base` | Array | Core base packages (e.g. `["base", "base-devel", "linux", "linux-firmware"]`). |
| `packages.ucode` | String | `"auto"` (auto-detects Intel vs AMD from `/proc/cpuinfo`), `"intel-ucode"`, or `"amd-ucode"`. |
| `packages.system` | Array | Essential utilities (`networkmanager`, `git`, `vim`, `sudo`, `zsh`, etc.). |
| `packages.additional` | Array | Your custom apps (`docker`, `docker-compose`, `htop`, `tmux`, etc.). |

### `bootloader`
| Field | Type | Possible Values | Description |
| :--- | :--- | :--- | :--- |
| `type` | String | `"systemd-boot"` or `"grub"` | Bootloader choice. (Note: On Legacy BIOS systems, the installer automatically selects GRUB). |

### `users`
| Field | Type | Description |
| :--- | :--- | :--- |
| `root_password` | String / `null` | Root password. If `null`, prompts interactively. |
| `accounts[].username` | String | Username to create. |
| `accounts[].password` | String / `null` | User password. If `null`, prompts interactively. |
| `accounts[].groups` | Array | Groups assigned to user (e.g. `["wheel", "docker", "storage"]`). |
| `accounts[].shell` | String | Login shell (`"/bin/bash"`, `"/bin/zsh"`). |
| `accounts[].sudo_nopasswd`| Boolean | `true` to allow `sudo` without entering a password. |

### `services`
| Field | Type | Description |
| :--- | :--- | :--- |
| `services` | Array | Systemd services to automatically enable (`["NetworkManager", "docker", "sshd"]`). |

---

## Testing in a Virtual Machine (Quick Steps)

If you want to test this script inside a VM (VirtualBox or QEMU/KVM):
1. Create a VM with at least 20GB disk space and 2GB+ RAM.
2. Attach the official Arch Linux ISO.
3. Boot the VM.
4. Run:
   ```bash
   git clone <your-repo> arch-auto-install
   cd arch-auto-install
   python3 install.py --profile vm-qemu
   ```
5. The installer will partition the `/dev/vda` disk, format it, install Arch + `qemu-guest-agent`, setup the bootloader, and prepare the system for immediate reboot!
