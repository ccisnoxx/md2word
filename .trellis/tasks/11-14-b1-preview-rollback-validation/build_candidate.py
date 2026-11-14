"""从固定提交导出正常和 B1 源码，记录离线验证输入与指纹。"""

from argparse import ArgumentParser
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tarfile


BASE_COMMIT = "4081b49e7b7fe18d41b4428321d4a33c206e6f37"
RECIPE = Path(__file__).resolve()
PATCH = RECIPE.with_name("candidate.patch")
CANDIDATE_FILES = {
    "app/domains/document_jobs/preview.py",
    "app/domains/document_jobs/preview_evidence.py",
    "app/services/renderer/block_anchors.py",
    "app/services/renderer/render_evidence.py",
}


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tree_manifest(root: Path) -> dict[str, dict[str, str | bool]]:
    return {
        path.relative_to(root).as_posix(): {
            "sha256": sha256(path.read_bytes()),
            "executable": bool(path.stat().st_mode & 0o111),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build(output: Path) -> dict:
    """将补丁仅应用于新建的候选目录；整个构建不读取工作区业务文件。"""
    repository = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=RECIPE.parent, text=True,
    ).strip()).resolve()
    output = output.resolve()
    if output.is_relative_to(repository):
        raise ValueError("候选输出须使用工作区之外的新目录。")
    output.mkdir()
    normal, candidate = output / "normal", output / "b1"
    normal.mkdir()
    with subprocess.Popen(
        ["git", "archive", "--format=tar", BASE_COMMIT], cwd=repository, stdout=subprocess.PIPE,
    ) as archive:
        with tarfile.open(fileobj=archive.stdout, mode="r|") as source:
            source.extractall(normal, filter="data")
        if archive.wait() != 0:
            raise RuntimeError("固定基线源码导出失败。")
    shutil.copytree(normal, candidate)
    patch = PATCH.read_bytes()
    subprocess.run(
        ["git", "apply", "--whitespace=error-all", "-"], cwd=candidate, input=patch, check=True,
    )

    normal_files = tree_manifest(normal)
    candidate_files = tree_manifest(candidate)
    changed = {name for name in normal_files.keys() | candidate_files.keys()
               if normal_files.get(name) != candidate_files.get(name)}
    if changed != CANDIDATE_FILES:
        raise RuntimeError(f"候选源码差异与预期不符：{sorted(changed)}")
    inputs = {
        name: info["sha256"] for name, info in normal_files.items()
        if name == "requirements.txt" or name.startswith("requirements/")
    }
    runtime = {
        "python": sys.version,
        "system": platform.system(),
        "machine": platform.machine(),
        "sqlite": sqlite3.sqlite_version,
        "distributions": {item.metadata["Name"]: item.version for item in metadata.distributions()},
    }
    fingerprints = {
        "base_commit": BASE_COMMIT,
        "patch_sha256": sha256(patch),
        "recipe_sha256": sha256(RECIPE.read_bytes()),
        "inputs_sha256": inputs,
        "runtime": runtime,
        "normal_tree_sha256": sha256(canonical_json(normal_files)),
        "candidate_tree_sha256": sha256(canonical_json(candidate_files)),
        "normal_app_sha256": {name: info["sha256"] for name, info in normal_files.items() if name.startswith("app/")},
        "candidate_app_sha256": {name: info["sha256"] for name, info in candidate_files.items() if name.startswith("app/")},
        "candidate_changed_files": sorted(changed),
    }
    (output / "fingerprints.json").write_text(
        json.dumps(fingerprints, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return fingerprints


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="工作区外尚未创建的输出目录")
    args = parser.parse_args()
    report = build(args.output)
    print(json.dumps({key: report[key] for key in (
        "base_commit", "patch_sha256", "normal_tree_sha256", "candidate_tree_sha256",
    )}, ensure_ascii=False))
