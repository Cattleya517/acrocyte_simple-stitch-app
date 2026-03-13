I want to build and ship a easy ashlar image stitching program to colleage 
the original ashlar open source code paired with coustom GUI for non-technical background user
They can one button install and use file manager to choose the tiles dir they want to stitch

stitching progress is shown in GUI to reduce stress

the backend logic is already in ./demo_nb.ipynb

don't help me finish this project, guide be step by step
maintain a todo list to help you and me to track the progress



# Ashlar Stitching GUI — Tech Stack


## Project
Cross-platform desktop app for running ashlar TIFF stitching with a GUI.
Must work on both Windows and macOS.

## Frontend / Desktop
- Electron (latest)
- React 18
- TypeScript
- Tailwind CSS
- Vite (as bundler/dev server via electron-vite)

## Python Bridge
- Node.js `child_process.spawn` to call Python
- Python command: `python` on Windows, `python3` on macOS (detect via `process.platform`)
- Python script: `runner.py` — thin wrapper around ashlar Python API
- Stream stdout/stderr back to Electron in real-time via ipcMain/ipcRenderer

## Python Side
- ashlar
- Input: TIFF files (multi-file)
- Output: OME-TIFF

## IPC Pattern
- ipcMain handles: run-ashlar, select-dir
- ipcRenderer sends tile directory path, receives log lines + completion status

## UI Features
- Directory picker (user selects tile folder to stitch)
- Real-time log output panel
- Run / Cancel button

## Packaging
- electron-builder
- Windows target: .exe (NSIS installer)
- macOS target: .dmg

## Path handling
- Always use Node.js `path.join()` — never hardcode separators


# TODO

## Phase 1: Project Setup
- [ ] Initialize Electron + React 18 + TypeScript + Vite project (electron-vite)
- [ ] Set up Tailwind CSS
- [ ] Set up project structure (main process, renderer, preload)

## Phase 2: Python Bridge
- [ ] Create `runner.py` — thin wrapper around ashlar/demo_nb.py Python API
- [ ] Implement `child_process.spawn` in main process to call Python
- [ ] Detect platform: `python` on Windows, `python3` on macOS
- [ ] Stream stdout/stderr back to renderer in real-time

## Phase 3: IPC & UI
- [ ] `run-ashlar` IPC handler (main ↔ renderer)
- [ ] `select-dir` IPC handler (open directory dialog for tile folder)
- [ ] Directory picker — user selects the tile folder to stitch
- [ ] Real-time log output panel
- [ ] Run / Cancel button
- [ ] Stitching progress indicator

## Phase 4: Packaging & Distribution
- [ ] Configure electron-builder
- [ ] macOS target: `.dmg`
- [ ] Windows target: `.exe` (NSIS installer) — build via GitHub Actions
- [ ] Bundle Python + dependencies for one-button install