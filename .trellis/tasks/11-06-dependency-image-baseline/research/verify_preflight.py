"""只读复核 B02 来源门槛，证据仅写入本任务目录。"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


REMOTE_PROBE = r'''
import hashlib, json, pathlib, shutil, subprocess

def protected():
    ids = subprocess.check_output(["docker", "ps", "-aq", "--filter", "name=md2word-p0-"], text=True).split()
    records = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
    return sorted([{"name": c["Name"], "id": c["Id"], "image": c["Image"], "status": c["State"]["Status"], "started_at": c["State"]["StartedAt"]} for c in records], key=lambda c: c["name"])

before = protected()
info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], text=True))
code = """import hashlib,json,pathlib,importlib.metadata
p=pathlib.Path('/opt/pub2-wheels')
print(json.dumps({'exists':p.exists(),'files':[{'name':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size} for f in sorted(p.glob('*.whl'))], 'nested_wheels':[str(f.relative_to(p)) for f in sorted(p.rglob('*.whl')) if f.parent != p], 'installed_pillow':importlib.metadata.version('pillow')}))"""
wheels = json.loads(subprocess.check_output(["docker", "exec", "-e", "PYTHONDONTWRITEBYTECODE=1", "md2word-p0-api-1", "python", "-B", "-c", code], text=True))
print(json.dumps({"disk": dict(zip(["total", "used", "free"], shutil.disk_usage("/"))), "daemon": {"version": info["ServerVersion"], "mirrors": info.get("RegistryConfig", {}).get("Mirrors"), "http_proxy_set": bool(info.get("HttpProxy")), "https_proxy_set": bool(info.get("HttpsProxy")), "no_proxy_set": bool(info.get("NoProxy"))}, "protected_before": before, "protected_after": protected(), "wheelhouse": wheels, "b02_containers": subprocess.check_output(["docker", "ps", "-a", "--filter", "name=md2word-b02-", "--format", "{{.Names}}"], text=True).splitlines(), "b02_images": subprocess.check_output(["docker", "image", "ls", "--filter", "reference=md2word-b02-*", "--format", "{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}"], text=True).splitlines()}))
'''


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    evidence_dir = Path(__file__).resolve().parent
    provenance = json.loads((evidence_dir / "pypi-provenance.json").read_text())
    comparison = json.loads((evidence_dir / "dependency-comparison.json").read_text())
    result = subprocess.run(
        ["ssh", "hostdzire", "python3 -"], input=REMOTE_PROBE,
        text=True, capture_output=True, check=True,
    )
    observed = json.loads(result.stdout)
    official = {f["file"]: f["official_sha256"] for f in provenance["files"]}
    current = {f["name"]: f["sha256"] for f in observed["wheelhouse"]["files"]}
    candidates = {normalize(p["name"]): p["version"] for p in comparison["closure"]}
    candidates.update({"cryptography": "50.0.2", "cffi": "2.1.1", "pycparser": "3.12"})
    wheel_versions = {normalize(name.split("-")[0]): name.split("-")[1] for name in current}
    missing = sorted(set(candidates) - wheel_versions.keys())
    mismatched = sorted(name for name in candidates.keys() & wheel_versions.keys() if candidates[name] != wheel_versions[name])
    hashes_match = current == official and all(f["status"] == "match" and f["observed_sha256"] == f["official_sha256"] for f in provenance["files"])
    stable = observed["protected_before"] == observed["protected_after"]
    report = {
        "target": "hostdzire", "source_container": "md2word-p0-api-1",
        "source_path": "/opt/pub2-wheels", "source_access": "只读，不挂载业务卷",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "requirements_sha256": hashlib.sha256(Path("requirements.txt").read_bytes()).hexdigest(),
        "official_evidence_reused": "pypi-provenance.json；本次未重新查询 PyPI",
        "official_hashes_match": hashes_match,
        "runtime_candidate_count": len(candidates), "wheel_count": len(current),
        "missing_runtime_wheels": [{"name": name, "version": candidates[name]} for name in missing],
        "version_mismatches": mismatched,
        "non_runtime_wheels": sorted(wheel_versions.keys() - candidates.keys()),
        "protected_unchanged": stable, "observed": observed,
        "remote_resources_created": [], "remote_bytes_created": 0,
        "source_gate": "passed" if hashes_match and not missing and not mismatched else "blocked",
    }
    (evidence_dir / "execution-preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("official_hashes_match", "runtime_candidate_count", "wheel_count", "missing_runtime_wheels", "version_mismatches", "non_runtime_wheels", "protected_unchanged", "source_gate")}, ensure_ascii=False))
    return 0 if report["source_gate"] == "passed" and stable else 1


if __name__ == "__main__":
    sys.exit(main())
