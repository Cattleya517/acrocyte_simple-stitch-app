#!/bin/bash
# Simple Stitch — macOS Installer
# Usage: bash install-mac.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Simple Stitch.app"
APP_SRC="$SCRIPT_DIR/$APP_NAME"
APP_DEST="/Applications/$APP_NAME"

if [ ! -d "$APP_SRC" ]; then
    echo "Error: $APP_NAME not found in current directory."
    echo "Make sure install-mac.sh is next to Simple Stitch.app"
    exit 1
fi

echo "Installing Simple Stitch..."

# Remove old version if exists
if [ -d "$APP_DEST" ]; then
    echo "Removing old version..."
    rm -rf "$APP_DEST"
fi

# Copy to Applications
echo "Copying to /Applications..."
cp -R "$APP_SRC" "$APP_DEST"

# Remove quarantine to prevent App Translocation
xattr -cr "$APP_DEST"

echo ""
echo "Done! Simple Stitch has been installed."
echo "You can now open it from Applications or run:"
echo "  open /Applications/Simple\ Stitch.app"
