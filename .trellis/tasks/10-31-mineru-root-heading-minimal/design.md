# 技术设计

## 边界与数据流

保持正式链路 `extract_zip → find_content_list → read_json_payload → ArtifactValidator → DocumentIR`。仅在输入选择 owner 和已有显式 heading 的层级解析点适配历史行为；不新增模块、依赖、配置或 runtime 分支。

## 第一批：输入选择

1. 使用当前 content-list 命名识别方式收集候选；空集合沿用 `mineru_content_list_missing / missing_content_list`。
2. 以候选父目录形成结果根集合；多根用 `MinerUPackageError` 显式失败。
3. 在唯一根内，存在 v2 就只考察 v2，否则考察 legacy；被选版本必须恰有一个候选。
4. 新增歧义错误码 `mineru_content_list_ambiguous`，原因分别为 `multiple_result_roots`、`multiple_content_lists`。只传稳定分类，不包含绝对路径或完整候选清单。
5. 后续读取失败沿用当前异常传播及 `MinerUArtifactValidationError` 报告，不尝试另一版本。

该变更不移动安全解压、资源限额或 ArtifactValidator 职责，不改变报告模型、policy 限额或源 JSON；通过现有 `add_package_error` 接入报告。

## 第二批：共享窄规则与接线

- 在 `text_semantics.py` 增加专供源 heading 的窄层级解析，复用现有编号、章节和附录语法，十进制深度上限为 6。
- 既有 `infer_heading_level` 的三级兼容行为保持。不得用旧分支整份模块覆盖 main，也不得改变 main 的公式、显式脚本和普通字面文本处理。
- converter 继续承担源层级字段解析与缺省；只在 `block_type == "heading"` 的现有路径结合可见标题文字应用共享规则。尽量复用当前文字提取结果，避免额外清洗或更改输出文本。
- 非编号 heading 保留已有源层级；其他块的类型、层级、ID、顺序、元数据与源定位不因新规则改变。

## 文件所有权

| 批次 | 产品与直接回归文件 |
| --- | --- |
| A | `app/services/document_ir/mineru_package.py`；`tests/test_mineru_result_root_uniqueness.py` |
| B | `app/conversion/docx_rules/text_semantics.py`；`app/services/document_ir/mineru_converter.py`；`tests/test_document_ir_numbered_heading_levels.py` |

必要合同文档仅在本 worktree 更新 `.trellis/spec/backend/word-generation-rules.md` 的 INPUT-001/TEXT-001 附近；不搬入历史维护 worktree 的文档修改。任务记录限于本任务目录。

## 取舍与风险

- 多根包以前可能被静默选中，本次有意改为明确拒绝；单根 v2/legacy 兼容及坏 v2 不回退继续成立。
- 标题编号优先级只作用于显式 heading。首页身份、目录与 caption 等启发式保持现状，避免改变源 inventory 或内容认证。
- 新回归使用自行构造的最小 ZIP 和真实 converter，不导入历史测试辅助类，不依赖模板渲染、数据库或网络。
- 不触碰持久化格式、请求幂等逻辑、模板种子或发布行为；遇到超出以上边界的实际问题先记录，不顺带扩展。

## 隔离与回退

基线固定为 main `a942bbda`；工作分支 `codex/mineru-root-heading-minimal-20261031`，worktree 位于 `/Users/sc/.codex/worktrees/mineru-root-heading-20261031-xtefthlw/md2word`。两批源码及直接回归内容保持已验证版本，按用户授权分别保存为两个本地提交；共用 Spec 按 INPUT-001/TEXT-001 分批纳入，任务记录随相应快照更新。不执行回退、推送、合并或分支删除。
