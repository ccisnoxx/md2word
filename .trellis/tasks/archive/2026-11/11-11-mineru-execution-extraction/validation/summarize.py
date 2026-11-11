"""把 unittest -v 日志归一成可逐行比较的清单。

用法：python summarize.py <结果目录>

输出 results.tsv，每行为「用例标识<TAB>状态<TAB>异常行」。失败用例连同异常行一起记录，
这样基线已失败的用例如果换了失败原因（例如搬移后变成 AttributeError），比较时能看出来。
"""

from __future__ import annotations

import pathlib
import re
import sys

SEPARATOR = "=" * 70
START = re.compile(r"^(test\w*) \(([\w\.]+)\)(?: \.\.\. ?.*)?$")
HEADER = re.compile(r"^(ERROR|FAIL): \w+ \(([\w\.]+)\)(?: (\(.*\)))?$")
# 每次运行都会变化的标识与临时路径，归一后才能跨运行比较。
VOLATILE = (
    (re.compile(r"\b([a-z]+)_[0-9a-f]{8,}\b"), r"\1_<id>"),
    (re.compile(r"/(?:private/)?(?:var/folders|tmp)/[^\s'\"]+"), "<tmp>"),
    (re.compile(r"0x[0-9a-f]+"), "<addr>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\.\d]*(?:\+\d{2}:\d{2}|Z)?"), "<time>"),
    (re.compile(r"datetime\.datetime\([^)]*\)"), "<datetime>"),
)


def normalize(text: str) -> str:
    for pattern, replacement in VOLATILE:
        text = pattern.sub(replacement, text)
    return text.strip()


def exception_line(block: list[str]) -> str:
    """取最后一个调用帧之后第一条顶格行，即最终异常的类型与消息首行。"""

    last_frame = max((index for index, line in enumerate(block) if line.startswith("  File ")), default=-1)
    for line in block[last_frame + 1:]:
        if line and not line[0].isspace() and not line.startswith("-" * 20):
            return normalize(line)
    return ""


def summarize(log: pathlib.Path) -> tuple[list[str], int | None, int]:
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    case_ids: list[str] = []
    skipped: dict[str, str] = {}
    current: str | None = None
    for line in lines:
        if line == SEPARATOR or line.startswith("Ran "):
            break
        match = START.match(line)
        if match:
            current = match.group(2)
            case_ids.append(current)
        # 带 docstring 的用例，状态落在标识行之后的某一行。
        if current is not None and (skip := re.search(r"\.\.\. (skipped .*)$", line)):
            skipped[current] = normalize(skip.group(1))
    ran = next((int(m.group(1)) for line in lines if (m := re.match(r"^Ran (\d+) tests?", line))), None)

    failures: dict[str, list[tuple[str, str]]] = {}
    index = 0
    while index < len(lines):
        if lines[index] == SEPARATOR and index + 1 < len(lines) and (match := HEADER.match(lines[index + 1])):
            end = index + 2
            while end < len(lines) and lines[end] != SEPARATOR and not lines[end].startswith("Ran "):
                end += 1
            key = match.group(2) + (f" {normalize(match.group(3))}" if match.group(3) else "")
            failures.setdefault(match.group(2), []).append((key, f"{match.group(1)}\t{exception_line(lines[index + 2:end])}"))
            index = end
        else:
            index += 1

    rows: list[str] = []
    for case_id in sorted(set(case_ids)):
        if case_id in failures:
            rows.extend(f"{key}\t{detail}" for key, detail in failures[case_id])
        elif case_id in skipped:
            rows.append(f"{case_id}\t{skipped[case_id]}\t")
        else:
            rows.append(f"{case_id}\tok\t")
    return rows, ran, len(set(case_ids))


def main() -> int:
    out = pathlib.Path(sys.argv[1])
    rows: list[str] = []
    mismatched = False
    for log in sorted(out.glob("tests.*.log")):
        module_rows, ran, seen = summarize(log)
        if ran != seen:
            mismatched = True
            print(f"用例条数不一致 {log.name}: Ran {ran}，解析到 {seen}")
        rows.extend(module_rows)
    (out / "results.tsv").write_text("\n".join(sorted(rows)) + "\n", encoding="utf-8")
    print(f"{len(rows)} 行结果已写入 {out / 'results.tsv'}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
