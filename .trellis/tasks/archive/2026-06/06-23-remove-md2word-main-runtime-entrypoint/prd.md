# remove md2word_main runtime entrypoint

## Goal

彻底停止从 `/Users/sc/PycharmProjects/PythonProject/md2word_main` 运行转换代码，把本地 MinerU 转 DOCX 调试入口收敛到正式项目 `/Users/sc/PycharmProjects/md2word`。`md2word_main` 只保留历史样例资产和输出目录；正式项目提供适合 PyCharm 直接运行的配置文件驱动入口。

## What I Already Know

- 用户明确要求以后完全不从 `md2word_main` 运行转换代码。
- `md2word_main` 应只作为历史样例资产目录，保留 `test_pdf/`、`mineru_result/`、`out/` 等资产。
- 当前 `md2word_main/mineru_to_docx.py` 仍代理调用正式项目的 `scripts.dev.run_local_mineru_conversion`，需要改为 deprecated 提示并退出。
- 正式项目已有 `scripts/dev/run_local_mineru_conversion.py`，但它主要依赖 CLI 参数或环境变量，不适合 PyCharm 一键运行。
- 正式项目已有 `docs/dev/local-conversion-sandbox.md`，但仍使用旧 `/Users/sc/miniconda3/envs/md2word/bin/python` 路径，并描述从 `md2word_main` 内运行薄壳。
- 当前工作树存在与本任务无关的 `.idea/md2word.iml` 和 `output/` 删除状态，本任务不得提交或恢复这些改动。
- 修改 `/Users/sc/PycharmProjects/PythonProject/md2word_main` 超出正式项目可写根目录，需要走审批写入。

## Requirements

- 在正式项目新增或改造一个 PyCharm 友好的本地调试脚本，优先读取 repo 内配置文件，例如 `scripts/dev/local_mineru_debug_config.json`，然后调用 `app.conversion.runtime_runner.run_conversion`。
- 配置文件必须支持常用参数：
  - `input_path`
  - `output_path`
  - `document_language`
  - `translation_mode`
  - `template_path` / `template`
  - `layout_config_path` / `layout_config`
  - `subscript_config`
  - `no_template`
  - `use_mineru_header_footer`
  - translation request/response/trace/model/base-url/max-pages/max-chars 等现有本地入口参数
  - `log_level`
- 配置中的相对路径从正式项目根目录解析；绝对路径可以指向 `md2word_main/mineru_result`。
- `md2word_main/mineru_to_docx.py` 标记为 deprecated，运行时明确提示：
  - 不再从 `md2word_main` 运行转换代码；
  - 去正式项目 `md2word` 使用新的 PyCharm 调试入口；
  - 不再代理调用 `scripts.dev.run_local_mineru_conversion`。
- 更新 `md2word_main/README.md`，明确它只是历史样例资产目录，并指向正式项目 PyCharm 入口。
- 更新 `docs/dev/local-conversion-sandbox.md`，把推荐路径改为正式项目内 PyCharm 运行方式，并删除/弱化从 `md2word_main` 运行转换的说明。
- 必要时更新正式项目 README / 测试文档，明确推荐 PyCharm 使用方式。
- 修正文档里与本任务相关的不存在解释器路径 `/Users/sc/miniconda3/envs/md2word/bin/python`，改为“选择项目 Python 3.11 解释器”或 `.venv/bin/python`。
- 补充或调整测试，覆盖：
  - `md2word_main` 入口 deprecated 行为；
  - 正式项目 PyCharm 配置读取和 `run_conversion` 参数构建；
  - 配置中样例路径的相对/绝对解析。

## Acceptance Criteria

- [ ] 正式项目中存在配置文件驱动的 PyCharm 本地 MinerU 转 DOCX 调试入口。
- [ ] `scripts/dev/local_mineru_debug_config.json` 或等价文件可作为 PyCharm Run Configuration 的默认配置。
- [ ] 新入口直接调用 `app.conversion.runtime_runner.run_conversion`，不依赖 `md2word_main` 入口。
- [ ] `md2word_main/mineru_to_docx.py` 运行时只输出 deprecated 指引并非零退出，不再代理调用正式项目转换脚本。
- [ ] `md2word_main/README.md` 和正式项目相关文档均说明新推荐路径。
- [ ] 针对性测试覆盖配置解析、参数构建、路径解析、deprecated 行为。
- [ ] 不修改转换渲染策略，不做无关 app/conversion 重构。
- [ ] 运行针对性验证并记录结果。

## Definition of Done

- 代码、配置、文档和测试改动完成。
- 正式项目测试通过。
- `md2word_main` 外部文件改动已完成或明确说明权限阻塞。
- 工作提交不包含既有无关 `.idea` / `output` 改动。
- Trellis 任务归档并记录 journal。

## Out of Scope

- 不迁移或删除 `md2word_main/test_pdf`、`md2word_main/mineru_result`、`md2word_main/out`。
- 不改变 `app/conversion` 渲染策略、表格策略、翻译策略或模板策略。
- 不清理当前已有 `.idea` 和 `output/playwright` 工作区改动。
- 不重跑真实 MinerU 或线上服务。

## Technical Notes

- 已检查文件：
  - `scripts/dev/run_local_mineru_conversion.py`
  - `scripts/dev/migrate_md2word_main_sandbox.py`
  - `tests/test_conversion_sandbox_dev_tools.py`
  - `docs/dev/local-conversion-sandbox.md`
  - `/Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_to_docx.py`
  - `/Users/sc/PycharmProjects/PythonProject/md2word_main/README.md`
  - `/Users/sc/PycharmProjects/PythonProject/md2word_main/tests/test_thin_shell.py`
- 预计新增正式项目脚本：
  - `scripts/dev/run_local_mineru_debug_config.py`
  - `scripts/dev/local_mineru_debug_config.json`
- 预计测试命令：
  - `.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools`
  - `.venv/bin/python -m unittest tests.test_component_pdf_sample_governance`
  - `git diff --check`
