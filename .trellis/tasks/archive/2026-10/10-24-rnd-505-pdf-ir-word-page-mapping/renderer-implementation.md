# RND-505 renderer 实施记录

状态：渲染器候选已完成，等待主会话组合验证和独立复核；不代表人工验收或生产启用。所有业务修改仅在 `/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`，未提交、未推送。基线为 G0 当前文件而非 HEAD；逐文件前后 hash 见 `renderer-validation.json`。

## 变更与归属

- `app/services/renderer/block_anchors.py`：新增 `block-anchor-evidence/v1`、同次节点创建/冻结、8MiB/100000 entry 预算和最终包认证。候选名是完整逻辑 anchor digest 的前30位加 `md2w_blk_`。模板原名字/数字ID在清空模板正文前保留为预占，最终包现有名字/ID再合并；冲突只记受控计数，不追认为创建成功。
- `block_evidence.py`：扩展 `WordRenderResult` 的可选 `block_anchor_evidence`、私有 `_anchor_ownership` 与安全计数；collector 在最后保存后同时冻结原 trace/图片 ownership 和新增证明。运行期证明归属为 frozen dataclass/嵌套 tuple，仅由真实创建引用生成，不写 metadata。
- `word_renderer.py`：实际 writer 全部结束后插入非可见 marker，随后仅保存一次并冻结。图片书签精确包围本图 drawing 所属 run；表格优先真实 caption/context，否则首个已有 cell paragraph。不加空段落、run、可见字符或分页属性。
- `evidence.py`：保留同次强 runtime 认证，抽取历史可选 trace 认证入口；主件原 aggregate/公式图片认证先执行。可选 proof 缺失、坏绑定、未知版本、超限或没有同次创建 ownership 仅不采信锚点。安全 `block_anchor_summary` 只投影固定版本和非负计数，完整 proof 不进事件摘要。
- `image_evidence.py`：经主会话明确认可的必要兼容接点。图片结构投影只排除命名精确、唯一数字ID、同段闭合、无内容/额外属性的新增 marker；原图片和题注 marker、run/drawing、尺寸、cell 与内容 hash 认证继续执行。marker 本身不授予内容 owner。
- `tests/test_renderer_block_anchors.py`：12项新合同测试。
- `tests/test_renderer_block_evidence.py`：按真实后代首名投影更新断言，继续检查旧题注 marker 存在；targets 数量、role、`Reason` 和 `word_page=None` 不变。
- `tests/test_formula_rendering.py`：两条负例明确选取报告登记的公式书签，避免误删新增通用书签；原缺失/重复/漏登记数学对象仍必须拒绝。

## 应用接口

`WordRenderResult.block_anchor_evidence` 为可选 `BlockAnchorEvidence`。metadata key 同名；entry 字段为：

```text
{block_id, anchor_ref, bookmark_name,
 start: {part, child_path}, end: {part, child_path},
 target: {part, child_path, role, item_index}}
```

proof 还绑定 `schema_version/input_ir_sha256/plan_sha256/docx_sha256/entries/evidence_sha256`，自身 hash 使用既有 canonical JSON 规则。最终定位必须同 part、start/end 数字ID唯一配对，图片必须在同一真实 paragraph 中且两 marker 间恰为其实际 run。证明不复制正文或 source spans。

```python
validate_block_anchor_evidence(
    value, *, plan: RenderPlan, block_evidence: BlockRenderEvidence,
    word_content: bytes, ownership: _BlockAnchorOwnership | None = None,
) -> BlockAnchorEvidence | None
```

该低层 reader 的前置条件是原主件/内容报告和 trace 已认证。新件的 `build_renderer_evidence(..., render_result=result)` 要求 `_anchor_ownership` 才采信 proof；恢复端只读取原 metadata，绝不从名字/namespace 创建成功证明。

```python
validate_persisted_render_evidence(
    document_ir, word_content, *, render_plan, block_render_evidence,
) -> tuple[RenderPlan, BlockRenderEvidence] | None
```

历史图片 target 位置沿原 RND-503 已认证 marker 的实际容器核对，不伪造 runtime ownership。此函数仅消费可选 trace；缺/坏 trace 返回 None，不能新增历史主件恢复/下载拒绝门。

`build_renderer_evidence` 另接受可选 `render_plan`、`block_render_evidence`、`block_anchor_evidence`，均支持原 dict。它先执行原 aggregate/报告认证，再返回可用的可选 trace/proof；原 hash/公式图片/完整性错误照常传播。应用三恢复入口应保留原 metadata 字节，不能按这里的局部不可用结果删掉/重算原字段。应用侧已有对应接线，整体验证由其实施者和主会话负责。

## 证据与限制

- 六模块回归145项通过，日志 `renderer-tests.log`；之后仅补共享页眉/页脚测试，锚点模块12项通过。两组重叠，唯一当前测试覆盖146项，不把数量相加。
- 覆盖真实最终 ZIP/XML、段落/标题/列表/公式/表/图片 cell、TOC和来源片段 owner、空块、抑制块、共享页眉页脚、模板在target内预占同名、短名冲突、高数字ID、同实例并发、部分插入撤回、错part/旧path/错end/同段另一run/同cell另一paragraph、marker内容/额外属性及原run/尺寸篡改拒绝。
- 移除新增 marker 后，对所有 `word/*.xml` 的 C14N 比较相同；公式和图片报告相同，证明未改变内容/结构。此证据不代替真实 Word 分页/视觉验收。
- 8个触及 Python 文件 AST 解析、精确路径 `git diff --check` 通过。当前环境无 ruff/mypy/pyright；lint/type-check 为 N/A，AST 不冒充类型检查。
- B1 实际兼容源码在 `tests/tmp/rnd505-b1-renderer`，5个关键 renderer 文件 hash 见其中 `source-fingerprints.json`。仅将源码生成常量固定为 `read-only/v1`，保留读取、原证明和报告认证；不是新增用户配置/运行时开关。交叉脚本 `check_compatibility.py` 及 `compatibility-results.json` 已运行。
- 已实证 B0 生成原件；B0 reader 拒绝新增图片段 marker，故 B0 不能直接回退。B1 读取 B0/新产物、保存的原证明和全部旧 aggregate/报告均通过，metadata字节未改，B1 新生成不再写通用 marker/proof。该结果只覆盖 renderer，应用三适配器/manifest完整B1须由主会话最终验证，不宣称代码回退整体已安全。
- 未运行 Word/WPS、部署预览视觉、真实生产大文档容量、InnoDB/FS/S3；生产保持 disabled。component/direct/release/OpenAPI 由主会话统一执行，未由本实现者重复运行。
- 新增/实质触及的注释、docstring、开发者错误和记录均使用中文；保留机器字段、协议名及测试合同值原文。未改批准的 PRD/design/implement 三件套，未触及原根或应用所有权文件。
