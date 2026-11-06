"""在禁网候选容器内核对依赖、基础镜像预装包及运行保护。"""

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import zipfile


normalize = lambda name: re.sub(r"[-_.]+", "-", name).lower()
expected = {}
for line in Path("/inputs/constraints.txt").read_text().splitlines():
    name, version = line.split("==")
    expected[normalize(name)] = version
installed = {
    normalize(d.metadata["Name"]): d.version
    for d in importlib.metadata.distributions()
}
tools = {name: version for name, version in installed.items() if name in {"pip", "setuptools", "wheel"}}
assert {name: version for name, version in installed.items() if name not in tools} == expected
assert platform.python_version() == "3.11.18" and platform.machine() == "x86_64"
assert os.getuid() != 0
checked = subprocess.run(["python", "-m", "pip", "--isolated", "check"], text=True, capture_output=True, check=True)

# 构建日志显示 packaging 已由基础镜像预装，逐文件验证它与已核实 wheel 的内容相同。
wheel = Path("/wheels/packaging-26.3-py3-none-any.whl")
distribution = importlib.metadata.distribution("packaging")
verified = 0
with zipfile.ZipFile(wheel) as archive:
    for item in archive.infolist():
        if item.is_dir() or item.filename.endswith(".dist-info/RECORD"):
            continue
        assert ".data/" not in item.filename
        actual = Path(distribution.locate_file(item.filename)).read_bytes()
        assert hashlib.sha256(actual).digest() == hashlib.sha256(archive.read(item)).digest(), item.filename
        verified += 1

poppler = {}
for executable in ("pdfinfo", "pdftoppm"):
    result = subprocess.run([executable, "-v"], text=True, capture_output=True, check=True)
    poppler[executable] = (result.stdout + result.stderr).splitlines()[0]
print(json.dumps({
    "python": platform.python_version(), "uid": os.getuid(), "runtime_packages": expected,
    "tools": tools, "pip_check": checked.stdout.strip(),
    "preinstalled_packaging_files_verified": verified,
    "poppler": poppler,
    "poppler_package": subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "poppler-utils"], text=True),
}, ensure_ascii=False, indent=2))
