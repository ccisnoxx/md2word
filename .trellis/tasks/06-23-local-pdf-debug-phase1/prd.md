# 落地本地 PDF direct/en2zh 调试第一阶段

## Goal

在正式项目 `/Users/sc/PycharmProjects/md2word` 内建立可重复使用的本地 MinerU PDF 调试流程，覆盖 `direct` 和 `en2zh` 两条路径，支持 PyCharm 直接运行或通过配置文件运行，并把实施计划和使用指南归档。

## What I already know

- `/Users/sc/PycharmProjects/md2word` 是唯一长期维护的转换代码源。
- `/Users/sc/PycharmProjects/md2word/mineru_result` 下已有 OPA228 P1/P2/P6/P7 MinerU 结果样例。
- `scripts/dev/run_local_mineru_debug_config.py` 已支持 JSON 配置入口。
- `scripts/dev/run_local_mineru_conversion.py` 已支持 `direct`、`en2zh`、`llm_en_to_zh`、`translation_response`、`translation_trace_output` 等参数。
- `en2zh` 无 `translation_response` 时会调用 OpenAI-compatible API；缺 `OPENAI_API_KEY` 必须失败，不能静默降级。
- `tests/tmp/` 已被忽略，适合作为 DOCX、trace 和本地报告输出目录。

## Requirements

- 不从 `md2word_main` 运行任何转换；文档中的默认示例应改为正式项目内路径。
- 提供 direct 与 en2zh 两套可复用本地 JSON 配置，PyCharm 可通过 Run Configuration 指定配置文件运行。
- 归档第一阶段实施计划和实际使用指南，说明新 PDF 到 MinerU 结果、转换、检查、定位、修复、回归的闭环。
- 明确本地 `mineru_result/` 与生成输出不提交，避免泄露专有 PDF、trace、API key。
- 使用项目内 `mineru_result` 样例做最小验证。
- 不修改无关渲染逻辑、翻译逻辑或线上 API 行为。

## Acceptance Criteria

- [ ] direct 配置能从 `mineru_result/OPA228_P1...` 生成 DOCX 到 `tests/tmp/local_mineru_debug/direct/`。
- [ ] en2zh 配置在缺少 API key 且没有 response 文件时明确失败；如果只写 request/trace，不应伪装成功。
- [ ] PyCharm 运行方式和 CLI 等价方式在文档中可直接照抄。
- [ ] 实施计划归档到 `docs/dev/`，并从现有开发文档可发现。
- [ ] `.gitignore` 覆盖本地 `mineru_result/`，保留 fixture 样例治理路径。
- [ ] 相关 dev tool 单测通过；如未跑全量测试，说明原因。

## Out of Scope

- 不重构 `app/conversion` 渲染、布局、翻译核心实现。
- 不沉淀全量品牌/分类样例矩阵。
- 不提交专有 PDF、真实翻译响应、真实 API key 或生成 DOCX。
- 不把 `md2word_main` 恢复为运行入口。

## Technical Notes

- 主要文件：`docs/dev/local-conversion-sandbox.md`、`docs/dev/component-pdf-regression-governance.md`、`scripts/dev/run_local_mineru_debug_config.py`、`scripts/dev/local_mineru_debug_config.json`、`.gitignore`。
- 计划新增配置文件优先放在 `scripts/dev/`，保持 PyCharm script path 不变，只切换 `--config`。
- 计划新增 `docs/dev/local-component-pdf-debugging-implementation-plan.md` 归档第一阶段计划和后续扩展路线。
