# Conversion Core Into FastAPI Design

## Summary

本次重构把“共享转换核心”从仓库根目录迁入 `app/conversion/`，并把根目录旧核心
整体迁到 `legacy/cli_core/` 作为历史归档。最终结构中：

- FastAPI 只依赖 `app/` 内部转换模块
- `mineru_to_docx.py` 只承担 CLI / PyCharm 入口与少量兼容职责
- `legacy/cli_core/` 只作为历史保留，不参与 FastAPI 运行时

## Scope

In scope:

- `app/conversion/*`
- `app/services/health_service.py`
- `mineru_to_docx.py`
- 根目录转换运行时模块迁移：
  - `input_adapter_runtime.py`
  - `page_layout_runtime.py`
  - `page_repair_runtime.py`
  - `render_config_runtime.py`
  - `text_rendering.py`
  - `translation_runtime.py`
  - `llm_client.py`
  - `table_html_parser.py`
  - `table_long_renderer.py`
  - `table_render_runtime.py`
- 必要的测试迁移：
  - `tests/test_fastapi_jobs_backend.py`
  - 受影响的 `tests/test_*_characterization.py`
  - `tests/runtime_direct_loaders.py`

Out of scope:

- FastAPI API 契约变更
- 转换算法或输出语义调整
- term rules / templates 领域代码
- 大规模测试框架迁移

## Design Goals

1. 让 FastAPI 的转换调用链完全落在 `app/` 目录内。
2. 把 CLI 核心和服务核心的边界从“共享根目录脚本/模块”改为“共享 app 模块”。
3. 归档历史代码，但不让历史代码反向成为服务依赖。
4. 保持 characterization tests 对既有行为的约束能力。
5. 让 `mineru_to_docx.py` 变成薄入口，而不是核心实现拥有者。

## Current Problem Shape

当前最大的问题不是有没有 `app/conversion/`，而是它只是中间层：

- `app/conversion/runtime_facade.py` 仍直接 re-export 根目录模块
- `app/conversion/runtime_runner.py` 仍直接 import 根目录运行时
- `app/conversion/runtime_helpers.py`、`runtime_rendering_api.py` 也仍直接依赖根目录
- `app/services/health_service.py` 仍绕过 `app/conversion/` 直接依赖根目录 `llm_client.py`
- `mineru_to_docx.py` 仍同时承担入口、运行时绑定、核心 orchestration、兼容导出

这导致：

1. FastAPI 不能被视为真正的“壳层”
2. 共享核心没有稳定归属目录
3. 任何后续服务化改造都还会被根目录历史代码牵制

## Target Module Shape

### App Conversion Core

建议把转换核心统一收敛到 `app/conversion/`，保留现有顶层目录，但把运行时实现整理成
明确子模块。目标形态可接受如下两种之一：

- 继续使用现有 `app/conversion/*.py`
- 或在其下新增 `app/conversion/runtime/` 承载迁入的旧核心

本次优先选择“最小变更路径”：

- 保留 `app/conversion/` 现有对外入口
- 将旧根目录模块迁入 `app/conversion/` 的稳定位置
- 重写内部 imports 指向新位置

### Legacy Archive

根目录旧核心迁入 `legacy/cli_core/`，用途仅限：

- 历史参考
- 行为对照
- 必要时辅助 characterization 分析

明确禁止：

- `app/*` import `legacy/cli_core/*`
- 新代码继续往 `legacy/cli_core/` 写运行时逻辑

### CLI Entrypoint

`mineru_to_docx.py` 最终应保留：

- CLI 参数解析
- PyCharm/local run config
- 调用 `app/conversion/` 公开入口
- 若测试仍需要，保留少量显式兼容 re-export

不再保留：

- 作为 FastAPI 或共享核心的真正实现归属地

## Migration Strategy

### Stage 1: Move Core Modules Into `app/conversion/`

先把仍被 `app/` 直接依赖的根目录运行时模块迁入 `app/conversion/` 下的新稳定位置，
并统一修改 `app/conversion/*` 的 imports。

目标：

- FastAPI 的直接依赖链先完全脱离仓库根目录

### Stage 2: Rewire CLI Entrypoint

让 `mineru_to_docx.py` 改为调用 `app/conversion/` 公开入口，而不是自己承载核心逻辑。
如果需要，为 characterization tests 保留兼容符号，但兼容层应当是薄封装。

目标：

- CLI 仍可直跑
- 核心实现所有权转移到 `app/conversion/`

### Stage 3: Update Health/Test Seams

把 `app/services/health_service.py` 与受影响测试的 import seam 改到新模块位置。
其中 characterization tests 需要尽量迁到明确模块，而不是继续把根目录脚本当成唯一入口。

目标：

- 服务侧和测试侧都认同新的核心归属

### Stage 4: Archive Historical Root Modules

将根目录旧核心文件移入 `legacy/cli_core/`，保留历史代码但从运行时链路断开。
如有必须留在根目录的极少数兼容文件，应只做薄代理，不保留真实实现。

目标：

- 仓库结构上完成“核心入 app，历史进 legacy”的收口

## Import Boundary Rules

重构完成后遵守以下规则：

- `app/*` 只能依赖：
  - `app/*`
  - 必要的共享根目录配置文件，如 `config.py`，如果本轮未一并内聚
- `app/*` 不得依赖：
  - 根目录旧核心运行时模块
  - `legacy/cli_core/*`
- `mineru_to_docx.py` 可以依赖：
  - `app/conversion/*`
  - 本地入口所需的配置
- `legacy/cli_core/*` 不作为任何新运行时依赖目标

## Test Strategy

按最小充分顺序验证：

1. `tests/test_fastapi_jobs_backend.py`
2. 受影响的 characterization tests：
   - 直接覆盖迁移模块的用例
   - `tests/runtime_direct_loaders.py` 相关加载路径
3. `mineru_to_docx.py` 本地 import / smoke

验证重点不是“所有测试全跑”，而是：

- FastAPI 依赖链已不再出根目录
- CLI 入口仍能调起转换核心
- characterization seams 没因迁移丢失行为约束

## Key Risks

1. 运行时模块之间存在 `bind_runtime()` 或导入顺序耦合，迁移后可能出现绑定失效。
2. characterization tests 当前严重依赖根目录模块路径，直接迁移可能导致 patch seam 失效。
3. `mineru_to_docx.py` 缩薄过早会让 CLI 或测试都找不到兼容符号。
4. 历史归档如果先做物理移动、后改 import，容易造成中间状态不可运行。

## Risk Mitigations

- 先迁 `app/conversion` 内部依赖，再改 CLI，再归档根目录文件。
- 对测试采用“改 seam 不改断言”的策略，优先更新 import target。
- 将 `mineru_to_docx.py` 兼容层保留到最后收口。
- 在归档前先用 `rg` 确认 `app/` 已无旧路径引用。

## Success Criteria

- `app/` 已不再 import 根目录旧核心模块。
- `app/` 已不再 import `legacy/cli_core/`。
- `mineru_to_docx.py` 已降为入口壳层。
- 历史核心代码已迁入 `legacy/cli_core/`。
- 目标测试通过，且未观察到行为回归。
