# Simple Stitch

A one-click desktop app for stitching microscopy tile images using [ashlar](https://github.com/labsyspharm/ashlar). No programming required.

## Download & Install

### macOS

1. Download `SimpleStitch.zip` from the latest release
2. Unzip it — you'll get `Simple Stitch.app` and `install-mac.sh`
3. Open Terminal, `cd` into the unzipped folder, and run:

```bash
bash install-mac.sh
```

4. Open **Simple Stitch** from Applications

> The install script copies the app to `/Applications` and removes the macOS quarantine flag so it opens without warnings.

### Windows

1. Download `acrocyte_simple-stitch-app-X.X.X-setup.exe` from the latest release
2. Run the installer and follow the prompts

## How to Use

1. Open **Simple Stitch**
2. Click **Select Folder** and pick the folder containing your TIFF tile images
3. Click **Start Stitching** — progress will stream in the log panel
4. When done, the stitched OME-TIFF will be saved in the same folder as your tiles
5. To stop a running stitch, click **Cancel**

## Troubleshooting

| Problem | Solution |
|---------|----------|
| macOS: "App is damaged" or blocked | Re-run `bash install-mac.sh` or run `xattr -cr /Applications/Simple\ Stitch.app` in Terminal |
| Windows SmartScreen warning | Click **More info** then **Run anyway** |
| Stitching fails immediately | Make sure your folder contains valid TIFF tile images |
| App won't open on macOS | Make sure you installed via the script, not by dragging from a DMG |

## For Developers

<details>
<summary>Building from source</summary>

### Prerequisites

- Node.js 20+
- Python 3.11+ with [uv](https://docs.astral.sh/uv/)

### Setup

```bash
npm install
uv sync
```

### Development

```bash
npm run dev
```

### Build

```bash
# macOS
npm run build:mac

# Windows
npm run build:win
```

</details>
