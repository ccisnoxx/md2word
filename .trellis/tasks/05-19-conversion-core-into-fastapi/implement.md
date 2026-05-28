# Conversion Core Into FastAPI Implementation Plan

## Scope

按已确认方案完成一次行为等价的结构收口：

- 转换核心并入 `app/conversion/`
- CLI 保留为 `mineru_to_docx.py`
- 根目录旧核心归档到 `legacy/cli_core/`
- FastAPI 禁止再引用历史目录

## Ordered Checklist

### 1. Map runtime module ownership and import graph

Files:

- `app/conversion/*`
- `app/services/health_service.py`
- 根目录旧核心模块
- `tests/runtime_direct_loaders.py`

Goals:

- 明确每个根目录运行时模块在 `app/conversion/` 的新归属位置
- 识别必须保留的 CLI 兼容导出和测试 seam

Validation:

- `rg -n "input_adapter_runtime|page_layout_runtime|page_repair_runtime|render_config_runtime|text_rendering|translation_runtime|llm_client|table_html_parser|table_long_renderer|table_render_runtime" app tests mineru_to_docx.py`

Rollback point:

- 此步仅做分析，不改代码

### 2. Move shared runtime modules into `app/conversion/`

Files:

- `app/conversion/*`
- 新增承载迁移代码的 `app/conversion/` 模块

Goals:

- 把 FastAPI 运行时依赖的共享转换核心迁到 `app/conversion/`
- 改写 `app/conversion/*` 内部 imports 到新位置

Validation:

- 目标模块 import smoke
- `rg -n "from input_adapter_runtime|import input_adapter_runtime|from page_layout_runtime|import page_layout_runtime|from llm_client|import llm_client" app/conversion app/services`

Rollback point:

- 恢复新增模块并回退 imports 到旧位置

### 3. Rewire `mineru_to_docx.py` to the new core

Files:

- `mineru_to_docx.py`
- 必要时 `app/conversion/entrypoint.py` 或相关公开入口

Goals:

- 让 CLI 入口调用 `app/conversion/` 公开核心
- 保留最小兼容导出，避免过度耦合测试到旧实现

Validation:

- `python3 -m py_compile mineru_to_docx.py`
- 针对 CLI 相关最小 characterization / import smoke

Rollback point:

- 恢复 `mineru_to_docx.py` 对旧实现的直接承载方式

### 4. Update health/test seams

Files:

- `app/services/health_service.py`
- `tests/runtime_direct_loaders.py`
- 受影响的 `tests/test_*_characterization.py`

Goals:

- 让健康检查和测试都指向新的核心模块归属
- 保留行为断言不变，仅迁移 import seam / loader seam

Validation:

- 运行受影响测试子集

Rollback point:

- 恢复测试 loader 和 health import 到旧位置

### 5. Archive historical root modules into `legacy/cli_core/`

Files:

- 根目录旧核心模块
- `legacy/cli_core/*`

Goals:

- 完成历史代码归档
- 保证 `app/` 已完全断开对旧路径的依赖

Validation:

- `rg -n "legacy/cli_core|input_adapter_runtime|page_layout_runtime|page_repair_runtime|render_config_runtime|text_rendering|translation_runtime|llm_client|table_html_parser|table_long_renderer|table_render_runtime" app`

Rollback point:

- 将归档文件移回原位，但保留前面已完成的 `app/conversion/` 收口

### 6. Final targeted verification

Files:

- 所有改动文件

Goals:

- 确认 FastAPI、CLI 和受影响测试路径都仍可工作

Validation:

- `python3 -m unittest tests.test_fastapi_jobs_backend`
- 受影响的 characterization tests
- `python3 -m py_compile mineru_to_docx.py`

Rollback point:

- 逐步回退最后一次修改，直到恢复最近的可验证状态

## Review Gates Before `task.py start`

- Confirm `app/conversion/` 是唯一共享转换核心归属目录。
- Confirm `legacy/cli_core/` 只做历史归档，不作为运行时依赖。
- Confirm characterization tests 可以迁 seam，但不放松行为约束。
- Confirm 本轮以最小必要验证为主，不做全仓库无差别重跑。
