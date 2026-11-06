"""静态检查本次交付范围、证据输入、引用与主机信息脱敏。"""

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml


task = Path(".trellis/tasks/11-06-dependency-image-baseline")
research = task / "research"
tracked = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True).splitlines()
untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True).splitlines()
allowed = {
    "requirements.txt", "requirements/locks/cp311-linux-amd64.txt",
    "docker/dev/Dockerfile", "docker/prod/Dockerfile",
    "docker/dev/docker-compose.yml", "docker/prod/docker-compose.yml",
    "docs/deploy/p0-docker-deployment.md", "docs/runbooks/backend.md",
    ".trellis/spec/backend/quality-guidelines.md",
}
files = sorted(set(tracked + untracked))
assert all(name in allowed or name.startswith(str(task) + "/") for name in files)
connection = dict(line.split(" ", 1) for line in subprocess.check_output(
    ["ssh", "-G", "hostdzire"], text=True, stderr=subprocess.DEVNULL,
).splitlines() if " " in line)
for name in files:
    path = Path(name)
    text = path.read_text()
    assert all(line == line.rstrip() for line in text.splitlines()), name
    assert not re.search(r"/[U]sers/|/[h]ome/|/[r]oot/|BEGIN [A-Z ]*PRIVATE KEY", text), name
    assert connection["hostname"] not in text, name
    assert not re.search(r"\b" + re.escape(connection["user"]) + r"@", text), name
    assert not re.search(r"(?::|Port\s|ssh\s+-p\s)" + re.escape(connection["port"]) + r"\b", text), name
    addresses = set(re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", text))
    # 回环/监听地址是既有运行保护，1.1.1.2 是已锁定 click-plugins 的版本。
    assert addresses <= {"127.0.0.1", "0.0.0.0", "1.1.1.2"}, (name, "出现需人工复核的地址形式")
    if path.suffix == ".json":
        json.loads(text)
    elif path.suffix == ".jsonl":
        for line in text.splitlines():
            assert Path(json.loads(line)["file"]).is_file()
    elif path.suffix == ".py":
        ast.parse(text)
for filename in ("input-hashes.json", "build-inputs.json"):
    for name, expected in json.loads((research / filename).read_text()).items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
for variant in ("dev", "prod"):
    path = f"docker/{variant}/docker-compose.yml"
    before = yaml.safe_load(subprocess.check_output(["git", "show", "HEAD:" + path], text=True))
    after = yaml.safe_load(Path(path).read_text())
    assert after["services"]["api"]["image"] == after["services"]["worker"]["image"]
    for service in before["services"]:
        del before["services"][service]["image"]
        del after["services"][service]["image"]
    assert before == after
subprocess.run(["git", "diff", "--check"], check=True)
result = {"checked_files": len(files), "scope_valid": True, "json_ast_references_valid": True, "input_hashes_unchanged": True, "compose_non_image_fields_unchanged": True, "host_identifiers_absent": True, "whitespace_valid": True}
(research / "artifact-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
