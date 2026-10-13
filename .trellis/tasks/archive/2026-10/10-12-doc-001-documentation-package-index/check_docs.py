"""DOC-001 只读文档检查；从仓库根目录运行，不访问网络。"""

import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = next(parent.parent for parent in Path(__file__).resolve().parents
            if parent.name == ".trellis")
TASK = Path(__file__).resolve().parent
PARENT = ROOT / ".trellis/tasks/10-12-datasheet-docx-delivery-quality"


def prose(text):
    """排除 fenced code 和行内代码，保留行号。"""
    output = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            output.append("")
        else:
            output.append("" if fence else re.sub(r"(`+).*?\1", "", line))
    return "\n".join(output)


def anchors(path):
    text = prose(path.read_text())
    result = set(re.findall(r'(?:id|name)=[\"\']([^\"\']+)[\"\']', text))
    counts = {}
    for heading in re.findall(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        base = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(base, 0)
        counts[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


paths = sorted({ROOT / "README.md", ROOT / "DOCUMENTATION-MANIFEST.md",
                *ROOT.joinpath("docs").rglob("*.md"),
                *ROOT.joinpath("trellis-bootstrap").rglob("*.md"),
                *TASK.rglob("*.md"), *PARENT.rglob("*.md")})
errors = []
links = 0
external = 0
fragments = 0
reference_uses = 0
for path in paths:
    text = prose(path.read_text())
    definitions = dict(re.findall(r"^\s*\[([^\]]+)\]:\s*<?([^\s>]+)>?", text, re.M))
    definitions = {key.casefold(): value for key, value in definitions.items()}
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*\[[^\]]+\]:", line):
            continue
        # 当前文档使用普通 inline links；兼容引用式链接及 HTML href/src。
        targets = [a or b for a, b in re.findall(
            r"!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s()]+(?:\([^()]*\)[^\s()]*)*))"
            r"(?:\s+[\"'][^\n]*?[\"'])?\s*\)", line)]
        targets += re.findall(r'(?:href|src)=[\"\']([^\"\']+)[\"\']', line)
        for label, ref in re.findall(r"!?\[([^\]]+)\]\[([^\]]*)\]", line):
            reference_uses += 1
            key = (ref or label).casefold()
            if key not in definitions:
                errors.append(f"{path.relative_to(ROOT)}:{number}: 未定义引用 {key}")
            else:
                targets.append(definitions[key])
        for target in targets:
            url = urlsplit(html.unescape(target))
            if url.scheme or url.netloc:
                external += 1
                continue
            links += 1
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not destination.exists():
                errors.append(f"{path.relative_to(ROOT)}:{number}: {target} -> 目标不存在")
            elif url.fragment and destination.suffix.lower() == ".md":
                fragments += 1
                if unquote(url.fragment) not in anchors(destination):
                    errors.append(f"{path.relative_to(ROOT)}:{number}: {target} -> 锚点不存在")

manifest_text = ROOT.joinpath("DOCUMENTATION-MANIFEST.md").read_text()
declared = re.findall(r"^\| (?:`([^`]+)`|\[[^\]]+\]\(([^)]+)\)) \|", manifest_text, re.M)
for raw, linked in declared:
    target = raw or linked
    if not (ROOT / target).exists():
        errors.append(f"DOCUMENTATION-MANIFEST.md: 缺少 {target}")

task_manifest = ROOT.joinpath("docs/implementation/codex-task-manifest.yaml").read_text()
ids = re.findall(r"^  - id: (\S+)$", task_manifest, re.M)
prompts = re.findall(r"^    prompt_file: (\S+)$", task_manifest, re.M)
for target in prompts:
    if not (ROOT / target).is_file():
        errors.append(f"codex-task-manifest.yaml: 缺少 {target}")
if len(ids) != len(set(ids)) or len(ids) != len(prompts):
    errors.append("任务 ID 重复或 prompt 数量不一致")
for directory in ("product", "architecture", "contracts", "design", "engineering", "implementation", "decisions"):
    if not list(ROOT.joinpath("docs", directory).glob("*.md")):
        errors.append(f"文档目录缺失或为空：docs/{directory}")
for name in ("prd.md", "design.md", "implement.md", "task-map.md"):
    if not ROOT.joinpath("trellis-bootstrap", name).is_file():
        errors.append(f"bootstrap 文件缺失：{name}")

# Git 不检查未跟踪文件；单独覆盖待纳入的文档包和任务文档。
package_dirs = {"product", "architecture", "contracts", "design", "engineering", "implementation", "decisions"}
whitespace_paths = [p for p in paths if "docs" not in p.relative_to(ROOT).parts
                    or p == ROOT / "docs/README.md"
                    or p.relative_to(ROOT).parts[1] in package_dirs]
for path in [*whitespace_paths, ROOT / "docs/implementation/codex-task-manifest.yaml"]:
    lines = path.read_text().splitlines()
    for number, line in enumerate(lines, 1):
        if line.rstrip() != line:
            errors.append(f"{path.relative_to(ROOT)}:{number}: 行尾空白")
    if lines and not lines[-1].strip():
        errors.append(f"{path.relative_to(ROOT)}: 文件末尾多余空行")

print(f"Markdown 文件={len(paths)}；相对链接={links}；Markdown 锚点={fragments}；引用式链接={reference_uses}；外部链接跳过={external}")
print(f"文档清单条目={len(declared)}；任务={len(ids)}；prompt={len(prompts)}；空白检查文件={len(whitespace_paths) + 1}")
for error in errors:
    print(error)
print(f"{'FAIL' if errors else 'PASS'}：问题总数={len(errors)}")
sys.exit(bool(errors))
