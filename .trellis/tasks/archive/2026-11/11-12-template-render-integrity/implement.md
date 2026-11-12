# 实施与验证

基线为 `30081252df51acdc3205809fe51f8b7df315a2e6`。在 `codex/template-render-integrity` 独立工作树执行。使用项目现有 Python 3.11 环境，在独立工作树目录运行。规划前基线命令为 `python -m unittest tests.test_template_seed_history tests.test_document_ir_word_renderer_layout`，78 项通过。

## 实施顺序

1. **TPL-BASE-001** 在 `tests/test_template_package_contract.py` 固定真实默认模板装饰、关系及单栏/双栏/横向/恢复纵向。以 `python -m unittest tests.test_template_package_contract` 确认运行时代码修改前通过，记录默认资源哈希。
2. **TPL-RSC-001** 改任务路径、快照解析、实际 SHA-256 校验、原子物化、正式渲染和发布证明调用。补同次输入一致、历史、资源缺失/篡改、任务副本重用、并发写入、规则显式重绑与 direct/翻译/draft 授权回归。运行新增资源测试和受影响的任务渲染、发布测试。
3. **TPL-QA-001** 实现关系检查和符合性报告，在实际输出 DOCX 计算。运行 `python -m unittest tests.test_template_conformance tests.test_template_package_contract`，覆盖删除媒体、关系文件、引用及改坏目标、替换媒体、单侧 override、多个 Section 与 no_template。
4. **TPL-VAL-001** 联合预检接入创建、替换、两个 draft 入口、publish、bootstrap。覆盖正常包、非法 DOCX/YAML、样式类型、损坏媒体、发布前重验及无写入断言。运行联合预检、`tests.test_template_seed_history` 和受影响管理端用例。
5. **TPL-CFG-001** 以 `tests.test_template_config_consumption` 验证字段覆盖和 OOXML 单字段变异。优先复用 `tests.test_document_ir_word_renderer_layout` 的有效覆盖，补缺少的触发条件、Word 样式和实物检查。
6. **TPL-QA-002** 集成证据构建、阻断、持久化读取、事件安全摘要及现有 Datasheet 报告。运行新增符合性测试和受影响证据/恢复/质量度量用例。至少用一个损坏实物证明质量门阻断，用旧证据证明兼容。
7. **TPL-GOV-001** 统一当前内置 seed 入口，加 manifest 旁注、维护文档和四个 release check 项。运行 `python -m unittest tests.test_template_layout_config_schema tests.test_template_seed_history tests.test_document_ir_word_renderer_layout tests.test_template_package_contract tests.test_template_conformance tests.test_template_config_consumption` 及 `python scripts/ops/check_release.py`。复用输入相同的成功检查。验证 OpenAPI 和三份发布资源的哈希。

## PR 与复核

按用户指定的顺序交付。建议依赖链依次为 BASE/RSC、QA-001、VAL、CFG、QA-002/GOV，前一组通过后再进行后一组。每组记录变更摘要、精确测试命令、通过与失败结果及适用的历史兼容边界。各组是可复核的差异边界，提交和外部 PR 操作按项目授权执行。

实施和复核时按阶段直接读取 `.trellis/spec/backend/word-generation-rules.md` 的 PAGE-001/002、FIELD-003、STYLE-002/003、QUALITY-001 和 RND-503 资源身份及历史恢复条款。

Trellis implement/check 复核持久化资源、并发写入和发布门禁。Spec 更新仅覆盖本次触及的模板版本、资源及证据合同。若验证发现正常 DOCX 有可见变化或历史状态变化，保留基线证据并修复到原合同；按对应差异边界回退实施，保持任务原记录和资源文件。

已确认本地 LibreOffice 26.2.4.2 可调用。用隔离用户配置检查真实默认模板生成产物打开，记录该打开证据的边界。真实验证任务、Word preview 和 Golden Sample preflight 依赖可访问的运行环境及其既有授权。按取得的证据分别报告。原工作树的暂存区、未提交文件和本地 main 指针保留。
