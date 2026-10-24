"""从当前候选构造停止新写入的兼容读者源码，供实际交叉恢复验证。"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / ".trellis").is_dir())
DEST = ROOT / "tests/tmp/rnd505-b1-reader"


def build():
    """保留读者，仅在隔离副本停用两个新生成入口；不修改当前候选。"""
    DEST.mkdir(parents=True, exist_ok=True)
    for name in ("app", "tests", "scripts", "resources"):
        shutil.copytree(ROOT / name, DEST / name, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "tmp", ".DS_Store"))
    for path in ROOT.glob("*.py"):
        shutil.copyfile(path, DEST / path.name)
    anchor = DEST / "app/services/renderer/block_anchors.py"
    text = anchor.read_text()
    old = 'BLOCK_ANCHOR_GENERATION_POLICY = "enabled/v1"'
    assert text.count(old) == 1
    anchor.write_text(text.replace(old, 'BLOCK_ANCHOR_GENERATION_POLICY = "disabled/b1"'))
    preview = DEST / "app/domains/document_jobs/preview.py"
    text = preview.read_text()
    start = text.index('            if status == "succeeded":\n                plan, trace, anchors = _mapping_source')
    end = text.index('            # manifest 或 CAS 持久化失败', start)
    preview.write_text(text[:start] + text[end:])
    fingerprints = {str(path.relative_to(DEST)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((DEST / "app").rglob("*.py"))}
    report = {"compat_root": str(DEST), "source_root": str(ROOT),
        "patches": ["block_anchors:disabled/b1", "preview:停止page_mapping写入，保留reader/helper"],
        "app_sha256": fingerprints}
    output = Path(__file__).with_name("b1-source-fingerprints.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(DEST)


if __name__ == "__main__":
    build()
