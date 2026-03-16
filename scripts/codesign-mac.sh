#!/bin/bash
# Ad-hoc codesign for macOS builds.
# Signs the bundled Python framework and runner before signing the whole app.
set -e

APP="dist/mac-arm64/Simple Stitch.app"

codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/_internal/Python.framework/Versions/3.11/Python"
codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/_internal/Python.framework"
codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/ashlar-runner"
codesign --force --deep --sign - "$APP"

echo "Code signing complete."
