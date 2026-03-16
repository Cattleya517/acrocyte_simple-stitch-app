#!/bin/bash
# Ad-hoc codesign for macOS builds.
# Signs the bundled Python framework and runner before signing the whole app,
# then re-creates the release zip with the properly signed app.
set -e

APP="dist/mac-arm64/Simple Stitch.app"

echo "Signing binaries..."
codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/_internal/Python.framework/Versions/3.11/Python"
codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/_internal/Python.framework"
codesign --force --sign - "$APP/Contents/Resources/ashlar-runner/ashlar-runner"
codesign --force --deep --sign - "$APP"

echo "Re-creating release zip..."
rm -f "dist/Simple Stitch-1.0.0-arm64-mac.zip"
cd dist/mac-arm64
zip -r -y "../Simple Stitch-1.0.0-arm64-mac.zip" "Simple Stitch.app"
cd ../..

echo "Done. Signed app and zip are ready."
