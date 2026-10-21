# ProtectedTokenCodec 内部合同

## 1. 范围与触发

修改 app/domains/translation/protected_tokens.py 或调用其内部接口时适用。该模块是技术 Token 检测、批次占位、验证和恢复的唯一 owner，采用标准库与现有 TranslationTextItem；不依赖 legacy runtime，不维护第二套翻译流水线。

TR-402 只交付纯内存原语；TR-403 的正式接线和恢复后技术 inventory 对账由 [翻译完整性验证与消费合同](translation-integrity-validator.md) 管理。Codec 自身仍无 I/O、预算或持久化职责，不能把纯模块/离线 fake 通过写成生产实译已达标。

## 2. 接口与模型

~~~python
encode(items: tuple[TranslationTextItem, ...]) -> EncodedTokenBatch
decode(
    items: tuple[TranslationTextItem, ...],
    batch: EncodedTokenBatch,
) -> tuple[TranslationTextItem, ...]
~~~

复用 TranslationTextItem(id, text)，不在 TranslationProviderRequest/Result 中添加原文映射。EncodedTokenBatch 字段为 item_ids、namespace（完整保留前缀）、items、occurrences；ProtectedTokenOccurrence 字段为 item_id、kind、start/end、placeholder、original_text。两者为 frozen/slots 且仅用不可变成员；原文、编码文本及原文 ledger 不进入默认 repr。

无配置键、HTTP 入口、数据库表或迁移。不访问环境、文件、网络、随机数或时钟。

## 3. 编码、检测和恢复合同

- 每次出现独立编号，包括同 item/跨 item 重复值；按输入 item 与源位置分配，编号支持超过 999。
- 从 n=0 开始扫描所有源文本，选择未出现的前缀 {{MD2W_PT_v1_n_；例如 {{MD2W_PT_v1_0_1}}。必须实际查源文，不依靠 hash/随机碰撞概率或全局计数。
- 在原文上产生跨度；URL/邮箱、完整公式、源文保留占位字面量优先于地址位字段、型号/标准/版本、信号、数量单位、数字和有界技术缩写。同级按最长、起点和固定规则序号确定；选取不交叠跨度后按源序一次拼接。
- 完整公式限成对数学定界符和可判定的技术赋值；单位包括 m 与常见 SI/已列明西里尔写法，复合支持 /、sqrt()、√、乘号和指数，不执行数学求值或单位转换。
- 普通词 Typical/Reserved/High/Low/NOTE、中俄文自然语言、a/in/at 不因大小写或字形被整体保护。单字母单位只限数值邻接或完整单位单元。
- 源文和 decode 使用一致的保留占位家族识别边界；已有 PH、新家族、残缺前缀及已支持变体必须被代理，避免合法原文在 roundtrip 中自误拒绝。普通 {{NAME}} 不属于保留家族。
- 扫描时先认领完整占位字面量，再识别不重叠的可疑片段，避免普通外括号吞掉生成的完整 Token。残缺保留语法与高优先级 URL/公式仅部分重叠时，继续代理其未被覆盖的片段，不能整段丢弃而遗留裸前缀，也不能拆开完整 URL/公式。
- 不 strip、不规范化 Unicode/换行，不纠正 OCR 或单位；原始切片恢复后字符串与有效 UTF-8 字节完全一致。公式只作文本，URL 只作文本，不执行或访问。
- decode 先验证全部 item 的 ID 顺序、Token 归属及每个 Token 恰好一次，全部通过后才构造结果；同 item 内完整占位符移动允许，跨 item 移植拒绝。
- 只进行一次非递归恢复；恢复出的源文字面占位符是合法内容，不能再次扫描或逐值连环 replace。
- 同一有序输入得到相同结果，调用间无共享状态；确定性重入不等于重复 encode 幂等。ledger 只用于对应批次，不定义跨 batch/generation 持久化协议。

## 4. 验证与错误矩阵

| 条件 | 内部错误 |
|---|---|
| 非法调用输入、空/重复源 ID | protected_token_invalid_input |
| 返回 ID 缺失、额外、重复或乱序 | protected_token_item_mismatch |
| 占位符被删除 | protected_token_missing |
| 同一占位符多次出现 | protected_token_duplicate |
| 合法新格式但 ledger 未登记的占位符 | protected_token_unknown |
| 合法占位符移到其他 item | protected_token_wrong_item |
| 可识别的占位符语法被破坏 | protected_token_malformed；或因不再精确匹配而报 missing |

任一 item 不通过均整批抛出，无部分成功、修复后继续或源文 fallback。错误文本、日志和默认 repr 不能包含原文、映射值或全文。正式调用由 Validator 映射为稳定 translation_integrity_*，保留既有主任务 translation_failed；Codec 不直接决定 HTTP/Worker 状态。

## 5. 正常、缺省与非法场景

- 正常：OPA228、25°C、0x0028[4:0]、VCC1_VCO、公式和 URL 各自保护；fake 响应只翻译普通文字，decode 精确恢复技术原文。
- 缺省：空批次、空文本、无 Token 合法；无 Token 响应中新注入的保留占位语法仍要拒绝。
- 非法：全批 Token 集合相同，但交换两个 item 的 Token；必须按所属关系拒绝，不能仅比较集合。
- 源文已有 {{PH_001}} 或新家族字面量时，encode 后都由新占位符代理，decode 一次还原，绝不能递归替换源文。

## 6. 必要测试与证据边界

tests.test_protected_tokens 覆盖每类命中/重叠、自然语言反例、源文碰撞、1000+ Token、逐 item 计数、篡改、ID 负例、输入/ledger 不变、Unicode/空白字节往返、fake 响应整批失败。

复用现有公开最小 OPA228 fixture，经 MinerUToDocumentIRService.convert_zip 和既有抽取入口构造输入后验证 Codec；不创建另一套解析实现，不调用真实模型。已有 translator、legacy、direct 定向回归保持。

纯函数不要求通过真实模型证明正确性；P1 preflight 的环境失败应如实报告，不能写成 Token 测试失败或整条翻译已通过。预算/Prompt/术语匹配与 Worker 接线由 TR-403 的定向测试覆盖；四方向正式实译与在线/Word 验收另需独立证据。

## 7. 错误与正确做法

错误：对每个 item 重置 PH_001，只比较 set，再对每个值循环 replace；或把含原文 ledger 附加到 Provider payload。

正确：完整批次 encode 一次，保留内存 ledger；获得返回 tuple 后整体验证并一次恢复。

~~~python
batch = encode(source_items)
# 仅将 batch.items 交给调用方的翻译边界，ledger 留在内存。
restored_items = decode(returned_items, batch)
~~~

增加检测类型时在同一模块的静态规则中扩展，补充正例、普通语言反例和重叠测试；不引入动态插件、模型判断或静默兼容路径。
