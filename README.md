# Arch Linux Quick Installer (`arch-installer`)

A modular, clean, and maintainable **Bash** installation suite for Arch Linux with an interactive **`archfi`-style TUI menu**. Driven by a simple configuration file (`vars.conf`) and a package list (`pkglist.txt`).

---

## Features

- **`archfi`-Style TUI Menu**: Clean dialog interface using `whiptail` with full arrow-key and enter navigation (identical look and feel to `cfdisk`).
- **Simple Configuration (`vars.conf`)**: Centralized defaults for mirrors, hostname, timezone, locale, filesystem (Btrfs or Ext4), bootloader, and users.
- **Customizable Package List (`pkglist.txt`)**: Simply comment (`#`) or add packages under section headers (`## BASE`, `## Essentials`).
- **Interactive Password Safeguard**: Passwords can be pre-configured in `vars.conf` or left empty (`""`) to securely prompt with masked input during setup.
- **Disk Setup with `cfdisk` & `lsblk`**:
  - Full-screen `cfdisk` partition manager.
  - Optional **LUKS2 disk encryption** wizard.
  - Optional **LVM setup** with volume group and logical volumes.
  - Filesystem formatting for **Btrfs** (with `@`, `@home`, `@snapshots`, `@var_log` subvolumes & zstd compression) or **Ext4**.
  - Built-in **`lsblk` layout viewer** so you can visually verify where Arch Linux will be installed.
- **Pre-Installation Tools**: Interactive Wi-Fi setup (`iwctl`), internet connectivity tester, clock & NTP synchronization, and automatic Pacman mirror ranking (`reflector` + `ParallelDownloads`).

---

## Project Structure

```
arch-auto-install/
├── install.sh             # Main executable TUI menu runner
├── vars.conf              # Central configuration file (variables & defaults)
├── pkglist.txt            # Package list (supports comments and categories)
├── lib/
│   ├── ui.sh              # Whiptail dialog helpers & terminal color formatters
│   ├── preinstall.sh      # Wi-Fi (iwctl), ping test, NTP, and Pacman tuning
│   ├── disk.sh            # cfdisk, LUKS, LVM, mkfs.btrfs/ext4, mount, lsblk
│   ├── pacstrap.sh        # pkglist.txt parser & pacstrap execution
│   ├── system.sh          # Timezone, locale-gen, keymap, hostname, mkinitcpio
│   ├── users.sh           # Root password, user creation, sudoers
│   └── bootloader.sh      # systemd-boot & GRUB installer with kernel cmdline
└── tests/
    └── test_bash_installer.sh  # Automated verification test suite
```

---

## Quickstart (Arch Linux Live ISO)

### 1. Boot the Official Arch Linux Live USB
Boot your target machine or Virtual Machine into the Arch Linux live environment.

### 2. Download or Clone the Installer
```bash
git clone https://github.com/your-username/arch-auto-install.git
cd arch-auto-install
```

### 3. Review or Edit `vars.conf` (Optional)
```bash
nano vars.conf
```
*(You can also adjust options directly inside the TUI menus during installation!)*

### 4. Review or Edit `pkglist.txt` (Optional)
```bash
nano pkglist.txt
```
Uncomment packages you want (e.g. `vim`, `docker`, `openssh`) or add your favorite packages.

### 5. Launch the Installer
```bash
./install.sh
```

---

## TUI Menu Flow

When you run `./install.sh`, you will be greeted by the Main Menu:

```
┌───────────────────────────────────────────────────────────────┐
│                    ARCH LINUX INSTALLER                       │
│                                                               │
│  Welcome to Arch Linux Installer! Choose a step:              │
│                                                               │
│  1  Pre-Installation (Wi-Fi, Internet Test, Time & Mirrors)   │
│  2  Disk Setup (cfdisk, LUKS, LVM, Format & Mount, lsblk)     │
│  3  Install System (Pacstrap, Config, Users, Bootloader)      │
│  4  View Disk & Mount Layout (lsblk)                          │
│  5  Reboot System                                             │
│  0  Exit to Shell                                             │
│                                                               │
│                  <Select>          <Exit>                     │
└───────────────────────────────────────────────────────────────┘
```

### Step 1: Pre-Installation
- **1.1 Connect to Wi-Fi (`iwctl`)**: Guides you through scanning and connecting to your Wi-Fi network.
- **1.2 Test Internet Connection**: Pings `archlinux.org` to confirm connectivity.
- **1.3 Set Timezone & Enable NTP**: Synchronizes system clock using `timedatectl`.
- **1.4 Configure Pacman & Mirrors**: Sets `ParallelDownloads=5` and ranks the fastest live mirrors using `reflector`.

### Step 2: Disk Setup
- **2.1 Partition Disk (`cfdisk`)**: Selects your disk (NVMe, SSD, HDD, or VM `/dev/vda`) and opens `cfdisk` full-screen. Automatically runs `partprobe` upon saving.
- **2.2 Setup LUKS Encryption**: (Optional) Formats and opens an encrypted container using LUKS2.
- **2.3 Setup LVM**: (Optional) Creates a Volume Group and Logical Volumes for root, swap, and optional home.
- **2.4 Format & Mount Filesystems**: Formats EFI (FAT32), Root (Btrfs or Ext4), optional Swap, and mounts them cleanly to `/mnt`.
- **2.5 View Current Disk & Mount Layout (`lsblk`)**: Displays a full-screen tree view of your drives and mountpoints to confirm your setup.

### Step 3: Install System
- **Installs Packages**: Runs `pacstrap` using your customized `pkglist.txt` and automatically detects CPU microcode (Intel/AMD) and VM guest tools.
- **Generates Fstab**: Writes `/etc/fstab` with permanent UUIDs.
- **Configures Core System**: Timezone, Locales (`locale-gen`), Keymap, Hostname, and `mkinitcpio` hooks.
- **Sets Up Users & Passwords**: Configures root password and user account with `sudo` permissions. Prompts interactively with masked input if passwords were left blank in `vars.conf`.
- **Installs Bootloader**: Installs `systemd-boot` (or `GRUB`) with kernel cmdline parameters for LUKS and Btrfs subvolumes.
- **Enables Services**: Automatically enables `NetworkManager` and VM guest agents.

### Step 4: Reboot
Unmounts `/mnt` safely and reboots into your fresh Arch Linux operating system!

---

## Configuration Reference (`vars.conf`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PARALLEL_DOWNLOADS` | `5` | Number of simultaneous package downloads in pacman. |
| `REFLECTOR_ENABLED` | `true` | Automatically ranks fastest mirrors. |
| `REFLECTOR_COUNTRY` | `"Worldwide"` | Mirror country filter (e.g. `"Philippines,Singapore"`). |
| `HOSTNAME` | `"arch"` | Machine hostname. |
| `TIMEZONE` | `"Asia/Manila"` | System timezone from `/usr/share/zoneinfo/`. |
| `LOCALE` | `"en_US.UTF-8"` | Generated locale. |
| `KEYMAP` | `"us"` | Console keyboard layout. |
| `FS_TYPE` | `"btrfs"` | Target filesystem: `"btrfs"` or `"ext4"`. |
| `SEPARATE_HOME` | `false` | `false` = combined in root (default), `true` = separate `/home`. |
| `ROOT_SIZE` | `"50G"` | Size of root partition/LV if separate `/home` is used. |
| `LUKS_ENABLED` | `false` | Enable full disk/partition encryption. |
| `LVM_ENABLED` | `false` | Enable Logical Volume Management. |
| `BOOTLOADER` | `"systemd-boot"` | `"systemd-boot"` (fastest for UEFI) or `"grub"`. |
| `ROOT_PASSWORD` | `""` | Root password (prompts securely if left empty). |
| `USERNAME` | `"alvin"` | Regular user account name. |
| `USER_PASSWORD` | `""` | User password (prompts securely if left empty). |
| `USER_GROUPS` | `"wheel,storage,power"` | Groups assigned to the user. |
| `SERVICES` | `"NetworkManager"` | Systemd services to automatically enable. |

---

## Testing & Verification

Run the automated test suite locally:
```bash
./tests/test_bash_installer.sh
```
Verifies shell syntax (`bash -n`), `vars.conf` evaluation, and `pkglist.txt` comment/package filtering.

