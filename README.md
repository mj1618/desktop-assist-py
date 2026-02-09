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
├── screen.py      # screen capture & image-location helpers
└── main.py        # CLI entry point / demo
```

## Key modules

| Module | Purpose |
|--------|---------|
| `actions` | Thin wrappers around PyAutoGUI mouse/keyboard functions with sane defaults (`PAUSE`, `FAILSAFE`). |
| `screen` | Screenshot capture, save-to-disk, and `locate_on_screen` for image-based element detection. |
| `main` | Entry point that wires everything together. Run via `desktop-assist` after install. |

## Safety

PyAutoGUI's **fail-safe** is enabled by default — move the mouse to the
top-left corner of the screen to abort any running automation.
