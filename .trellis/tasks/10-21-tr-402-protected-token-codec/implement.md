# TR-402：实施清单与验证门（2026-10-21 已获实施批准）

## 1. 当前阶段与授权

用户已明确批准本文件与当前 prd.md、design.md，并授权实施。当前任务已在 md2word/TR-402 分支准确 start；实施后 manifest 进入 review，Trellis 保持 in_progress，人工验收前不提交、不 push、不 archive。实际验证与残余风险以 validation.md 为准。

依赖 BAS-001 已核验为 done，归档任务 completed 且有人工验收，工作提交在当前 HEAD 可达。规划时 main 上已有其他任务和文档 dirty；本轮获批后创建 md2word/TR-402，保留原有改动。不得 pull、stash 或清理他人改动。

## 2. 有序实施清单

1. [x] **实施前复核**：读取最新三份规划、根规则、backend Spec、manifest 和调查证据；重新核验 BAS-001、当前分支、已有 dirty 及是否已有等价 Codec。确认没有与其他任务重叠的写所有权。若能力已完整存在，则转验证收口并等待人工决定 skipped_existing，不重复实现。
2. [x] **评审与状态门**：确认用户批准的是当前版本规划；仅在后续获批会话对准确子任务执行 task.py start，再仅更新 TR-402 为 in_progress；不启动父任务或相邻任务。新 session 无指针时用准确路径，不猜测活动任务。
3. [x] **模型与首个契约测试**：新增同模块 frozen/slots 分类、出现记录、批次 envelope 和非正文异常；复用 TranslationTextItem，不修改 models.py。先写最小 roundtrip/碰撞行为测试，确认针对缺失能力失败，再实现。
4. [x] **检测与编码**：按 design.md 的静态分类、优先级、最长匹配、非重叠跨度实现；加入自然语言反例。实现完整批次命名空间扫描、每次出现独立编号、源文占位字面量保护和一次切片拼接；不使用随机/时间/外部状态。
5. [x] **整批验证和解码**：验证 item 序列、所属 item、次数、未知/篡改；异常不部分返回；验证后一次替换，防止原文恢复值被递归改写；固定错误分类优先级，确保异常不含源文本。
6. [x] **完成定向测试**：补齐 AC1–AC9 的正反例和 fake Provider 纯离线 seam；复用 OPA228 最小 fixture 经正式 converter/extractor 输入，不改业务抽取、Provider 或 Worker。
7. [x] **文档和 Spec**：更新 docs/design/translation-design.md 的 Codec 合同/当前阶段说明，新增 backend protected-token-codec.md 并加入 index；描述新模块尚未接生产，TR-403 才接入。按 touched-scope 检查中文 docstring、错误文本、注释，仅解释非显然规则。
8. [x] **稳定候选集中验证**：检查最终 diff 和唯一 owner；执行下列最小门禁，分类所有失败。不要在每次文件编辑后反复跑全量测试；相关输入未变化的成功基线证据可复用。
9. [x] **独立合同复核**：新增内部调用合同承载字节保真和确定性完整性保证，候选实现需要独立只读 reviewer，聚焦碰撞、重叠、逐 item 次数、恢复递归、纯函数与敏感信息；没有候选前不以独立代码审查代替规划。按 AGENTS/编排 skill 生成有效审计证据；如无法获取独立复核，明确报告缺口，不宣称自审等价。
10. [x] **人工验收前收口**：逐项映射 AC 证据，task.py validate、文档/JSONL 路径与 diff 检查；清理本任务临时文件/进程；只将 TR-402 manifest 改为 review，Trellis 仍 in_progress。展示准确 commit plan 后停止，人工验收前不得 done/skipped_existing、archive、commit 或 push。

## 3. 计划修改文件与写边界

| 路径 | 实施期变更 |
|---|---|
| app/domains/translation/protected_tokens.py | 新增纯 Codec、局部不可变模型和错误；唯一业务 owner。 |
| tests/test_protected_tokens.py | 新增纯函数、fake seam 和公开最小 fixture 定向契约测试。 |
| docs/design/translation-design.md | 同步实际 Codec 语法、范围、错误和未接生产的说明，保留其余目标设计。 |
| .trellis/spec/backend/protected-token-codec.md | 固化输入输出、规则顺序、碰撞/计数/恢复和隐私合同。 |
| .trellis/spec/backend/index.md | 新 Spec 入口。 |
| 当前子任务下文档/context/验证记录 | 按实际结果更新，不改其他任务。 |
| docs/implementation/codex-task-manifest.yaml | 仅 TR-402 状态、路径和本任务证据。 |

models.py 是已调查的只读依赖，现有 id/text 足够；不为占位映射扩展 Provider DTO。明确不修改 document_ir_translator.py、execution.py、legacy translation_runtime.py、Provider、Prompt、Profile、API/OpenAPI、DB/schema/migrations、前端、发布或 release runner。若实现确需突破写边界，先停止并重新评审，不借“顺手接线”实施 TR-403。

## 4. 验收与定向测试矩阵

| AC | 最小可靠证据（tests.test_protected_tokens） |
|---|---|
| AC1–2 | 各分类表驱动正例，包含温度、科学计数、正负范围、单位、西里尔单位、地址位字段、信号、型号/封装/标准/缩写、URL/邮箱/版本、定界公式及赋值；断言实际原始片段、分类及非交叠覆盖，不只比较 mock 值。 |
| AC3 | 跨 item 相同技术值、同 item 重复值；源文本含 PH 和新家族字面量、残缺候选前缀、保留语法大小写/空白变体；公式/URL 内嵌字面量；连锁恢复值；1000+ Token；每次出现和全批次占位唯一。 |
| AC4 | 每类数据全量往返；空 batch/空 item/无 Token；CRLF/NBSP/组合字符/µ/μ/Unicode 负号等精确字符串及 UTF-8 字节对比。 |
| AC5 | 删除/重复/未知编号/改变 namespace、大小写、括号、插空格/零宽字符；合法 Token 换到别的 item；缺失/额外/重复/乱序返回 ID；输入重复/空 ID；无 Token 批次被注入未知占位符；任一 item 异常整批抛出，原输入/ledger 不变且错误不含原文。 |
| AC6–7 | fake Provider 只翻译普通语言或在同 item 内移动完整 Token 后仍还原；Typical/Reserved/High/Low/NOTE/普通中俄文不被吞掉；含数量的句子只替换技术跨度；小写 a/in/at 不当作单位。 |
| AC8 | 既有 OPA228 fixture 临时 zip → MinerUToDocumentIRService.convert_zip → DocumentIRTranslationService.extract_translation_items → Codec roundtrip；不调用 translate，不连接真实 Provider；断言 IR 未变并命中 OPA228、3 nV/sqrt(Hz)、10 V/us。 |
| AC9 | 重复/交错调用不互相污染、映射/输入不被修改、同输入 ledger 完全相同；fake seam 成功和失败均无落盘回填；保留已有正式/legacy/direct 回归。 |
| AC10 | 三份文档、Spec、context 与实际代码一致；最终 diff 不越界，无真实外部调用或产品规则削弱。 |

缺失/额外 ID 和“某个响应失败不返回解码结果”只验证 Codec envelope；不会在这里实现 TR-403 的 JSON validator 或 TR-406 的真实批次状态机。

## 5. 验证命令与门禁范围

### 已有基线（本规划轮实际执行）

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_ir_translation \
  tests.test_translation_runtime_characterization
~~~

2026-10-21：21 tests / OK。只证明当前结构/批次/legacy 合同基线，两个只读反例仍复现缺口；不能作为未来 Codec 的通过证据。

### 实施稳定候选的必需定向门

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_protected_tokens
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_ir_translation \
  tests.test_translation_runtime_characterization \
  tests.test_document_job_modes
git diff --check
python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-402-protected-token-codec
~~~

新测试是首要行为证据；已有三模块用于确认没有接线、legacy 兼容或 direct 资源合同回归。实施前先确认 targets 仍存在，已有相关输入完全没变的成功证据可复用，不机械重复。

未来实施应使用项目 .venv 和 unittest 现有风格，无新的 pytest/property-test/lint/type-check 依赖。需要语法检查时可在内存 compile 新模块；没有仓库规定的统一 Python lint/type 门，不杜撰通过结果。

### 不适用门与条件升级

- 当前规划：不跑 release/full suite、模型、线上、DB、Word 或浏览器；只跑只读调查与任务/context/文档检查。
- 纯 Codec 实施：check_release.py 不作为本子任务必需门，原因是没有 OpenAPI/DB/状态/前端或生产接线变化；以新算法测试、既有 translation/legacy/direct 定向回归、Spec/独立合同复核替代。不能声称已通过 release。
- 已有最小 fixture 的 Codec roundtrip 作为与真实 MinerU 文本格式有关的样本证据；不跑 Renderer/全 component/Golden 来重复证明未修改的 DOCX 路径。P0 direct 定向单测保护边界，完整 P0 正式证据属于后续阶段集成。
- 不为本子任务新增四方向样本 matrix；Codec 语言无关，以中英俄混合合成向量覆盖，不代替 TR-407 四方向实译验收。当前 runner 没有已确认的 translation-core 样本集，不能照目标文档直接假定可运行。
- 用户在实施授权中明确要求 P1 preflight，因此本轮实际执行并单独报告；它不调用模型但需要 runtime/认证，预检成功也不等同 Token 或翻译正确性通过。环境阻断不通过补填凭据、启动服务或削弱检查来掩盖。
- 如果候选不得不改变生产调用、持久化、状态、API 或权限，超出已批准范围，先重新规划并选择对应 integration/OpenAPI/迁移门；不得通过放松断言或直接扩大测试来掩盖扩围。

## 6. 文档、Spec、回滚与完成定义

- 文档更新须区分现有能力、目标能力与本任务交付，不能把“纯模块已实现”写成“生产 100% 已保证”。
- 注释/docstring/开发者错误文本默认中文；常量、机器码、模式和现有测试契约字面值保持协议语言。
- 规划回滚点：仅还原本任务 manifest stanza、父任务新增 child 链接及本任务文档，不覆盖已有 dirty。
- 实施回滚点：未接生产的新模块/测试及其 Spec 增量可独立撤销；无迁移/backfill/数据回滚；禁止修改已发布文件、资源快照或历史审计。
- 完成定义：AC1–AC10 逐项有证据；范围内检查通过或准确记录环境阻断；无未解释的新质量问题；独立合同复核已完成或明确缺口；Spec 同步；干净的本任务交付清单；manifest=review、Trellis=in_progress；等待人工验收和提交授权。
- 停止条件沿用 prd.md §7；本轮最终停在实现 review 与 commit plan，等待人工验收和提交授权。
