from __future__ import annotations

import sys
from pathlib import Path


VENDOR_DIR = Path(__file__).resolve().parent / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
