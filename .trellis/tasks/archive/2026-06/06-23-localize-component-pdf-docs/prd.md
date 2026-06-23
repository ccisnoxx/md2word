# localize component PDF governance docs

## Goal

将上一轮新增的电子元器件 PDF 样例治理 Markdown 文档改为中文，使本地调试、样例沉淀、回归运行和人工验收流程能被中文使用者直接阅读和执行。

## What I Already Know

- 用户明确指出新增 `.md` 文档是英文，但需要中文文档。
- 上一轮之所以写成英文，是因为 `.trellis/spec/backend/index.md` 当前声明 “All documentation should be written in English”。
- 本次修正应优先满足用户对本地工作流文档的使用需求。
- 当前工作树存在与本任务无关的脏文件：`.idea/md2word.iml` 以及 `output/playwright/...` 删除记录，本任务不得触碰这些文件。

## Requirements

- 将 `docs/dev/component-pdf-regression-governance.md` 的用户可读内容改为中文，保留命令、路径、文件名、参数名和 YAML front matter 键名。
- 将 `tests/fixtures/component_pdf_samples/README.md` 改为中文，保留目录结构示例和命令可复制性。
- 将 `tests/fixtures/component_pdf_samples/acceptance-record-template.md` 改为中文，保留可填写模板结构和状态枚举值。
- 检查 README / dev docs index / local sandbox doc 中新增链接附近的说明是否已经是中文；如已有中文，不做无关改动。
- 不修改 `app/conversion` 渲染、解析或回归脚本逻辑。
- 不修改 `.idea`、`output/playwright` 等与本任务无关的现有脏文件。

## Acceptance Criteria

- [ ] 三份面向使用者的 Markdown 文档主体为中文。
- [ ] 命令、路径、脚本参数、样例 ID、枚举值保持可复制和机器可读。
- [ ] `rg` 检查三份文档中不再残留大段英文说明文本。
- [ ] `git diff --check` 通过。
- [ ] 运行样例治理相关的最小验证，确认文档改动未影响脚本入口。

## Definition of Done

- 文档中文化完成。
- 最小验证通过。
- 仅本任务文件进入提交；无关脏文件保持原样。
- Trellis 任务归档并记录 journal。

## Out of Scope

- 不翻译 `.trellis/spec/` 中既有 agent 规范文档，除非后续明确决定项目规范也改为中文。
- 不重写 manifest schema、CLI 参数或测试逻辑。
- 不清理或恢复当前已有的 IDE / Playwright 输出脏文件。

## Technical Notes

- 相关文档：
  - `docs/dev/component-pdf-regression-governance.md`
  - `tests/fixtures/component_pdf_samples/README.md`
  - `tests/fixtures/component_pdf_samples/acceptance-record-template.md`
- 相关验证：
  - `.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate`
  - `.venv/bin/python -m unittest tests.test_component_pdf_sample_governance`
  - `git diff --check`
