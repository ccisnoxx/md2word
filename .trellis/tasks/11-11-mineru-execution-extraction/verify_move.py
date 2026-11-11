"""核对 MinerU 回调段的搬移与改接线是否保持方法体等价。

一次性验收脚本，只读：用 git 取基线 execution.py，与工作区的 execution.py、
mineru_execution.py 做 AST 比较，并核对测试中按模块路径打的补丁目标。用法：

    python verify_move.py --stage 1 [--base <提交>]
    python verify_move.py --stage 2 [--base <提交>]
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys

# 任务目录归档后层级会变，仓库根目录由 git 定位。
ROOT = pathlib.Path(subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], cwd=pathlib.Path(__file__).resolve().parent,
    check=True, capture_output=True, text=True,
).stdout.strip())
HOST_PATH = "app/domains/document_jobs/execution.py"
MOVED_PATH = "app/domains/document_jobs/mineru_execution.py"
HOST_MODULE = "app.domains.document_jobs.execution"
MOVED_MODULE = "app.domains.document_jobs.mineru_execution"
HOST_CLASS = "DocumentJobExecutionService"
HOP = "mineru"

MOVED_METHODS = frozenset("""
_run_mineru_parse find_job_for_mineru_callback enqueue_mineru_callback_for_job
_process_replayable_callback_messages _process_callback_message _build_callback_message_payload
_build_callback_dedupe_key _sync_callback_ids _record_callback_ignored_event
_download_and_register_mineru_result _refresh_mineru_parse_attempt _select_mineru_result
_mineru_language_for_job _build_callback_seed _build_mineru_client
""".split())
HOST_WHITELIST = frozenset({
    "_record_event", "_mark_failed", "_fail_stage_attempt", "_mark_timed_out_if_needed", "_get_uploaded_file",
})
HOST_ENTRIES = frozenset({"_process_replayable_callback_messages", "_run_mineru_parse"})
# 阶段二后宿主不再持有、由协作者持有的依赖。
EXCLUSIVE_ATTRS = frozenset({"callback_message_store", "mineru_client_factory", "mineru_config_resolver"})
# 测试曾按宿主模块路径打补丁、迁出后宿主不得保留的名字；本任务测试中没有这类补丁。
MOVED_ONLY_PATCHED: frozenset[str] = frozenset()

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def top_level_defs(tree: ast.Module) -> dict[str, ast.AST]:
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def module_names(tree: ast.Module) -> set[str]:
    """模块顶层绑定的全部名字：定义、导入与赋值。"""

    names = set(top_level_defs(tree))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def class_methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}


class _DropHop(ast.NodeTransformer):
    """把 <对象>.<hop>.<名字> 归一为 <对象>.<名字>，用于抵消改接线引入的一跳。"""

    def __init__(self, hop: str) -> None:
        self.hop = hop

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Attribute) and node.value.attr == self.hop:
            return ast.Attribute(value=node.value.value, attr=node.attr, ctx=node.ctx)
        return node


def dump(node: ast.AST, *, drop_hop: str | None = None) -> str:
    node = ast.parse(ast.unparse(node))
    if drop_hop is not None:
        node = _DropHop(drop_hop).visit(node)
    return ast.dump(node)


def self_accesses(node: ast.AST) -> set[str]:
    return {
        item.attr for item in ast.walk(node)
        if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == "self"
    }


def hop_accesses(node: ast.AST, hop: str) -> set[str]:
    """收集 self.<hop>.<名字> 中的名字。"""

    return {
        item.attr for item in ast.walk(node)
        if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Attribute)
        and item.value.attr == hop and isinstance(item.value.value, ast.Name) and item.value.value.id == "self"
    }


def init_assigned(method: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(method):
        targets = item.targets if isinstance(item, ast.Assign) else [item.target] if isinstance(item, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                names.add(target.attr)
    return names


def compare_methods(label: str, current: dict[str, ast.FunctionDef], baseline: dict[str, ast.FunctionDef],
                    names: frozenset[str] | set[str], *, drop_hop: str | None = None) -> None:
    for name in sorted(names):
        if name not in current:
            fail(f"{label}: 缺少方法 {name}")
        elif dump(current[name], drop_hop=drop_hop) != dump(baseline[name]):
            fail(f"{label}: 方法体与基线不等价 {name}")


def check_patch_targets(host_names: set[str], moved_names: set[str]) -> None:
    """测试中按模块路径打的补丁目标必须真实存在；f-string 目标按已知循环值展开。"""

    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "tests/*.py"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    pattern = re.compile(r"(app\.domains\.document_jobs\.(?:execution|mineru_execution))\.(\{\w+\}|\w+)")
    for name in files:
        path = ROOT / name
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            for match in pattern.finditer(line):
                module, target = match.groups()
                if target.startswith("{"):
                    fail(f"无法静态展开的 f-string 补丁目标 {name}:{lineno} {module}.{target}")
                    continue
                targets = [target]
                namespace = host_names if module == HOST_MODULE else moved_names
                for item in targets:
                    if item not in namespace:
                        fail(f"补丁目标不存在 {name}:{lineno} {module}.{item}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(1, 2), required=True)
    parser.add_argument("--base", default="bc4226a8")
    args = parser.parse_args()

    baseline_source = subprocess.run(
        ["git", "show", f"{args.base}:{HOST_PATH}"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    baseline_tree = ast.parse(baseline_source)
    host_tree = ast.parse((ROOT / HOST_PATH).read_text(encoding="utf-8"))
    moved_tree = ast.parse((ROOT / MOVED_PATH).read_text(encoding="utf-8"))

    baseline_defs = top_level_defs(baseline_tree)
    host_defs = top_level_defs(host_tree)
    moved_defs = top_level_defs(moved_tree)
    baseline_methods = class_methods(baseline_defs[HOST_CLASS])
    host_class = host_defs[HOST_CLASS]
    host_methods = class_methods(host_class)

    missing = MOVED_METHODS - set(baseline_methods)
    if missing:
        fail(f"基线中找不到待迁出方法: {sorted(missing)}")

    moved_class_name = "MinerUExecutionMixin" if args.stage == 1 else "MinerUExecution"
    if moved_class_name not in moved_defs:
        fail(f"新模块缺少类 {moved_class_name}")
        return report()
    moved_class = moved_defs[moved_class_name]
    moved_methods = class_methods(moved_class)

    extra_moved_defs = set(moved_defs) - {moved_class_name}
    if extra_moved_defs:
        fail(f"新模块出现计划外的顶层定义: {sorted(extra_moved_defs)}")
    other_defs = set(baseline_defs) - {HOST_CLASS}
    if set(host_defs) - {HOST_CLASS} != other_defs:
        fail(f"宿主模块顶层定义集合变化: {sorted(set(host_defs) ^ (other_defs | {HOST_CLASS}))}")
    hop = HOP if args.stage == 2 else None
    for name in sorted(other_defs & set(host_defs)):
        if dump(host_defs[name], drop_hop=hop) != dump(baseline_defs[name]):
            fail(f"宿主模块顶层定义与基线不等价 {name}")

    host_names = module_names(host_tree)
    kept_imports = MOVED_ONLY_PATCHED & host_names
    if kept_imports:
        fail(f"宿主模块仍绑定应迁出的名字，旧补丁不会显式失败: {sorted(kept_imports)}")
    check_patch_targets(host_names, module_names(moved_tree))

    leftover = MOVED_METHODS & set(host_methods)
    if leftover:
        fail(f"宿主类仍定义迁出方法: {sorted(leftover)}")
    host_bases = [ast.unparse(base) for base in host_class.bases]

    if args.stage == 1:
        if host_bases != ["MinerUExecutionMixin"]:
            fail(f"阶段一宿主基类应为 MinerUExecutionMixin，实际 {host_bases}")
        if set(moved_methods) != MOVED_METHODS:
            fail(f"Mixin 方法集合与迁出集合不一致: {sorted(set(moved_methods) ^ MOVED_METHODS)}")
        compare_methods("Mixin", moved_methods, baseline_methods, MOVED_METHODS)
        stay = set(baseline_methods) - MOVED_METHODS
        if set(host_methods) != stay:
            fail(f"宿主方法集合变化: {sorted(set(host_methods) ^ stay)}")
        compare_methods("宿主", host_methods, baseline_methods, stay)
        return report()

    # 阶段二
    if host_bases:
        fail(f"阶段二宿主不应再有基类，实际 {host_bases}")
    expected_moved = MOVED_METHODS | {"__init__"}
    if set(moved_methods) != expected_moved:
        fail(f"协作者方法集合不符: {sorted(set(moved_methods) ^ expected_moved)}")
    compare_methods("协作者", moved_methods, baseline_methods, MOVED_METHODS, drop_hop="_host")

    host_calls = hop_accesses(moved_class, "_host")
    if host_calls - HOST_WHITELIST:
        fail(f"协作者越界访问宿主: {sorted(host_calls - HOST_WHITELIST)}")
    if "__init__" in moved_methods:
        assigned = init_assigned(moved_methods["__init__"])
        unknown = self_accesses(moved_class) - set(moved_methods) - assigned
        if unknown:
            fail(f"协作者访问了自身不存在的成员: {sorted(unknown)}")
        if not EXCLUSIVE_ATTRS <= assigned:
            fail(f"协作者未持有全部 MinerU 依赖: {sorted(EXCLUSIVE_ATTRS - assigned)}")

    stay = set(baseline_methods) - MOVED_METHODS
    if set(host_methods) != stay:
        fail(f"宿主方法集合变化: {sorted(set(host_methods) ^ stay)}")
    compare_methods("宿主", host_methods, baseline_methods, stay - {"__init__"}, drop_hop=HOP)
    entries = hop_accesses(host_class, HOP)
    if entries - HOST_ENTRIES:
        fail(f"宿主越界访问协作者: {sorted(entries - HOST_ENTRIES)}")
    host_assigned = init_assigned(host_methods["__init__"])
    unknown = self_accesses(host_class) - set(host_methods) - host_assigned
    if unknown:
        fail(f"宿主访问了自身不存在的成员: {sorted(unknown)}")
    kept = EXCLUSIVE_ATTRS & host_assigned
    if kept:
        fail(f"宿主仍持有 MinerU 依赖: {sorted(kept)}")
    if HOP not in host_assigned:
        fail(f"宿主 __init__ 未构造 {HOP}")
    return report()


def report() -> int:
    if errors:
        print("核对未通过：")
        for message in errors:
            print(f"  - {message}")
        return 1
    print("核对通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
