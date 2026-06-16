#!/Users/sc/miniconda3/envs/md2word/bin/python
from __future__ import annotations

# scripts/dev/run_api.py: PyCharm 友好的 FastAPI 本地直跑入口。

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
root_path = str(ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

VENDOR_DIR = ROOT / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

import uvicorn


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
