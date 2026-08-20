# MinerU 空表占位符误判根因

## 线上证据

- 任务：`docjob_cfcdfa737312`
- 发布版本：`9231fd6`
- 失败阶段：`ir_converting`，进度 `40`
- 错误：`document_ir_failed: MinerU→DocumentIR 内容完整性校验失败：source_ir_integrity:payload_missing:table`
- MinerU 提交、callback、结果 ZIP 下载均成功；失败发生在模板与 renderer 介入之前。
- 任务绑定的模板为 `default@4` draft，说明用户草稿已保存并进入资源快照，但不是本次失败原因。

## 真实 payload 形状

失败 ZIP 的 content list 有 421 个 block、20 个 table。唯一无 HTML table 是第 167 个 block：

```json
{
  "type": "table",
  "content": {
    "image_source": {"path": "images/"},
    "table_caption": [],
    "table_footnote": [],
    "html": "",
    "table_type": "simple_table",
    "table_nest_level": 1
  },
  "page_idx": 11
}
```

它紧随 `page_idx=10` 的真实 HTML table，`images/ + empty html/caption/footnote` 是既有规则认可的续表空占位符。

## 因果链

1. `app/services/document_ir/layout_signals.py::_is_mineru_empty_table_placeholder` 调用共享 `is_empty_table_placeholder()`。
2. 调用方把 `("text", "content", ...)` 交给 `collect_text_from_fields()`；命中整个 `content` 容器后，`coerce_text_list()` 递归遍历未声明语义的字典值。
3. `content.table_type="simple_table"` 因而变成 `text_candidates=["simple_table"]`。
4. `app/conversion/docx_rules/mineru_content.py::is_empty_table_placeholder` 在 `text_candidates` 非空时返回 `False`。
5. 占位符未被 `merge_table_placeholder_continuations()` 合并，进入 DocumentIR 后成为 `html=None` 的 table。
6. `app/services/document_ir/integrity.py::build_source_integrity` 正确产生 `source_ir_integrity:payload_missing:table` 并失败关闭。

诊断性地只把该 block 标为 `table_placeholder` 后，同一结果包可以完成 DocumentIR 转换；因此完整性门禁暴露了上游分类缺陷，不是门禁误报。

## 为什么既有检查未发现

- 既有 `test_convert_zip_merges_real_mineru_empty_table_continuations` 覆盖了顶层 `image_source/html`，没有覆盖 MinerU v2 的真实 `content` 嵌套和 `table_type` 元数据。
- 旧 runtime 的 `parse_visual_block()` 不把整个 `content` 容器作为 table 文本候选，正式 DocumentIR adapter 与旧共享规则的调用参数出现了未被测试捕获的不对称。
- 新完整性门禁在 commit `13111fcb` 中加入，正确地把之前可能静默产生的空 table 变成显式失败；发布门禁的合成 fixture 没有包含该真实 v2 形状。

## 防复发结论

- 容器字段只表示结构，不能因为递归遍历到枚举、类型或路径元数据就认定存在正文。
- MinerU 输入适配测试必须使用脱敏后的真实嵌套形状，而不是把叶子字段提升到顶层的简化形状。
- 正例必须证明占位符被归一化；负例必须证明真实 HTML、题注、脚注或明确正文不会被静默删除。
- source→IR 完整性门禁继续 fail-closed；不得用放宽 blocker 掩盖分类错误。

## Break-loop 复盘

### 1. 根因分类

- **主类别：D — 测试覆盖缺口。** 合成用例把 v2 叶字段提升到顶层，没有保持线上 `content` 嵌套拓扑，因此没有执行到结构枚举被递归收集的路径。
- **次类别：E — 隐式假设。** 调用方假设 `content` 容器内的所有非路径字符串都是正文，但 MinerU v2 同时在该容器保存 `table_type` 等 schema 元数据。

### 2. 为什么发布前未拦截

- 占位符合并旧测试本身通过，release check 也真实执行了该模块；缺陷不是测试未运行，而是 fixture shape 与生产输入不同。
- commit `13111fcb` 加入的完整性门禁没有制造数据缺失，只把之前可能静默生成的空 table 变成可见失败，因此不能通过回退门禁解决。
- 本次没有经历多轮错误修复；诊断阶段用同一结果包强制标记占位符后转换成功，直接区分了“分类错误”和“完整性规则错误”。

### 3. 预防机制

| 优先级 | 机制 | 具体动作 | 状态 |
|---|---|---|---|
| P0 | 正式链路测试 | 保留 nested v2 `content.image_source/html/table_type/table_nest_level` 正例 | 已完成 |
| P0 | 内容保真负例 | 覆盖明确 text、description、题注、脚注、真实 HTML 和孤立空 table | 已完成 |
| P0 | 运行时门禁 | 保持 `payload_missing:table` fail-closed | 已完成 |
| P1 | 代码规范 | 在 `INPUT-005` 固化结构元数据与语义叶字段边界 | 已完成 |
| P1 | 真实输入证据 | 当前修复对旧线上 ZIP 做临时 converter 回归 | 已完成 |
| P1 | 线上任务证据 | 部署新版本后 retry/clone | 待部署阶段 |

### 4. 系统性扩展

- 已检索正式代码中所有 `collect_text_from_fields()` 调用；修复后没有其他调用把整个 `content` 容器当正文候选。
- 全局文本递归工具仍服务于明确需要拍平富文本的入口，不应为 table 特例增加元数据黑名单。
- 未发现需要建立通用 MinerU schema 框架的证据；当前单一正式 adapter + 精确叶字段合同足够，避免引入第二 parser。

### 5. 知识沉淀

- `.trellis/spec/backend/word-generation-rules.md` 已新增 `INPUT-005` 和回归矩阵记录。
- `tests/test_document_ir_mineru_converter_layout.py` 已加入正式 converter 正反例。
- 旧线上 ZIP（SHA-256 `f60e2002654a873492c38d0c018e595cb44804f037a8adcc64973bea31452419`）已在临时文件中通过当前 converter：420 个归一化 source blocks、19 个 table、38 个图片资产、`blocking_quality_flags=[]`；临时文件已删除。
- 项目不存在 `src/templates/markdown/spec/` 或其他 spec 模板镜像，因此无模板同步目标。
- 规范与代码提交需按项目 Git 规则在用户确认 commit 计划后执行。
