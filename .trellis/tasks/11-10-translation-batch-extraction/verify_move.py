"""核对翻译批次执行逻辑的搬移与改接线是否保持方法体等价。

一次性验收脚本，只读：用 git 取基线 execution.py，与工作区的 execution.py、
translation_execution.py 做 AST 比较。用法：

    python verify_move.py --stage 1 [--base <提交>]
    python verify_move.py --stage 2 [--base <提交>]
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
HOST_PATH = "app/domains/document_jobs/execution.py"
MOVED_PATH = "app/domains/document_jobs/translation_execution.py"
HOST_CLASS = "DocumentJobExecutionService"

MOVED_METHODS = frozenset("""
_ensure_translation_batches_and_enqueue _get_translation_execution_snapshot
summarize_translation_generation _build_expected_translation_plans execute_translation_batch
_claim_translation_batch _reconcile_translation_batch_atomic_rejection
_fail_translation_batch_storage _mark_translating_started _handle_translation_batch_failure
_should_split_translation_batch _split_translation_batch _finalize_translation_generation
_register_translated_document_ir_and_continue _read_translation_artifact _read_translation_source
_translation_integrity_binding _load_batch_replacements _register_translation_batch_result
_enqueue_runnable_translation_batches _next_runnable_translation_batch
_reset_expired_translation_batch_leases _cancel_translation_batch _provider_call_budget_remaining
_provider_call_budget_remaining_for_batch _translation_batch_error_code
_translation_profile_batch_limits _translation_profile_for_job _page_range_for_item_ids
_translate_document_ir _record_translation_audit_events _recorder_call_log_file_ids
_recorder_debug_archive_file_ids _resolve_term_version_for_job
""".split())
MOVED_MODULE_DEFS = frozenset({"_TranslationBatchStorageError", "_is_metadata_storage_error"})
# 阶段二随协作者迁出的队列注入方法；阶段一仍留在宿主。
QUEUE_SETTER = "set_translation_batch_task_queue"
HOST_WHITELIST = frozenset({
    "_record_event", "_mark_failed", "_fail_stage_attempt", "_mark_timed_out_if_needed",
    "_get_uploaded_file", "_document_ir_layout_metadata", "execute_job",
})
HOST_ENTRIES = frozenset({
    "_ensure_translation_batches_and_enqueue", "_finalize_translation_generation", "_read_translation_source",
})
EXCLUSIVE_ATTRS = frozenset({
    "translation_batch_repository", "document_ir_translation_service", "translation_audit_service",
    "term_version_service", "translation_batch_task_queue",
})

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def top_level_defs(tree: ast.Module) -> dict[str, ast.AST]:
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


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
    if drop_hop is not None:
        node = _DropHop(drop_hop).visit(ast.parse(ast.unparse(node)))
    else:
        node = ast.parse(ast.unparse(node))
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(1, 2), required=True)
    parser.add_argument("--base", default="d45e46e1")
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

    moved_class_name = "TranslationBatchExecutionMixin" if args.stage == 1 else "TranslationBatchExecution"
    if moved_class_name not in moved_defs:
        fail(f"新模块缺少类 {moved_class_name}")
        return report()
    moved_class = moved_defs[moved_class_name]
    moved_methods = class_methods(moved_class)

    # 模块级定义：两个翻译专属定义迁出，其余顶层定义留在宿主模块。
    for name in sorted(MOVED_MODULE_DEFS):
        if name in host_defs:
            fail(f"宿主模块仍定义 {name}")
        if name not in moved_defs:
            fail(f"新模块缺少 {name}")
        elif dump(moved_defs[name]) != dump(baseline_defs[name]):
            fail(f"模块级定义与基线不等价 {name}")
    extra_moved_defs = set(moved_defs) - MOVED_MODULE_DEFS - {moved_class_name}
    if extra_moved_defs:
        fail(f"新模块出现计划外的顶层定义: {sorted(extra_moved_defs)}")
    other_defs = set(baseline_defs) - MOVED_MODULE_DEFS - {HOST_CLASS}
    if set(host_defs) - {HOST_CLASS} != other_defs:
        fail(f"宿主模块顶层定义集合变化: {sorted(set(host_defs) ^ (other_defs | {HOST_CLASS}))}")
    hop = "translation_batches" if args.stage == 2 else None
    for name in sorted(other_defs & set(host_defs)):
        if dump(host_defs[name], drop_hop=hop) != dump(baseline_defs[name]):
            fail(f"宿主模块顶层定义与基线不等价 {name}")

    leftover = MOVED_METHODS & set(host_methods)
    if leftover:
        fail(f"宿主类仍定义迁出方法: {sorted(leftover)}")
    host_bases = [ast.unparse(base) for base in host_class.bases]

    if args.stage == 1:
        if host_bases != ["TranslationBatchExecutionMixin"]:
            fail(f"阶段一宿主基类应为 TranslationBatchExecutionMixin，实际 {host_bases}")
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
    expected_moved = MOVED_METHODS | {"__init__", QUEUE_SETTER}
    if set(moved_methods) != expected_moved:
        fail(f"协作者方法集合不符: {sorted(set(moved_methods) ^ expected_moved)}")
    compare_methods("协作者", moved_methods, baseline_methods, MOVED_METHODS | {QUEUE_SETTER}, drop_hop="_host")

    host_calls = hop_accesses(moved_class, "_host")
    if host_calls - HOST_WHITELIST:
        fail(f"协作者越界访问宿主: {sorted(host_calls - HOST_WHITELIST)}")
    if "__init__" in moved_methods:
        own = set(moved_methods) | init_assigned(moved_methods["__init__"])
        unknown = self_accesses(moved_class) - own
        if unknown:
            fail(f"协作者访问了自身不存在的成员: {sorted(unknown)}")
        if not EXCLUSIVE_ATTRS <= init_assigned(moved_methods["__init__"]):
            fail(f"协作者未持有全部专属依赖: {sorted(EXCLUSIVE_ATTRS - init_assigned(moved_methods['__init__']))}")

    stay = set(baseline_methods) - MOVED_METHODS - {QUEUE_SETTER}
    if set(host_methods) != stay:
        fail(f"宿主方法集合变化: {sorted(set(host_methods) ^ stay)}")
    compare_methods("宿主", host_methods, baseline_methods, stay - {"__init__"}, drop_hop="translation_batches")
    entries = hop_accesses(host_class, "translation_batches")
    if entries - HOST_ENTRIES:
        fail(f"宿主越界访问协作者: {sorted(entries - HOST_ENTRIES)}")
    host_own = set(host_methods) | init_assigned(host_methods["__init__"])
    unknown = self_accesses(host_class) - host_own
    if unknown:
        fail(f"宿主访问了自身不存在的成员: {sorted(unknown)}")
    kept = EXCLUSIVE_ATTRS & init_assigned(host_methods["__init__"])
    if kept:
        fail(f"宿主仍持有翻译专属依赖: {sorted(kept)}")
    if "translation_batches" not in init_assigned(host_methods["__init__"]):
        fail("宿主 __init__ 未构造 translation_batches")
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
