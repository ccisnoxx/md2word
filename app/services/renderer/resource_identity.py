"""实际渲染资源的规范化指纹与已加载实现身份。"""
from __future__ import annotations

import hashlib
import marshal
import sys
from types import FunctionType

from app.services.renderer.render_plan import ResourceIdentity, content_hash


def normalized_resource_identity(*, template_content, config, logo_content, document_language):
    """渲染与声明对账共用同一规范化语义，避免比较文件 hash 与内容 hash。"""
    snapshot = config.model_dump(mode="json", exclude={"terminology", "sample_content", "language_overrides", "template_name", "output_filename"})
    snapshot["header"]["logo_path"] = None
    terminology = config.terminology
    rules = [{"source": rule.source, "pattern": rule.pattern, "replacement": rule.replacement,
        "priority": rule.priority, "apply_scope": rule.apply_scope, "enabled": rule.enabled,
        "regex_flags": rule.regex.flags if rule.regex is not None else None} for rule in terminology.rules] if terminology else []
    return ResourceIdentity(template_sha256=hashlib.sha256(template_content).hexdigest() if template_content is not None else None,
        effective_config_sha256=content_hash(snapshot), symbol_rules_sha256=content_hash(rules) if rules else None,
        logo_sha256=hashlib.sha256(logo_content).hexdigest() if logo_content is not None else None,
        document_language=document_language)


def renderer_implementation_identity() -> dict:
    """记录本进程已加载的实际 Python code，而非可在运行后改变的磁盘源码或 schema 号。"""
    modules = {}
    for name, module in tuple(sys.modules.items()):
        if not name.startswith(("app.services.renderer.", "app.conversion.docx_rules.")) or module is None:
            continue
        codes = {}
        for symbol, value in sorted(vars(module).items()):
            if isinstance(value, FunctionType) and value.__module__ == name:
                codes[symbol] = hashlib.sha256(marshal.dumps(value.__code__)).hexdigest()
            elif isinstance(value, type) and value.__module__ == name:
                for method_name, method in sorted(vars(value).items()):
                    method = method.__func__ if isinstance(method, (staticmethod, classmethod)) else method
                    if isinstance(method, FunctionType):
                        codes[symbol + "." + method_name] = hashlib.sha256(marshal.dumps(method.__code__)).hexdigest()
        if codes:
            modules[name] = content_hash(codes)
    return {"schema_version": "renderer-python-code/v1", "implementation_sha256": content_hash(modules), "modules": modules}
