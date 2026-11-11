"""sr-2 代码生成器：把 DocumentJobService 按 plan.py 的归属原样搬入 use_cases 包。

规则：
- 方法体逐字搬移，只改写 `self.<方法>` 引用：同组件保持 `self.<名>`，跨组件改为 `self.<组件属性>.<名>`。
- 共享组件（access/read_model/...）中被跨组件调用的私有方法去掉前导下划线成为公开方法；
  `_get_job` 与 access 中的公开 `get_job` 同名冲突，改名为 `get_authorized_job`。
- 死代码（plan.DEAD）不迁移。
- 模块级常量、数据类等迁入 use_cases/common.py。
- 每个模块的 import 只保留实际用到的名字（按原 import 来源）。
在仓库根目录执行：python .trellis/tasks/11-11-sr-2-job-use-cases/tools/generate.py
"""
import ast
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import plan as P  # noqa: E402

HEADER_PLACEHOLDER = "# @@HEADER@@"
OUT = pathlib.Path("app/domains/document_jobs/use_cases")
SRC = P.service_source()
LINES = SRC.splitlines(keepends=True)

CLASS_NAMES = {
    "access": "DocumentJobAccess",
    "read_model": "DocumentJobReadModel",
    "events": "DocumentJobEventWriter",
    "review_writer": "DocumentReviewWriter",
    "dispatcher": "DocumentJobDispatcher",
    "request_snapshot": "DocumentJobRequestSnapshots",
    "submission": "DocumentJobSubmission",
    "lifecycle_commands": "DocumentJobLifecycleCommands",
    "publication": "DocumentJobPublication",
    "quality_review": "DocumentJobQualityReview",
    "table_references": "DocumentJobTableReferences",
    "translation_qa": "DocumentJobTranslationQa",
    "downloads": "DocumentJobDownloads",
    "queries": "DocumentJobQueries",
}
DOCSTRINGS = {
    "access": "任务读取授权、有效读投影与任务文件归属判断的共享 owner。",
    "read_model": "任务读视图与可用动作（含禁用原因）的共享 owner；列表、详情与命令前置检查共用同一份规则。",
    "events": "document_job 事件写入。",
    "review_writer": "质量评审记录提交；质量评审与翻译 QA 共用。",
    "dispatcher": "新建/重试任务的 Worker 投递与投递失败收口。",
    "request_snapshot": "创建、克隆、重试共用的请求快照、资源快照与模式/模板/术语版本解析。",
    "submission": "用例：创建、克隆、重试任务及重试 Word 预览。",
    "lifecycle_commands": "用例：归档、取消归档、删除预览与删除、取消任务。",
    "publication": "用例：文档发布、发布记录与发布文件下载、新代请求。",
    "quality_review": "用例：质量/评审/预览读取与评审提交、表格证据。",
    "table_references": "用例：表格参考图列表与内容读取。",
    "translation_qa": "用例：翻译 QA 读取与更新。",
    "downloads": "用例：结果文件与任务文件下载授权、下载审计事件。",
    "queries": "用例：任务列表、事件、文件与翻译批次查询。",
}
SHARED_ORDER = ["events", "access", "read_model", "review_writer", "dispatcher", "request_snapshot"]
USE_CASE_ORDER = list(P.PUBLIC_GROUPS)
ALL = SHARED_ORDER + USE_CASE_ORDER


def new_name(method, comp):
    if method == "_get_job":
        return "get_authorized_job"
    if comp in P.SHARED and method.startswith("_"):
        return method[1:]
    return method


COMMON_RENAMES = {"_UNREAD_RESULT": "UNREAD_RESULT", "_SYSTEM_LOGGER": "SYSTEM_LOGGER",
                  "_ReviewCommit": "ReviewCommit", "_TableReferenceSnapshot": "TableReferenceSnapshot",
                  "_DocumentJobSearchable": "DocumentJobSearchable"}


def rename_common(text):
    for old, new in COMMON_RENAMES.items():
        text = re.sub(rf"\b{old}\b", new, text)
    return text


def method_source(func):
    start = (func.decorator_list[0].lineno if func.decorator_list else func.lineno) - 1
    return "".join(LINES[start:func.end_lineno])


def main():
    tree, cls, methods = P.load()
    owner, unresolved, comp_deps, comp_uses, _other, _ = P.plan()
    assert not unresolved, unresolved
    renamed = {m: new_name(m, owner[m]) for m in owner}
    init = next(f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    # 依赖类型沿用原构造函数注解；原本可选的依赖保持 `| None` 注解
    ann = {a.arg: ast.get_source_segment(SRC, a.annotation) for a in init.args.args[1:]}

    # 共享组件中同组件内仍用原私有名的方法，也统一改为新名；确认无重名
    for comp in ALL:
        names = [renamed[m] for m in owner if owner[m] == comp]
        assert len(names) == len(set(names)), (comp, names)

    def rewrite(text, comp):
        def sub(match):
            name = match.group(1)
            if name in owner:
                target = owner[name]
                if target == comp:
                    return f"self.{renamed[name]}"
                return f"self.{target}.{renamed[name]}"
            if name in P.DEAD:
                raise SystemExit(f"{comp} 引用了死代码 {name}")
            return match.group(0)
        return re.sub(r"\bself\.(\w+)\b", sub, text)

    # ---- 模块级定义 -> common.py
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    module_defs = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
                   and not (isinstance(n, ast.ClassDef) and n.name == "DocumentJobService")
                   and not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant))
                   and not (isinstance(n, ast.ClassDef) and n.name == "_DocumentJobSearchable")]
    common_body = ""
    for n in module_defs:
        start = (n.decorator_list[0].lineno if getattr(n, "decorator_list", None) else n.lineno) - 1
        common_body += "".join(LINES[start:n.end_lineno]).rstrip("\n") + "\n\n\n"
    common_body = rename_common(common_body)
    common_names = set()
    for n in module_defs:
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)):
            common_names.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                common_names |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)}
    common_names = {COMMON_RENAMES.get(n, n) for n in common_names}

    # import 来源表：名字 -> (模块, 原名, 别名) ；import x -> ("", x, None)
    origin = {}
    for n in imports:
        if isinstance(n, ast.ImportFrom):
            if n.module == "__future__":
                continue
            for a in n.names:
                origin[a.asname or a.name] = (n.module, a.name, a.asname)
        else:
            for a in n.names:
                origin[(a.asname or a.name).split(".")[0]] = ("", a.name, a.asname)

    origin["DocumentJobSearchable"] = ("app.domains.document_jobs.list_query", "DocumentJobSearchable", None)

    def import_block(body, extra_common=True):
        tree_ = ast.parse(body)
        used = {x.id for x in ast.walk(tree_) if isinstance(x, ast.Name)}
        used |= {x.value.id for x in ast.walk(tree_) if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)}
        plain, froms = [], {}
        for name in sorted(used):
            if name in origin:
                mod, orig, alias = origin[name]
                if mod == "":
                    plain.append(f"import {orig}" + (f" as {alias}" if alias else ""))
                else:
                    froms.setdefault(mod, []).append(orig + (f" as {alias}" if alias else ""))
        if extra_common:
            cn = sorted(n for n in used if n in common_names)
            if cn:
                froms.setdefault("app.domains.document_jobs.use_cases.common", []).extend(cn)
        def render(mod, names):
            names = sorted(set(names))
            line = f"from {mod} import {', '.join(names)}"
            if len(line) <= 110:
                return [line]
            return [f"from {mod} import ("] + [f"    {x}," for x in names] + [")"]

        third_party = {"bs4", "botocore", "fastapi"}
        groups = {"std": [], "third": [], "app": []}
        for line in sorted(set(plain)):
            top = line.split()[1].split(".")[0]
            groups["third" if top in third_party else "std"].append(line)
        for mod in sorted(froms):
            top = mod.split(".")[0]
            key = "app" if top == "app" else "third" if top in third_party else "std"
            groups[key] += render(mod, froms[mod])
        out = ["from __future__ import annotations", "", HEADER_PLACEHOLDER, ""]
        for key in ("std", "third", "app"):
            if groups[key]:
                out += groups[key] + [""]
        return "\n".join(out).rstrip("\n") + "\n"

    OUT.mkdir(exist_ok=True)
    common_text = (import_block(common_body, extra_common=False).replace(
        HEADER_PLACEHOLDER, "# app/domains/document_jobs/use_cases/common.py: 各用例共享的常量、结果数据类与 API 异常。")
        + "\n\n" + common_body.rstrip("\n") + "\n")
    (OUT / "common.py").write_text(common_text)

    # ---- 组件类
    for comp in ALL:
        ms = sorted((m for m in owner if owner[m] == comp), key=lambda m: methods[m].lineno)
        deps = [d for d in P.DEPS if d in comp_deps[comp]]
        uses = [u for u in ALL if u in comp_uses[comp]]
        params = [f"        {d}: {ann[d]}," for d in deps] + [f"        {u}: {CLASS_NAMES[u]}," for u in uses]
        assigns = [f"        self.{x} = {x}" for x in deps + uses]
        body = [f"class {CLASS_NAMES[comp]}:", f'    """{DOCSTRINGS[comp]}"""', ""]
        body += ["    def __init__(", "        self,", "        *,", *params, "    ) -> None:", *assigns, ""]
        for m in ms:
            text = rename_common(rewrite(method_source(methods[m]), comp))
            if renamed[m] != m:
                text = re.sub(rf"\bdef {re.escape(m)}\(", f"def {renamed[m]}(", text, count=1)
            body.append(text.rstrip("\n"))
            body.append("")
        cls_text = "\n".join(body).rstrip("\n") + "\n"
        # 跨组件类型注解需要导入对应类
        for u in uses:
            origin[CLASS_NAMES[u]] = (f"app.domains.document_jobs.use_cases.{u}", CLASS_NAMES[u], None)
        header = import_block(cls_text).replace(
            HEADER_PLACEHOLDER, f"# app/domains/document_jobs/use_cases/{comp}.py: {DOCSTRINGS[comp]}")
        text = header + "\n\n" + cls_text
        (OUT / f"{comp}.py").write_text(text)

    # 汇总给后续步骤使用
    print({c: CLASS_NAMES[c] for c in ALL})
    print("renamed:", {m: r for m, r in renamed.items() if m != r and owner[m] in P.SHARED})


if __name__ == "__main__":
    main()
