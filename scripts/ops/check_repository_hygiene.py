#!/usr/bin/env python3
"""只读检查真实暂存 blob 或显式工作树文本，不输出命中原文。"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys


# 仅豁免已审查部署行；修改行内容会使指纹失效，不能借同一文件加入新地址。
PRIVATE_IP_EXCEPTIONS = {
    ".trellis/tasks/11-06-list-loading-performance/production-switch-plan.md": {
        "83c67f31bb61243f8c1f8cd7a19f6f79c66f153dd2b24707705d2cb4ea4ace43": "生产切换计划记录现有监听与代理协议边界",
    },
    "deploy/nginx/md2word-api.962850.xyz.conf": {
        "208f2a75d49eaf08feb7916992b2ad0490c230d2f4f42b0a0a6e86f3d818af89": "现有 HTTP 私网监听配置",
        "fee23d5e892786ac10fe3b0d6b1550cde442590c68cb3adea8df237e728da957": "现有 HTTPS 私网监听配置",
    },
    "docs/deploy/hostdzire-dmit-md2word.md": {
        "eca0f321b59874f7c279ab212cafc86461ac55bc61ea6039ff79965bad950e90": "现有 WireGuard 两端地址说明",
        "0226d62b12652bd248ec26dcb58043330b17377076f08ee8e7b1b986d1f1c4c2": "现有跨主机 HTTP 与 HTTPS 转发说明",
    },
}

HOME_PATH = re.compile(
    r"(?<![\w])(?:[A-Za-z]:)?/(?:Users|home)/([^/\s\"'`<>]+)", re.IGNORECASE
)
PLACEHOLDER = re.compile(r"(?:\$\{[A-Za-z_][A-Za-z_0-9]*\}|\$[A-Za-z_][A-Za-z_0-9]*\$?)")
IP_CANDIDATE = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])")
MESSAGES = {
    "temporary-file": "请移除待提交的临时文件。",
    "user-home-path": "请使用项目相对路径、环境变量或明确占位符。",
    "private-ip": "请移除私网地址，或提交精确部署例外供审查。",
}


class ScanError(Exception):
    """只携带安全描述，避免底层错误中的路径或内容进入输出。"""


def git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    except OSError as error:
        raise ScanError("git-read-failed：无法启动 Git，请检查安装。") from error
    if result.returncode:
        raise ScanError(f"git-read-failed：Git {args[0]} 读取失败，退出码 {result.returncode}。")
    return result.stdout


def findings(path: str, data: bytes) -> tuple[list[tuple[int, str]], bool]:
    """返回定位与规则；二进制或非 UTF-8 内容只检查文件名并明确报告跳过。"""
    result = [(1, "temporary-file")] if path.lower().endswith(".tmp") else []
    if b"\0" in data:
        return result, False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return result, False
    for number, line in enumerate(text.splitlines(), 1):
        # 只归一化路径分隔符；不执行文本转义或把任意内容当成 Python/JSON 代码。
        normalized = re.sub(r"\\+", "/", line.replace(r"\/", "/"))
        if any(
            not PLACEHOLDER.fullmatch(match[1]) for match in HOME_PATH.finditer(normalized)
        ):
            result.append((number, "user-home-path"))
        for candidate in IP_CANDIDATE.finditer(line):
            try:
                address = ipaddress.IPv4Address(candidate[0])
            except ipaddress.AddressValueError:
                continue
            first, second, _, _ = address.packed
            private = first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
            if private:
                fingerprint = hashlib.sha256(line.encode("utf-8")).hexdigest()
                if fingerprint not in PRIVATE_IP_EXCEPTIONS.get(path, {}):
                    result.append((number, "private-ip"))
                break
    return result, True


def index_entries(root: Path) -> dict[str, tuple[str, str]]:
    entries = {}
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise ScanError("git-index-unmerged：暂存区存在未解决冲突，请先解决冲突。")
        entries[os.fsdecode(raw_path)] = (mode, oid)
    return entries


def scan(args: argparse.Namespace) -> int:
    root = Path(os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")).removesuffix("\n"))
    entries = index_entries(root)
    if args.staged:
        # 禁用重命名折叠后，目的路径作为新增读取；删除路径不再进入待检集合。
        paths = [os.fsdecode(path) for path in git(
            root, "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "--no-renames", "-z", "--"
        ).split(b"\0") if path]
    elif args.tracked:
        paths = list(entries)
    else:
        paths = []
        for name in args.files:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ScanError("invalid-input-path：--files 只接受仓库根目录下的相对文件路径。")
            paths.append(path.as_posix())
    failed = False
    skipped = 0
    for path in dict.fromkeys(paths):
        location = json.dumps(path, ensure_ascii=False)
        if path in entries and entries[path][0] == "160000":
            print(f"{location}:1: unsupported-submodule：未扫描子模块内部内容。")
            skipped += 1
            continue
        if args.staged:
            data = git(root, "cat-file", "blob", entries[path][1])
        else:
            try:
                file = root / path
                data = os.fsencode(os.readlink(file)) if file.is_symlink() else file.read_bytes()
            except OSError as error:
                print(f"{location}:1: worktree-read-failed：工作树文件缺失或无法读取。")
                failed = True
                continue
        hits, is_text = findings(path, data)
        for line, rule in hits:
            print(f"{location}:{line}: {rule}：{MESSAGES[rule]}")
            failed = True
        if not is_text:
            print(f"{location}:1: binary-or-non-utf8：未扫描内容，仅检查文件名。")
            skipped += 1
    print(f"仓库卫生检查完成：文件 {len(set(paths))}，内容跳过 {skipped}，{'发现违规' if failed else '未发现规则命中'}。")
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--staged", action="store_true", help="检查本次改动的完整 index blob")
    modes.add_argument("--tracked", action="store_true", help="检查当前跟踪工作树文件")
    modes.add_argument("--files", nargs="+", metavar="PATH", help="检查显式指定的新增候选文件；路径相对仓库根目录")
    args = parser.parse_args()
    try:
        return scan(args)
    except ScanError as error:
        print(f"仓库卫生检查失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
