"""document_jobs 用例拆分后的测试辅助。

拆分前所有应用层逻辑都在同一模块、同一对象里，测试可以只 patch 一个模块名或只替换一个对象属性。
拆分后同一名字分布在多个用例模块和组件中，这里统一把 patch/替换同步到全部持有方，
覆盖的调用点集合与拆分前完全相同。
"""

from __future__ import annotations

import importlib
import pkgutil
from contextlib import ExitStack, contextmanager
from dataclasses import fields
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import app.domains.document_jobs.use_cases as use_cases_package
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.use_cases import DocumentJobUseCases


def _use_case_modules() -> list[Any]:
    return [importlib.import_module(f"{use_cases_package.__name__}.{info.name}")
            for info in pkgutil.iter_modules(use_cases_package.__path__)]


@contextmanager
def patch_use_case_global(name: str, **mock_kwargs: Any) -> Iterator[MagicMock]:
    """在所有导入了 `name` 的用例模块中替换为同一个 mock，共享调用计数与 side_effect 序列。"""

    owners = [module for module in _use_case_modules() if hasattr(module, name)]
    if not owners:
        raise AssertionError(f"没有用例模块导入 {name}")
    mock = MagicMock(**mock_kwargs)
    with ExitStack() as stack:
        for module in owners:
            stack.enter_context(patch.object(module, name, mock))
        yield mock


def patch_use_case_clock(**mock_kwargs: Any):
    """冻结用例层的 utc_now；等价于拆分前 patch `app.domains.document_jobs.service.utc_now`。"""

    return patch_use_case_global("utc_now", **mock_kwargs)


def patch_publication_evidence(**mock_kwargs: Any):
    """替换用例层的 prepare_publication_evidence（发布命令与读视图发布动作共用）。"""

    return patch_use_case_global("prepare_publication_evidence", **mock_kwargs)


def replace_dependency(use_cases: DocumentJobUseCases, name: str, value: Any) -> Any:
    """把构造后替换的依赖同步到 bundle 中所有持有该依赖的组件，返回 value 便于链式赋值。"""

    holders = [getattr(use_cases, field.name) for field in fields(use_cases)]
    holders = [holder for holder in holders if hasattr(holder, name)]
    if not holders:
        raise AssertionError(f"没有用例组件持有依赖 {name}")
    for holder in holders:
        setattr(holder, name, value)
    return value


def build_incident_service(use_cases: DocumentJobUseCases, file_repository: Any) -> DocumentJobIncidentService:
    return DocumentJobIncidentService(file_repository=file_repository, access=use_cases.access,
                                      read_model=use_cases.read_model, queries=use_cases.queries,
                                      submission=use_cases.submission)
