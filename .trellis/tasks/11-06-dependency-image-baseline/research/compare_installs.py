"""核对两次解析、安装和官方制品身份，成功后写出运行锁。"""

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path):
    text = "\n".join(line for line in path.read_text().splitlines() if not line.strip().startswith("#"))
    records = {}
    for line in text.replace("\\\n", " ").splitlines():
        if not line.strip():
            continue
        requirement, *hashes = line.split()
        name, version = requirement.split("==")
        records[normalize(name)] = {"version": version, "hashes": sorted(hashes)}
    return records


def main():
    evidence = Path(__file__).resolve().parent
    candidates = {}
    for line in (evidence / "constraints.txt").read_text().splitlines():
        name, version = line.split("==")
        candidates[normalize(name)] = version
    official = {f["file"]: f["official_sha256"] for f in json.loads((evidence / "pypi-provenance.json").read_text())["files"]}
    pillow = json.loads((evidence / "wheelhouse-provenance.json").read_text())["pillow"]
    official[pillow["filename"]] = pillow["official_sha256"]
    outputs = {}
    for label in ("A", "B"):
        folder = evidence / label
        lock = read_lock(folder / "runtime-lock.txt")
        assert {name: item["version"] for name, item in lock.items()} == candidates
        before = json.loads((folder / "before.json").read_text())
        after = json.loads((folder / "after.json").read_text())
        assert before["python"] == "3.11.18" and before["machine"] == "x86_64"
        assert before["os_release"]["VERSION_CODENAME"] == "trixie"
        assert before["resolver_environment"] == {}
        tools = {normalize(p["name"]): p["version"] for p in before["packages"]}
        assert set(tools) <= {"pip", "setuptools", "wheel"}
        installed = {normalize(p["name"]): p["version"] for p in after["packages"]}
        assert installed == candidates | tools
        report_file = folder / "install-report.json"
        raw = report_file.read_bytes()
        report = json.loads(raw)
        actual = {}
        compact = []
        for item in report["install"]:
            name = normalize(item["metadata"]["name"])
            version = item["metadata"]["version"]
            url = urlparse(item["download_info"]["url"])
            assert url.scheme == "file" and url.path.startswith("/wheels/")
            filename = Path(unquote(url.path)).name
            sha256 = item["download_info"]["archive_info"]["hashes"]["sha256"]
            assert sha256 == official[filename]
            assert lock[name] == {"version": version, "hashes": ["--hash=sha256:" + sha256]}
            actual[name] = version
            compact.append({"name": name, "version": version, "filename": filename, "sha256": sha256, "url": item["download_info"]["url"]})
        assert actual == candidates
        # 原始报告保留在远端；仓库只保存验收字段，避免复制上游介绍及个人联系信息。
        compact_report = {"raw_report_sha256": hashlib.sha256(raw).hexdigest(), "pip_version": report["pip_version"], "install": compact}
        (folder / "install-evidence.json").write_text(json.dumps(compact_report, ensure_ascii=False, indent=2) + "\n")
        report_file.unlink()
        outputs[label] = {"lock": lock, "installed": installed, "tools": tools, "pip_version": report["pip_version"]}
    assert outputs["A"] == outputs["B"]
    lock_file = Path("requirements/locks/cp311-linux-amd64.txt")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    text = "# 运行依赖锁：CPython 3.11.18 / Debian 13 trixie / linux/amd64。\n# uv 0.11.19 离线解析；来源与重建说明见 docs/deploy/p0-docker-deployment.md。\n# 工具 pip/setuptools/wheel 不属于运行闭包。\n"
    for name, record in sorted(outputs["A"]["lock"].items()):
        text += name + "==" + record["version"] + " \\\n    " + " \\\n    ".join(record["hashes"]) + "\n"
    lock_file.write_text(text)
    result = {"runtime_count": len(candidates), "normalized_locks_equal": True, "installed_sets_equal": True, "source_hashes_match": True, "tools": outputs["A"]["tools"], "pip_version": outputs["A"]["pip_version"], "lock_sha256": hashlib.sha256(lock_file.read_bytes()).hexdigest(), "requirements_sha256": hashlib.sha256(Path("requirements.txt").read_bytes()).hexdigest()}
    (evidence / "comparison-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
