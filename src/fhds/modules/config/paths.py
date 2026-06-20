"""Single source of truth for filesystem paths.

All modules read paths from here, never recompute them. The same constants
work whether the app runs from source or from `uv tool install`: ROOT is the
`fhds` package dir, so the bundled assets (icons, lang) resolve next to it.

Writable user data (DATA) lives in a per-user data directory, so it survives
reinstalls and keeps the source tree clean.
"""
from pathlib import Path

# ROOT: package root containing main.py + bundled assets (icons, lang).
ROOT = Path(__file__).resolve().parent.parent.parent

# DATA: writable user data dir (user_preferences.json, crash.log, ...).
#   Per-user data dir: survives reinstalls, keeps the tree clean.
from platformdirs import user_data_dir
DATA = Path(user_data_dir("fhds", appauthor=False))

# Read-only bundled assets.
LANG = ROOT / "lang"
ICON_ICO = ROOT / "data" / "icon.ico"
ICON_PNG = ROOT / "data" / "icon.png"
