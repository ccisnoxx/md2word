"""录制 build_runtime 期间启动副作用的调用顺序（file 与 database 两种后端）。

用法（仓库根目录）：python .trellis/tasks/11-11-sr-3-composition-root/tools/record_bootstrap_order.py <输出 json>
重构前后各运行一次并对比输出。
"""
import json
import sys
import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch

warnings.simplefilter("ignore")

from app.core.config import Settings  # noqa: E402
from app.domains.acceptance.service import AcceptanceRunService  # noqa: E402
from app.domains.term_rules.bootstrap import TermRuleBootstrapService  # noqa: E402
from app.domains.term_rules.file_repository import FileTermRuleRepository  # noqa: E402
from app.domains.term_rules.versioning_service import TermRuleSetVersionService  # noqa: E402
from app.domains.templates.read_service import TemplateReadService  # noqa: E402
from app.domains.translation.profiles_service import TranslationProfileVersionService  # noqa: E402
from app.domains.translation.term_version_service import TermVersionService  # noqa: E402
from app.main import build_runtime  # noqa: E402
from app.services.auth import AuthService  # noqa: E402

TARGETS = [
    (AcceptanceRunService, "bootstrap_default_runs_if_empty"),
    (AuthService, "_bootstrap_repository_from_config_if_empty"),
    (TermVersionService, "bootstrap_repository_from_csv_if_empty"),
    (FileTermRuleRepository, "__init__"),
    (TermRuleSetVersionService, "bootstrap_seed_as_default_if_empty"),
    (TermRuleBootstrapService, "bootstrap"),
    (TranslationProfileVersionService, "bootstrap_default_profiles_if_missing"),
    (TemplateReadService, "get_default_template_id"),
    (TemplateReadService, "bootstrap_manifest_versions"),
    (Settings, "page_quality_policy"),
]


def record(backend: str) -> list[str]:
    calls: list[str] = []
    patches = []
    for owner, name in TARGETS:
        original = getattr(owner, name)

        def wrapper(*args, __original=original, __label=f"{owner.__name__}.{name}", **kwargs):
            calls.append(__label)
            return __original(*args, **kwargs)
        patches.append(patch.object(owner, name, wrapper))
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "data"
        extra = {"jobs_metadata_database_path": str(data_dir / "metadata.sqlite3")} if backend == "database" else {}
        settings = Settings(_env_file=None, data_dir=str(data_dir), jobs_repository_backend=backend, **extra)
        for item in patches:
            item.start()
        try:
            build_runtime(settings)
        finally:
            for item in patches:
                item.stop()
    return calls


if __name__ == "__main__":
    result = {backend: record(backend) for backend in ("file", "database")}
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
