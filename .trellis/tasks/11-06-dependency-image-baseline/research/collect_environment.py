"""记录隔离解释器、工具包与运行包，不读取应用配置。"""

import importlib.metadata
import json
import os
import platform

print(json.dumps({
    "python": platform.python_version(),
    "machine": platform.machine(),
    "libc": platform.libc_ver(),
    "os_release": platform.freedesktop_os_release(),
    "resolver_environment": {k: v for k, v in os.environ.items() if k.startswith(("UV_", "PIP_"))},
    "packages": sorted([
        {"name": d.metadata["Name"], "version": d.version}
        for d in importlib.metadata.distributions()
    ], key=lambda d: d["name"].lower()),
}, ensure_ascii=False, indent=2))
