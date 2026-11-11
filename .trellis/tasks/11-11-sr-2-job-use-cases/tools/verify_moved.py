"""独立核验：use_cases 中每个方法反向还原后应与 HEAD 中 DocumentJobService 原方法逐字一致。"""
import ast, pathlib, re, subprocess, sys

old_src = subprocess.run(["git", "show", "HEAD:app/domains/document_jobs/service.py"],
                         capture_output=True, text=True, check=True).stdout
old_lines = old_src.splitlines(keepends=True)
old_cls = next(n for n in ast.parse(old_src).body if isinstance(n, ast.ClassDef) and n.name == "DocumentJobService")
old = {}
for f in old_cls.body:
    if isinstance(f, ast.FunctionDef) and f.name != "__init__":
        s = (f.decorator_list[0].lineno if f.decorator_list else f.lineno) - 1
        old[f.name] = "".join(old_lines[s:f.end_lineno]).rstrip("\n")
COMMON = {"UNREAD_RESULT": "_UNREAD_RESULT", "SYSTEM_LOGGER": "_SYSTEM_LOGGER", "ReviewCommit": "_ReviewCommit",
          "TableReferenceSnapshot": "_TableReferenceSnapshot", "DocumentJobSearchable": "_DocumentJobSearchable"}
COMPS = ["events", "access", "read_model", "review_writer", "dispatcher", "request_snapshot", "submission",
         "lifecycle_commands", "publication", "quality_review", "table_references", "translation_qa", "downloads", "queries"]
new = {}
for comp in COMPS:
    src = pathlib.Path(f"app/domains/document_jobs/use_cases/{comp}.py").read_text()
    lines = src.splitlines(keepends=True)
    cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef))
    for f in cls.body:
        if isinstance(f, ast.FunctionDef) and f.name != "__init__":
            s = (f.decorator_list[0].lineno if f.decorator_list else f.lineno) - 1
            new[(comp, f.name)] = "".join(lines[s:f.end_lineno]).rstrip("\n")


SHARED = {"events", "access", "read_model", "review_writer", "dispatcher", "request_snapshot"}


def old_name(name, comp=None):
    if name == "get_authorized_job":
        return "_get_job"
    # 共享组件中由私有方法公开化而来的名字，优先还原为旧私有名
    if comp in SHARED and "_" + name in old and name != "get_job":
        return "_" + name
    if name in old:
        # 公开名在旧类中存在：若旧类同时有 _name，则需看上下文；共享组件仅当旧名不存在时才去掉了下划线
        return name
    return "_" + name


def restore(text, comp):
    text = re.sub(r"\bself\.(%s)\.(\w+)\b" % "|".join(COMPS), lambda m: "self." + old_name(m.group(2), m.group(1)), text)
    text = re.sub(r"\bself\.(\w+)\b", lambda m: "self." + (old_name(m.group(1), comp) if m.group(1) not in {
        "settings", "job_repository", "event_repository", "file_repository", "task_queue", "template_read_service",
        "term_version_service", "job_resource_snapshot_service", "document_job_translation_batch_repository",
        "file_upload_service", "word_preview_service", "audit_service"} else m.group(1)), text)
    for k, v in COMMON.items():
        text = re.sub(rf"\b{k}\b", v, text)
    return text


bad, seen = [], set()
for (comp, name), text in new.items():
    o = old_name(name, comp)
    restored = restore(text, comp)
    restored = re.sub(rf"\bdef {re.escape(name)}\(", f"def {o}(", restored, count=1)
    seen.add(o)
    if restored != old.get(o):
        bad.append((comp, name))
missing = sorted(set(old) - seen)
print(f"核对 {len(new)} 个方法；不一致 {len(bad)}：{bad[:10]}；未迁移：{missing}")
sys.exit(1 if bad else 0)
