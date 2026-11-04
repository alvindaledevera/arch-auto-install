#!/usr/bin/env bash
# ==============================================================================
# Automated Test Suite for Bash Arch Installer
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Testing syntax of all bash scripts..."
bash -n "$PROJECT_DIR"/install.sh "$PROJECT_DIR"/lib/*.sh
echo "✓ Syntax check passed."

echo "Testing vars.conf sourcing..."
source "$PROJECT_DIR/vars.conf"
[ -n "$HOSTNAME" ] || { echo "Error: HOSTNAME is empty"; exit 1; }
[ -n "$TIMEZONE" ] || { echo "Error: TIMEZONE is empty"; exit 1; }
[ -n "$FS_TYPE" ] || { echo "Error: FS_TYPE is empty"; exit 1; }
echo "✓ vars.conf validated successfully (HOSTNAME=$HOSTNAME, FS_TYPE=$FS_TYPE)."

echo "Testing pkglist.txt parsing..."
packages=()
while read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    packages+=("$line")
done < "$PROJECT_DIR/pkglist.txt"

# Verify active packages are present
echo "${packages[*]}" | grep -q "base" || { echo "Error: 'base' not found in pkglist"; exit 1; }
echo "${packages[*]}" | grep -q "linux" || { echo "Error: 'linux' not found in pkglist"; exit 1; }
echo "${packages[*]}" | grep -q "nano" || { echo "Error: 'nano' not found in pkglist"; exit 1; }

# Verify commented packages are NOT present
if echo "${packages[*]}" | grep -w "vim"; then
    echo "Error: Commented package 'vim' was included!"
    exit 1
fi
echo "✓ pkglist.txt parser validated successfully (${#packages[@]} active packages)."

echo "All tests passed successfully!"

