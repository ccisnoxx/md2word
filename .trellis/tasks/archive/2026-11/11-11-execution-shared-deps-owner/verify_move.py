"""核对共用依赖收归宿主后，三个执行协作者与宿主是否保持方法体等价、依赖归属是否符合约定。

一次性验收脚本，只读：用 git 取基线的四个模块，与工作区做 AST 比较，并做全仓检索与运行时归属检查。用法：

    python verify_move.py [--base <提交>]
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
PACKAGE = "app/domains/document_jobs"
HOST_PATH = f"{PACKAGE}/execution.py"
HOST_CLASS = "DocumentJobExecutionService"

SHARED = frozenset({
    "settings", "job_repository", "file_repository", "file_service", "document_ir_service",
    "job_resource_snapshot_service",
})
# 文件名 -> (类名, 宿主属性名, 宿主方法白名单, 专属依赖)
COLLABORATORS = {
    "translation_execution.py": (
        "TranslationBatchExecution", "translation_batches",
        frozenset({"_record_event", "_mark_failed", "_fail_stage_attempt", "_mark_timed_out_if_needed",
                   "execute_job", "_get_uploaded_file", "_document_ir_layout_metadata"}),
        frozenset({"translation_batch_repository", "document_ir_translation_service", "translation_audit_service",
                   "term_version_service", "translation_batch_task_queue"}),
    ),
    "render_execution.py": (
        "WordRenderExecution", "rendering",
        frozenset({"_record_event", "_mark_failed", "_mark_succeeded", "_mark_timed_out_if_needed",
                   "_get_uploaded_file", "_document_ir_layout_metadata"}),
        frozenset({"template_read_service", "word_renderer", "word_preview_service"}),
    ),
    "mineru_execution.py": (
        "MinerUExecution", "mineru",
        frozenset({"_record_event", "_mark_failed", "_fail_stage_attempt", "_mark_timed_out_if_needed",
                   "_get_uploaded_file"}),
        frozenset({"callback_message_store", "mineru_config_resolver", "mineru_client_factory"}),
    ),
}
EXCLUSIVE_ALL = frozenset().union(*(spec[3] for spec in COLLABORATORS.values()))

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}


class _UnhopShared(ast.NodeTransformer):
    """把 self._host.<共用依赖> 归一为 self.<共用依赖>，抵消本任务引入的一跳；宿主方法调用不动。"""

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        inner = node.value
        if (node.attr in SHARED and isinstance(inner, ast.Attribute) and inner.attr == "_host"
                and isinstance(inner.value, ast.Name) and inner.value.id == "self"):
            return ast.Attribute(value=inner.value, attr=node.attr, ctx=node.ctx)
        return node


def dump(node: ast.AST, *, unhop: bool = False) -> str:
    node = ast.parse(ast.unparse(node))
    if unhop:
        node = _UnhopShared().visit(node)
    return ast.dump(node)


def self_attrs(node: ast.AST) -> set[str]:
    return {a.attr for a in ast.walk(node)
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == "self"}


def host_attrs(node: ast.AST) -> set[str]:
    return {a.attr for a in ast.walk(node)
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Attribute) and a.value.attr == "_host"
            and isinstance(a.value.value, ast.Name) and a.value.value.id == "self"}


def init_assigned(method: ast.FunctionDef) -> set[str]:
    names = set()
    for item in ast.walk(method):
        targets = item.targets if isinstance(item, ast.Assign) else [item.target] if isinstance(item, ast.AnnAssign) else []
        names.update(t.attr for t in targets
                     if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self")
    return names


def git_show(base: str, path: str) -> ast.Module:
    return ast.parse(subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT, check=True,
                                    capture_output=True, text=True).stdout)


def check_collaborators(base: str) -> None:
    for filename, (cls_name, _, whitelist, exclusive) in COLLABORATORS.items():
        path = f"{PACKAGE}/{filename}"
        base_cls = classes(git_show(base, path))[cls_name]
        cur_cls = classes(ast.parse((ROOT / path).read_text(encoding="utf-8")))[cls_name]
        base_methods, cur_methods = methods(base_cls), methods(cur_cls)
        if set(base_methods) != set(cur_methods):
            fail(f"{cls_name}: 方法集合变化 {sorted(set(base_methods) ^ set(cur_methods))}")
        for name in sorted(set(base_methods) & set(cur_methods) - {"__init__"}):
            if dump(cur_methods[name], unhop=True) != dump(base_methods[name]):
                fail(f"{cls_name}: 方法体与基线不等价 {name}")
        assigned = init_assigned(cur_methods["__init__"])
        if assigned & SHARED:
            fail(f"{cls_name}: __init__ 仍保存共用依赖 {sorted(assigned & SHARED)}")
        if not exclusive <= assigned:
            fail(f"{cls_name}: __init__ 缺少专属依赖 {sorted(exclusive - assigned)}")
        leaked = self_attrs(cur_cls) & SHARED
        if leaked:
            fail(f"{cls_name}: 仍经 self 访问共用依赖 {sorted(leaked)}")
        unknown = self_attrs(cur_cls) - set(cur_methods) - assigned
        if unknown:
            fail(f"{cls_name}: 访问了自身不存在的成员 {sorted(unknown)}")
        outside = host_attrs(cur_cls) - whitelist - SHARED
        if outside:
            fail(f"{cls_name}: 越界访问宿主 {sorted(outside)}")


def check_host(base: str) -> None:
    base_cls = classes(git_show(base, HOST_PATH))[HOST_CLASS]
    cur_cls = classes(ast.parse((ROOT / HOST_PATH).read_text(encoding="utf-8")))[HOST_CLASS]
    base_methods, cur_methods = methods(base_cls), methods(cur_cls)
    if set(base_methods) != set(cur_methods):
        fail(f"宿主方法集合变化 {sorted(set(base_methods) ^ set(cur_methods))}")
    for name in sorted(set(base_methods) & set(cur_methods) - {"__init__"}):
        if dump(cur_methods[name]) != dump(base_methods[name]):
            fail(f"宿主方法体与基线不等价 {name}")
    assigned = init_assigned(cur_methods["__init__"])
    if not SHARED <= assigned:
        fail(f"宿主 __init__ 缺少共用依赖 {sorted(SHARED - assigned)}")
    if assigned & EXCLUSIVE_ALL:
        fail(f"宿主 __init__ 持有专属依赖 {sorted(assigned & EXCLUSIVE_ALL)}")


def check_repository() -> None:
    """经协作者访问共用依赖、以及对执行服务赋值专属依赖名，都应为 0。"""

    hops = "|".join(spec[1] for spec in COLLABORATORS.values())
    via_collaborator = re.compile(r"\.(?:" + hops + r")\.(" + "|".join(sorted(SHARED)) + r")\b")
    receiver = r"(?<![\w\.])(?:(?:new_|old_)?execution|[\w\.]*document_job_execution_service|[\w\.]*execution_service|self\.execution)"
    exclusive_write = re.compile(receiver + r"\.(" + "|".join(sorted(EXCLUSIVE_ALL)) + r")\s*=(?!=)")
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "*.py"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    for name in files:
        if name.startswith(".trellis/"):
            continue
        path = ROOT / name
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if via_collaborator.search(line):
                fail(f"经协作者访问共用依赖 {name}:{lineno}")
            if exclusive_write.search(line):
                fail(f"对执行服务赋值专属依赖 {name}:{lineno}")


def check_runtime() -> None:
    """构造宿主后，协作者的 _host 必须是宿主实例，且协作者上访问任一共用依赖都必须抛 AttributeError：
    残留的 self.<依赖> 会显式失败，而不是读到旧对象。方法体是否经 _host 读取由 AST 比较负责。"""

    sys.path.insert(0, str(ROOT))
    from app.domains.document_jobs.execution import DocumentJobExecutionService

    args = [object() for _ in range(11)]
    host = DocumentJobExecutionService(*args, word_preview_service=object())
    for filename, (_, attr, _, _) in COLLABORATORS.items():
        collaborator = getattr(host, attr)
        if collaborator._host is not host:
            fail(f"{attr}: _host 不是宿主实例")
        for dep in sorted(SHARED):
            if hasattr(collaborator, dep):
                fail(f"{attr}: 协作者上仍可访问共用依赖 {dep}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="6101ad44")
    args = parser.parse_args()
    check_collaborators(args.base)
    check_host(args.base)
    check_repository()
    check_runtime()
    if errors:
        print("核对未通过：")
        for message in errors:
            print(f"  - {message}")
        return 1
    print("核对通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
