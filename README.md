# desktop-assist

Drive a desktop machine programmatically using **PyAutoGUI** and **Pillow**.

## Quickstart

```bash
# create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# install the package in editable mode
pip install -e ".[dev]"

# run the demo
desktop-assist
```

## Project layout

```
desktop_assist/
├── __init__.py    # package metadata
├── actions.py     # mouse & keyboard helpers (click, type, hotkey, …)
├── clipboard.py   # clipboard read/write and copy/paste helpers
├── launcher.py    # launch apps, open files/URLs, check running state
├── screen.py      # screen capture & image-location helpers
├── filesystem.py  # file system helpers (read, write, list, find, wait)
├── notifications.py # system notifications and modal dialogs
├── windows.py     # window discovery, focus, move & resize
└── main.py        # CLI entry point / demo
```

## Key modules

| Module | Purpose |
|--------|---------|
| `actions` | Thin wrappers around PyAutoGUI mouse/keyboard functions with sane defaults (`PAUSE`, `FAILSAFE`). |
| `clipboard` | Read/write the system clipboard and convenience copy/paste helpers. Uses `pbcopy`/`pbpaste` on macOS, `pyperclip` elsewhere. |
| `launcher` | Launch apps by name, open files/URLs in default apps, check if apps are running, and wait for app startup. Uses `open` on macOS, `xdg-open` on Linux. |
| `screen` | Screenshot capture, save-to-disk, and `locate_on_screen` for image-based element detection. |
| `filesystem` | Read, write, append, list, find, and wait for files. Includes `wait_for_file` for downloads and `find_files` for recursive search. Standard library only. |
| `notifications` | System notification banners and blocking modal dialogs (alert, confirm, prompt). Uses `osascript` on macOS, `notify-send`/`zenity` on Linux. |
| `windows` | List, find, focus, move and resize application windows. Uses Quartz + AppleScript on macOS, pygetwindow elsewhere. |
| `main` | Entry point that wires everything together. Run via `desktop-assist` after install. |

## Safety

PyAutoGUI's **fail-safe** is enabled by default — move the mouse to the
top-left corner of the screen to abort any running automation.
