"""生成本任务的静态引用证据和逐项删除清单，不执行应用或外部调用。"""

import ast
import json
from pathlib import Path
import re
import subprocess


TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[2]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def test_names(source):
    return {
        f"{cls.name}.{node.name}"
        for cls in ast.parse(source).body if isinstance(cls, ast.ClassDef)
        for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


changes = [row.split("\t") for row in git("diff", "--name-status").splitlines()]
deleted = [path for status, path in changes if status == "D"]
modules = {path[:-3].replace("/", ".") for path in deleted if path.endswith(".py")}
pattern = re.compile(r"runtime_runner|runtime_facade|ConversionService|JobStageService|StageWorker|stage_dispatcher|replay_pending|ConversionFailure")
references = []
module_references = []
parsed = 0
for directory in ("app", "scripts", "tests"):
    for path in (ROOT / directory).rglob("*.py"):
        source = path.read_text()
        relative = path.relative_to(ROOT)
        tree = ast.parse(source)
        parsed += 1
        for line_number, line in enumerate(source.splitlines(), 1):
            if pattern.search(line):
                references.append(f"{relative}:{line_number}:{line.strip()}")
            if any(module in line or module.replace(".", "/") + ".py" in line for module in modules):
                module_references.append(f"{relative}:{line_number}:{line.strip()}")
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = relative.with_suffix("").parts[:-1]
                    module = ".".join(parts[:len(parts) - node.level + 1])
                    module += "." + node.module if node.module else ""
                else:
                    module = node.module or ""
                candidates = [module] + [module + "." + alias.name for alias in node.names]
            if any(candidate in modules for candidate in candidates):
                module_references.append(f"{relative}:{node.lineno}:{candidates}")

report = {
    "python_files_parsed": parsed,
    "removed_python_modules": len(modules),
    "symbol_references_before": len((TASK / "static-before.txt").read_text().splitlines()),
    "symbol_references_after": references,
    "deleted_module_import_or_text_references": sorted(set(module_references)),
}
(TASK / "static-after.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
assert not references and not module_references, report

files = []
tests = []
for status, path in changes:
    previous = git("show", "HEAD:" + path)
    if status == "D":
        files.append({"path": path, "deleted_lines": len(previous.splitlines())})
    if path.startswith("tests/") and path.endswith(".py"):
        remaining = test_names((ROOT / path).read_text()) if status != "D" else set()
        for name in sorted(test_names(previous) - remaining):
            if "formal_conversion_configuration" in path:
                reason = "仅移除旧配置导出断言；正式生成配置与默认值断言在重命名方法中保留。"
            elif "workflow_policy" in path:
                reason = "仅覆盖已删除旧 jobs workflow 状态转换；共享模型 4 项测试保留。"
            elif "fastapi_jobs_backend" in path:
                reason = "仅覆盖旧 stage/jobs 调度、仓储或旧异常映射；正式 API、回调与健康测试保留。"
            elif "database_job_repository" in path:
                reason = "仅覆盖旧 stage 启动重放与仓储；正式仓储及事件测试保留。"
            elif "mineru_download_boundary" in path:
                reason = "仅覆盖旧 stage 结果恢复；正式轮询与回调下载边界保留。"
            elif "conversion_sandbox_dev_tools" in path:
                reason = "仅检查旧运行时动态绑定；正式本地 adapter 测试保留。"
            elif "artifact" in path:
                reason = "仅覆盖旧 JobFile artifact 存储、迁移或保留期；正式 DocumentFile 用例保留。"
            elif "shadow_copy" in path or "storage_integrity" in path:
                reason = "仅覆盖已删除旧 jobs/stage 元数据运维脚本。"
            else:
                reason = "仅覆盖旧运行时或直接加载机制；混合文件中的共享规则测试保留并直接导入。"
            tests.append({"path": path, "test": name, "reason": reason})

stats = [row.split("\t") for row in git("diff", "--numstat").splitlines()]
summary = {
    "files_deleted": len(files),
    "deleted_file_lines": sum(item["deleted_lines"] for item in files),
    "diff_added_lines": sum(int(row[0]) for row in stats if row[0].isdigit()),
    "diff_deleted_lines": sum(int(row[1]) for row in stats if row[1].isdigit()),
    "removed_test_methods": len(tests),
}
inventory = {"summary": summary, "deleted_files": files, "removed_tests": tests,
             "changed_files": [path for _, path in changes]}
(TASK / "deletion-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
(TASK / "deletion-inventory.md").write_text(
    "# 删除清单\n\n" + json.dumps(summary, ensure_ascii=False) +
    "\n\n测试方法计数包含一项仅去掉旧断言后重命名的方法，正式断言保留。\n\n## 已删除文件\n\n" +
    "".join(f'- `{item["path"]}`：{item["deleted_lines"]} 行。\n' for item in files) +
    "\n## 已移除测试及范围\n\n" +
    "".join(f'- `{item["path"]}::{item["test"]}`：{item["reason"]}\n' for item in tests)
)
print(json.dumps({"static": report, "deletions": summary}, ensure_ascii=False, indent=2))
