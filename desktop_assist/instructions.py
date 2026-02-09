"""Custom instructions — find and load user-provided instruction files."""

from __future__ import annotations

from pathlib import Path

_INSTRUCTIONS_FILENAME = ".desktop-assist.md"
_MAX_FILE_SIZE = 10 * 1024  # 10 KB


def find_instructions_file(start_dir: str | Path | None = None) -> Path | None:
    """Walk from *start_dir* (default CWD) up to $HOME looking for .desktop-assist.md.

    Returns the path to the first match, or ``None`` if not found.
    """
    start = Path(start_dir) if start_dir else Path.cwd()
    home = Path.home()

    current = start.resolve()
    home_resolved = home.resolve()

    while True:
        candidate = current / _INSTRUCTIONS_FILENAME
        if candidate.is_file():
            return candidate

        # Stop at home directory (inclusive — we already checked it)
        if current == home_resolved:
            break

        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding home
            break
        current = parent

    return None


def load_instructions_file(path: str | Path) -> str:
    """Read an instructions file, enforcing the 10 KB size limit.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file exceeds the size limit.
    """
    p = Path(path)
    size = p.stat().st_size
    if size > _MAX_FILE_SIZE:
        raise ValueError(
            f"Instructions file is too large ({size:,} bytes, "
            f"max {_MAX_FILE_SIZE:,}): {p}"
        )
    return p.read_text(encoding="utf-8")
