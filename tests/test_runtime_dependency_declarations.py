"""守卫：app/ 的第三方导入必须由 requirements.txt 直接声明，或在白名单中写明来源。

生产镜像只执行 `pip install -r requirements.txt`；仅在本地被其他包间接带入的依赖会让镜像启动失败。
"""
import ast
import re
import sys
import tempfile
from importlib.metadata import packages_distributions
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_fastapi_jobs_backend import build_test_runtime


ROOT = Path(__file__).resolve().parents[1]

# 已声明包的必然传递依赖：{顶层模块: requirements.txt 中声明的父依赖}。
TRANSITIVE_IMPORTS = {
    "starlette": "fastapi",
    "pydantic": "fastapi",
    "pydantic_core": "fastapi",
    "botocore": "boto3",
    "lxml": "python-docx",
    "kombu": "celery",
    "billiard": "celery",
}
# 有意可选：缺失时页面质量观测返回 unavailable，不影响启动。
OPTIONAL_IMPORTS = frozenset({"pdfminer"})


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_requirements(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(normalize(re.split(r"[\s\[<>=!~;]", line, maxsplit=1)[0]))
    return names


def third_party_imports(root: Path) -> dict[str, set[str]]:
    """含函数内延迟导入；忽略相对导入、标准库与 app 自身。"""
    found: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                top = module.split(".", 1)[0]
                if top != "app" and top not in sys.stdlib_module_names:
                    found.setdefault(top, set()).add(path.relative_to(root.parent).as_posix())
    return found


def undeclared_imports(imports, declared, module_distributions) -> dict[str, set[str]]:
    """返回既未直接声明、也不在白名单中的顶层模块及其所在文件。"""
    result = {}
    for module, files in imports.items():
        if module in TRANSITIVE_IMPORTS or module in OPTIONAL_IMPORTS:
            continue
        if not any(normalize(dist) in declared for dist in module_distributions.get(module, ())):
            result[module] = files
    return result


class RuntimeDependencyDeclarationTests(TestCase):
    def setUp(self):
        self.declared = declared_requirements((ROOT / "requirements.txt").read_text(encoding="utf-8"))

    def test_app_imports_are_declared(self):
        missing = undeclared_imports(third_party_imports(ROOT / "app"), self.declared, packages_distributions())
        self.assertEqual(missing, {}, "以下导入未在 requirements.txt 直接声明，生产镜像不会安装：")

    def test_transitive_allowlist_parents_are_declared(self):
        for module, parent in TRANSITIVE_IMPORTS.items():
            with self.subTest(module=module):
                self.assertIn(normalize(parent), self.declared)

    def test_guard_reports_missing_declaration(self):
        imports = {"PIL": {"app/x.py"}, "fastapi": {"app/y.py"}}
        distributions = {"PIL": ["Pillow"], "fastapi": ["fastapi"]}
        self.assertEqual(undeclared_imports(imports, {"fastapi"}, distributions), {"PIL": {"app/x.py"}})
        self.assertEqual(undeclared_imports(imports, {"fastapi", "pillow"}, distributions), {})
        self.assertEqual(undeclared_imports({"unknown_pkg": {"app/z.py"}}, {"fastapi"}, {}),
                         {"unknown_pkg": {"app/z.py"}})

    def test_requirement_name_parsing(self):
        text = "celery[redis]>=5.4,<6\nPyYAML>=6.0  # 注释\n\n# 整行注释\npython_docx\n"
        self.assertEqual(declared_requirements(text), {"celery", "pyyaml", "python-docx"})


class PdfCropToolsReadinessTests(TestCase):
    def _ready(self, available_tools):
        def which(tool):
            return f"/usr/bin/{tool}" if tool in available_tools else None

        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(build_test_runtime(Path(directory)))) as client:
                with patch("app.services.health_service.shutil.which", side_effect=which):
                    return client.get("/api/v1/health/ready").json()["dependency_checks"]

    def test_tools_present_reports_available_without_warning(self):
        checks = self._ready({"pdfinfo", "pdftoppm"})
        self.assertIn("pdf_crop_tools_available", checks["readiness_non_blocking_checks"])
        self.assertIs(checks["pdf_crop_tools_available"], True)
        self.assertNotIn("pdf_crop_tools_missing", checks["readiness_warnings"])

    def test_missing_tool_warns_without_blocking(self):
        present = self._ready({"pdfinfo", "pdftoppm"})
        missing = self._ready({"pdfinfo"})
        self.assertIs(missing["pdf_crop_tools_available"], False)
        self.assertIn("pdf_crop_tools_missing", missing["readiness_warnings"])
        self.assertEqual(missing["readiness_blockers"], present["readiness_blockers"])
