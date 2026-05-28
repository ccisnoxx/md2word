# Refactor conversion core into FastAPI app

## Goal

把当前仍散落在仓库根目录的 CLI 转换核心完整并入 `app/conversion/`，
使 FastAPI 仅依赖 `app/` 内部转换模块；原根目录核心代码迁入
`legacy/cli_core/` 作为历史归档，且不再作为 FastAPI 的运行时依赖。

## Confirmed Facts

- 当前仓库存在两层结构：
  - `mineru_to_docx.py` 为本地 CLI / PyCharm 入口
  - `app/` 为 FastAPI 服务层
- `app/conversion/service.py`、`app/conversion/runtime_runner.py`、
  `app/conversion/runtime_facade.py`、`app/conversion/runtime_helpers.py`、
  `app/conversion/runtime_rendering_api.py` 当前仍直接依赖根目录模块：
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
- `app/services/health_service.py` 当前也直接依赖根目录 `llm_client.py`。
- `mineru_to_docx.py` 目前不是单纯入口文件，仍混合了：
  - CLI 参数解析与本地直跑配置
  - 运行时模块绑定
  - 转换核心 orchestration 和兼容导出
- 现有行为主要由两类测试覆盖：
  - `tests/test_fastapi_jobs_backend.py`
  - 多个 `tests/test_*_characterization.py`
- 用户已明确确认本次目标：
  - 转换核心迁入 `app/conversion/`
  - 根目录旧核心迁到 `legacy/cli_core/` 历史归档
  - FastAPI 禁止再引用旧目录

## Requirements

- 保持本次重构为 `behavior-preserving refactor`。
- FastAPI 运行时依赖必须完全收敛到 `app/` 内部，不得再 import 根目录旧核心或
  `legacy/cli_core/`。
- `mineru_to_docx.py` 继续保留用户入口职责，面向本地开发、调试和直跑转换。
- 允许 `mineru_to_docx.py` 在重构后调用 `app/conversion/` 中的新核心入口。
- 允许在 `app/conversion/` 下新增子模块或子包，只要不引入额外框架层。
- 根目录旧核心模块需要整体迁入 `legacy/cli_core/`，作为历史代码保留。
- characterization tests 如果当前绑定点依赖根目录模块，允许做最小必要迁移，
  但行为断言不能被放宽。
- 不改变：
  - FastAPI API 契约
  - job lifecycle 语义
  - DOCX 转换输出语义
  - 现有 CLI 主入口名字 `mineru_to_docx.py`
- 不在本任务中处理：
  - term rules / templates 新需求
  - 新 API
  - 新依赖引入
  - 大范围行为优化

## Acceptance Criteria

- [ ] `app/` 下所有运行时代码不再 import 根目录旧核心模块。
- [ ] `app/` 下所有运行时代码不再 import `legacy/cli_core/`。
- [ ] 转换核心实现已移动到 `app/conversion/` 内部稳定模块。
- [ ] `mineru_to_docx.py` 仍可作为本地 CLI / PyCharm 入口工作。
- [ ] 根目录旧核心文件已迁入 `legacy/cli_core/` 历史目录。
- [ ] FastAPI 后端测试通过最小相关验证。
- [ ] 受影响的 characterization tests 通过最小相关验证。
- [ ] PRD、`design.md`、`implement.md` 在 `task.py start` 前完成并经用户确认。

## Likely Out Of Scope

- 把历史代码彻底删除而不是归档。
- 在同一轮里重写全部 characterization 测试风格。
- 修改 `FileJobRepository`、任务状态机或 API 路由设计。
- 以“顺手清理”为名进行无关模块重构。

## Notes

- 这次重构的本质不是“让 FastAPI 调另一个壳”，而是“把共享转换核心真正收回
  `app/conversion/`，让 FastAPI 成为组合壳层，CLI 成为本地入口壳层”。
