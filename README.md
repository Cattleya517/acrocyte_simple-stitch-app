# Simple Stitch

A one-click desktop app for stitching microscopy tile images using [ashlar](https://github.com/labsyspharm/ashlar). No programming required.

## Download & Install

### macOS

1. Go to [**Releases**](../../releases/latest) and download `Simple.Stitch-X.X.X-arm64-mac.zip`
2. Double-click the zip to unzip — you'll get `Simple Stitch.app`
3. Drag `Simple Stitch.app` into your **Applications** folder
4. Open Terminal and run:

```bash
xattr -cr /Applications/Simple\ Stitch.app
```

5. Open **Simple Stitch** from Applications

> Step 4 removes the macOS quarantine flag (needed because the app is not signed with an Apple Developer certificate). You only need to do this once.

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
| macOS: "App is damaged" or blocked | Run `xattr -cr /Applications/Simple\ Stitch.app` in Terminal |
| Windows SmartScreen warning | Click **More info** then **Run anyway** |
| Stitching fails immediately | Make sure your folder contains valid TIFF tile images |
| App won't open on macOS | Make sure you ran the `xattr -cr` command after dragging to Applications |

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
