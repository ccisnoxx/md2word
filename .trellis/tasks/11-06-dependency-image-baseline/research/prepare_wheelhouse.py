"""按已授权清单准备隔离 wheelhouse；任何来源差异均立即失败。"""

import json
from pathlib import Path
import shlex
import subprocess
import sys


REMOTE = r'''
import datetime, hashlib, json, pathlib, shutil, subprocess, sys, urllib.request

base = pathlib.Path(sys.argv[1])
destination = base
suffix = 0
while destination.exists():
    suffix += 1
    destination = base.with_name(base.name + "-" + str(suffix))
free = shutil.disk_usage(base.parent).free
if free < 5 * 1024**3:
    raise RuntimeError("任务可用空间不足 5 GiB，停止")
ids = subprocess.check_output(["docker", "ps", "-aq", "--filter", "name=md2word-p0-"], text=True).split()
containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
protected = sorted([{"name": c["Name"], "id": c["Id"], "image": c["Image"], "status": c["State"]["Status"], "started_at": c["State"]["StartedAt"]} for c in containers], key=lambda c: c["name"])
with urllib.request.urlopen("https://pypi.org/pypi/pillow/12.2.0/json", timeout=30) as response:
    metadata = json.load(response)
filename = "pillow-12.2.0-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
selected = [f for f in metadata["urls"] if f["filename"] == filename]
if len(selected) != 1 or selected[0]["yanked"]:
    raise RuntimeError("官方 Pillow 制品不存在、不唯一或已撤回，停止")
artifact = selected[0]
if artifact["digests"]["sha256"] != "e74473c875d78b8e9d5da2a70f7099549f9eb37ded4e2f6a463e60125bccd176":
    raise RuntimeError("Pillow 官方元数据与预检值不一致，停止")
destination.mkdir()
source = destination / "source-wheels"
source.mkdir()
subprocess.run(["docker", "cp", "md2word-p0-api-1:/opt/pub2-wheels/.", str(source)], check=True, stdout=subprocess.DEVNULL)
observed = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in source.glob("*.whl")}
if observed != EXPECTED:
    raise RuntimeError("现存离线制品与已核实来源清单不一致，停止")
wheelhouse = destination / "wheelhouse"
wheelhouse.mkdir()
for f in source.glob("*.whl"):
    if not f.name.startswith("pip-"):
        shutil.copy2(f, wheelhouse / f.name)
with urllib.request.urlopen(artifact["url"], timeout=60) as response:
    data = response.read()
actual = hashlib.sha256(data).hexdigest()
if actual != artifact["digests"]["sha256"]:
    raise RuntimeError("下载的 Pillow SHA-256 与 PyPI 不一致，停止")
with (wheelhouse / filename).open("xb") as output:
    output.write(data)
record = {"target": "hostdzire", "remote_dir": "${B02_REMOTE_DIR}", "disk_free_before": free, "protected_before": protected, "pillow": {"filename": filename, "source_url": artifact["url"], "metadata_url": "https://pypi.org/pypi/pillow/12.2.0/json", "official_sha256": actual, "download_sha256": actual, "downloaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "size": len(data), "license": metadata["info"].get("license_expression"), "selection": "CPython 3.11 / x86_64 / glibc 2.41；兼容候选中优先选择较高 manylinux 标签"}, "existing_runtime_wheels": 56, "runtime_wheels": 57, "tool_wheels": [name for name in observed if name.startswith("pip-")], "source_hashes_unchanged": True}
(destination / "wheelhouse-provenance.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"actual_remote_dir": str(destination), "record": record}, ensure_ascii=False))
'''


def main():
    evidence = Path(__file__).resolve().parent
    provenance = json.loads((evidence / "pypi-provenance.json").read_text())
    expected = {f["file"]: f["official_sha256"] for f in provenance["files"]}
    script = "EXPECTED = " + repr(expected) + "\n" + REMOTE
    result = subprocess.run(
        ["ssh", "hostdzire", "python3 -B - " + shlex.quote(sys.argv[1])],
        input=script, text=True, capture_output=True, check=True,
    )
    result = json.loads(result.stdout)
    (evidence / "wheelhouse-provenance.json").write_text(json.dumps(result["record"], ensure_ascii=False, indent=2) + "\n")
    print(result["actual_remote_dir"])
    print("Pillow 官方 hash 匹配；运行 wheelhouse 共 57 个文件，工具 pip 单列。")


if __name__ == "__main__":
    main()
