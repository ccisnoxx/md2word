# TR-402：技术设计（2026-10-21 已获实施批准）

## 1. 规划时实现与差距

以下为规划调查基线。正式链路为 MinerU → DocumentIR → DocumentIRTranslationService/Worker 批次 → Provider → ID 验证 → replacements → 目标 IR → renderer。调查证据和源码锚点见 [current-state.md](research/current-state.md)；本任务实施结果以 validation.md 和 backend Codec Spec 为准。

- app/domains/translation/protected_tokens.py 尚不存在。
- models.py 的 TranslationTextItem 是 frozen/slots 的 id/text 对；现有 Request/Result、Profile、Prompt、Term 快照均已有明确职责，不应塞入原文映射。
- document_ir_translator.py:519 的 validate_result 仅比较 ID 序列；数字从 25°C 改为 99°C 仍被接受。text/list/html 抽取含 strip，不能把现有整条抽取链路的空白行为误写成 Codec 的无损合同。
- legacy translation_runtime.py:323 已有 protect_text，但编号每个 item 重置为 PH_001，无碰撞检查；restore_placeholders 逐项 replace；validate_translation_responses 用集合，不能识别重复。旧逻辑有限命中不是可用的正式 Codec。
- execution.py:1198、:1216 为持久化批次调用/校验入口，:1553 起 fan-in；批次另有 generation、lease 和 CAS。本任务不触碰这些边界。

目标设计 docs/design/translation-design.md §7 和 ADR-008 要求代码确定性保护。TR-402 补齐 Codec 原语；生产调用、Prompt 告知、预算与结果校验接线留到 TR-403，不复制翻译服务或另建转换流程。

## 2. 唯一 owner 与内部合同

新增 app/domains/translation/protected_tokens.py，依赖标准库和现有 TranslationTextItem。分类、匹配、批次命名、映射、解码校验由这一文件拥有；不把旧 runtime 导入正式 domain，也不复制旧 runtime 成为新服务。

拟定内部接口：

~~~python
encode(items: tuple[TranslationTextItem, ...]) -> EncodedTokenBatch
decode(items: tuple[TranslationTextItem, ...],
       batch: EncodedTokenBatch) -> tuple[TranslationTextItem, ...]
~~~

可用无状态 ProtectedTokenCodec 命名空间承载这两个操作，或等价模块函数；不得引入实例计数器、可变 registry、抽象 Provider 或配置工厂。

新增局部 frozen/slots 模型：

- ProtectedTokenKind：稳定分类标识；扩展通过代码变更和向量测试，不引入运行时插件。
- ProtectedTokenOccurrence：item_id、kind、start/end（Python 字符偏移）、placeholder、original_text。每次出现各有一个记录；original_text 不进入默认 repr。
- EncodedTokenBatch：原始 item ID 顺序、所选命名空间、编码后的 items、出现记录 tuple。含文本字段避免默认 repr 泄漏；没有 dict 可被外部原地改写的映射。
- ProtectedTokenError(ValueError)：稳定 code 与非正文元数据；错误文本中文，不拼原始值/全文。

不修改 models.py、TranslationTextItem、TranslationProviderRequest/Result、DocumentIR v2 或公开 API。未来调用方可直接使用 batch.items；映射不能附到 Provider 请求中。

## 3. 检测类别、顺序与普通语言边界

在原文上产生候选跨度，不在已经替换的字符串上继续匹配。按以下优先级先选择不重叠候选；同级最长跨度优先、再按原始起点和固定规则序号确定；最后按源顺序输出。多个规则不得重复消费字符。

| 优先级 | 类别 | 明确正例与边界 |
|---|---|---|
| 1 | url/email | https://example.test/a?x=1、tech@example.test；保留内部数字/符号，不吸收句末标点。 |
| 2 | formula | 成对 $...$、$$...$$、\(...\)、\[...\]；有明确语法边界的 LaTeX 与 TA = 25°C、E=mc^2 等技术赋值。 |
| 3 | literal_placeholder | 源文已有 {{PH_001}} 或 {{MD2W_PT_...}} 家族字面量及可识别的残缺前缀/变体，整体保护；位于完整 URL/公式内时由外层整体保护。 |
| 4 | address/bit_field | 0x0028[4:0] 优先整体；独立 0x0028、[4:0]、带明确信号前缀的位段。 |
| 5 | model/standard/version | OPA228、ZK7044、SOIC-8、QFN-32、IEEE 802.3、v1.2.3；带数字的型号与版本优先于裸数字。 |
| 6 | signal/identifier | VCC1_VCO、V_OUT、RESET_N 及有限常见信号；变量限公式、显式下标/信号语法，不匹配任意单词。 |
| 7 | quantity/unit | −40–+85 °C、±0.5%、1.2e−3 A、3 nV/sqrt(Hz)、10 V/us；单位表精确区分大小写；µ、μ、u 和已列明的西里尔单位各自保留。 |
| 8 | number/symbol | 剩余整数、小数、科学计数、公差、范围，以及数字/表达式相关正负号和比较符；不吞掉两侧自然语言。 |
| 9 | technical_literal | 有界技术 allowlist，如 ADC、DAC、PLL、I2C、SPI、UART、USB、JEDEC；不是全部大写词或任意缩写。 |

单位表从上述正例和现有单位规则提炼，明确包括 V/A/Hz/Ω/F/s/°C/% 及常见 SI 前缀、复合写法；独立单位只在整个 item 的非空白内容明确为单位时命中，前后空白仍按源片段保留。俄文单位不本地化；普通俄文参数名不作为单位。

普通词 Typical、Reserved、High、Low、Input、NOTE、中文/俄文自然语言不因字形被保护。普通连接词 a、in、at 不作为单位/变量。裸单词、未闭合数学定界符不允许贪婪吞整句；未闭合公式只按其余确定规则检测，不能声称其已获得完整公式保护。不使用 eval、通用数学求解器或语言识别模型。

## 4. 批次唯一、碰撞消除与编码

1. 按输入顺序接受完整 batch；拒绝空 ID 或重复 ID，空文本/空 batch 合法。不重排 item。
2. 在全部原始文本上选择命名空间：从 n=0 起，找首个没有出现在任一源文本中的保留前缀 {{MD2W_PT_v1_n_。这是实际源文扫描，不依赖“碰撞概率很低”。源文含候选前缀则递增 n。
3. 按 item 顺序和原始位置从 1 连续编号，例如 {{MD2W_PT_v1_0_1}}。数字不限定三位；同一技术值出现两次也有两个不同的 placeholder。
4. 原文中本家族和 legacy 家族的已有占位字面量作为 literal_placeholder 记录（已被完整 URL/公式包住的由外层保护），不能再拆出内部数字。源文扫描和返回值扫描共用同一保留语法识别器：凡 decode 会判为保留/可疑占位语法的源片段，都必须在 encode 时先被代理，包括残缺的 {{MD2W_PT_v1_0_ 前缀、大小写或空白变体；否则源文自身可能在 roundtrip 时被误拒绝。识别器只处理带保留家族标识的括号片段，不把任意花括号、{{NAME}} 或普通词整体吞掉。
5. 依据原始 span 一次性拼接编码文本和不可变 ledger，不 strip、不做 Unicode/换行规范化。

n 的选择和编号完全由有序输入决定；不同批次可以使用相同命名空间，要求仅为批次内唯一。映射只用于该次输入，不能跨 batch/generation 缓存或混用；未来生产接线须用批次上下文管理归属，本任务不创造全局 ID 或 generation 协议。

## 5. 解码、失败和原文恢复

decode 先验证整个返回 tuple，全部通过后再构造解码后的 tuple：

- 返回 ID 序列必须等于 batch 的原始 ID 序列，不能借 dict 静默折叠缺失、额外或重复项。这是 Codec envelope 合同，不替代未来 Provider JSON shape validator。
- 扫描返回文本中的保留占位符家族，逐 item 按出现次数比较：每个预期 placeholder 恰好一次；未知 placeholder、别的 item 的合法 placeholder 均拒绝。空 ledger 也必须检测新注入的保留占位符。
- 修改大小写、空白、括号、编号、命名空间、零宽插入等造成非精确匹配时，至少命中缺失/非法检查，不尝试“修好再还原”。恶意附加未知占位符必须拒绝。
- 源文已有保留占位字面量在编码后由当前 placeholder 代理，因此校验时不应被误当未知；解码结果可合法包含其原字面量。
- 恢复使用对已验证占位符的一次扫描/替换，从 ledger 取原始切片；不能逐值连环 replace 或在恢复后再次扫描 Token 家族，否则会递归改写合法原文。
- 同一 item 中完整占位符移动可接受（翻译语序）；跨 item 移植不允许。Codec 不判断移动后的语义是否仍正确，也不检查未编码数字，后者由 TR-403 完整性验证负责。

内部错误码拟定：protected_token_invalid_input、protected_token_item_mismatch、protected_token_missing、protected_token_duplicate、protected_token_unknown、protected_token_wrong_item、protected_token_malformed。多错误时按固定次序报告：输入/ID → malformed/unknown/wrong_item → missing → duplicate，同类按输入 item 顺序和位置；没有稳定归类的破坏不得静默通过。可只返回首个确定错误，不建立大而全诊断框架。

## 6. 数据流与未来接线位置

本任务的离线验证流：

~~~text
现有 TranslationTextItem tuple
→ encode → batch.items + 内存 ledger
→ fake Provider 仅修改自然语言（不发生外部调用）
→ decode 验证整批并恢复 → 新 TranslationTextItem tuple
~~~

真实最小样本：复用已提交公开/最小化的 OPA228 component fixture，临时 zip 后通过 MinerUToDocumentIRService.convert_zip 和既有 extract_translation_items 获取输入；不自行写第二套 content_list 解析器，不改 extractor。

未来 TR-403 必须同时覆盖 translator.translate 与 execution 的独立 Worker batch 入口；不能只在同步入口接线。需要协同编码后的字符预算、术语匹配顺序、Prompt 的占位语法说明、落盘前 decode、失败映射和 fan-in。此处只记录影响，不执行接线或扩写相邻任务。

## 7. API、DB、状态与兼容影响

| 边界 | TR-402 决策 |
|---|---|
| OpenAPI/前端 | 不变，无路由、DTO、generated types、query key 或动作改动。 |
| DB/迁移 | 不增表列、不 backfill、不序列化 ledger；file/sqlite/MySQL repository 均不变。 |
| 状态机/权限 | 不改执行阶段、下载、审核、发布、owner/admin 或 available actions。 |
| 幂等/并发 | 纯函数重入，无锁、事务、lease 或全局计数；同输入同输出，不等同于 encode(encode(x))=encode(x)。 |
| generation | 无新增 generation；重试/拆分后的映射重建和批次归属由未来调用方负责，禁止复用不匹配 ledger。 |
| 不可变 | 新 ledger 不可原地修改；不覆盖历史 IR/DOCX、Prompt seed、配置快照、PublicationRecord 或审计。 |
| 错误映射 | 仅新增内部异常/码；不接 Worker/HTTP，不改 translation_failed 等已有映射。 |

legacy PH 格式及其测试原封保留，正式链路暂不使用新模块，历史任务不重跑。产品 PRD/ADR 优先于 seed Prompt 的局部指示：现有 en2zh 允许翻译 $PACKAGE$ 中自然词，ru2zh 允许单位本地化，本任务按用户明确要求恢复原字符；因为不接 Provider，不存在需要改变冻结产品规则才能完成的冲突。后续接线必须审查版本化 Prompt，不可原地篡改已绑定快照。

总体实施计划/rollout 提到 TRANSLATION_PROTECTED_TOKENS_ENABLED 是未来生产启用建议，当前没有该配置。本任务不创建 flag、双实现开关或新 snapshot 字段；启用仍属后续集成/灰度。

## 8. 安全、隐私与可观测性

- 仅处理内存字符串，不读取文件/网络/环境；URL/邮箱只是字面量，不访问目标；公式不执行；不向外部发送专有文本。
- 映射含原文，为敏感内存数据；不默认 repr/日志输出，不加入 Provider payload、审计表、错误消息或质量 Artifact。
- 调试证据使用合成向量与既有公开 fixture，不保存客户 PDF、正文快照或新增全文 debug；未来如要导出须沿用 Admin 显式授权和保留期，不能由本任务开启。
- 测试只断言稳定错误码、计数、item ID 和返回/拒绝结果。无新增 metrics、业务事件或日志基础设施。
- 只用受约束规则和标准库；不要为追求所有技术语言覆盖添加大而全的解析器或猜测 fallback。用有限正反例覆盖规则边界；若真实样本暴露新语法，再作为明确增量评审。

## 9. 风险、停止条件与回滚

主要风险是过度保护普通语言、重叠类别漏/错切、源文字面占位符触发递归替换、重复/跨 item 迁移被集合校验掩盖，以及把原语完成误称为生产完整性完成。对应 AC1–AC9 的精确向量和负例直接验证。

通用停止条件以 prd.md §7 为准。若实现必须修改 Prompt/Profile/Worker/DB/权限或改冻结规则，停止扩围，先更新三份规划并重新评审。

本任务尚无生产接线，回滚仅撤销本任务新增模块、测试和对应文档/Spec 增量；不删历史数据、不撤其他任务代码，不降级技术安全合同。未来集成若关闭调用，也不得把失败内容作为已校验译文回填。
