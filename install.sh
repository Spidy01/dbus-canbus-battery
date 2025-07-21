#!/bin/bash
set -euo pipefail

# Define paths
INSTALL_DIR="/data"
REPO_AUTHOR="Spidy01"
REPO_NAME="dbus-canbus-battery"
ZIP_NAME="repo.zip"
TMP_DIR="${INSTALL_DIR}/${REPO_NAME}-main"
FINAL_DIR="${INSTALL_DIR}/${REPO_NAME}"
SYMLINK_PATH="/opt/victronenergy/service/${REPO_NAME}"

# Check dependencies
for cmd in wget unzip; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: Required command '$cmd' is not installed. Please install it and re-run this script."
        exit 1
    fi
done

# Go to install directory
cd "$INSTALL_DIR"

# Clean up any previous attempts
echo "Cleaning up previous installation..."
rm -rf "$TMP_DIR" "$FINAL_DIR" "$ZIP_NAME"

# Download and extract the latest repo ZIP
echo "Downloading ${REPO_NAME}..."
wget "https://github.com/${REPO_AUTHOR}/${REPO_NAME}/archive/refs/heads/main.zip" -O "$ZIP_NAME"

echo "Extracting archive..."
unzip "$ZIP_NAME"
rm -f "$ZIP_NAME"

# Rename and move to final directory
mv "$TMP_DIR" "$FINAL_DIR"
cd "$FINAL_DIR"

# Make main script executable
chmod +x dbus-canbus-battery.py

# Create symlink to Victron service directory
echo "Creating symlink to Victron service directory..."
ln -sf "$FINAL_DIR/service" "$SYMLINK_PATH"

# Attempt to restart the service (optional)
echo "Attempting to restart the service (if supported)..."
if command -v svc &>/dev/null && [ -d "/service/${REPO_NAME}" ]; then
    svc -t "/service/${REPO_NAME}" && echo "Service restarted successfully."
else
    echo "Note: 'svc' command not available or service not found. Skipping restart."
fi

# Done
echo "${REPO_NAME} has been successfully installed and linked."
