# RND-503 现状与证据（2026-10-23）

## 调查边界

仓库 `/Users/sc/PycharmProjects/md2word`，分支 `md2word/RND-502`，HEAD=`1835263621a2a18627a5730e7fd62b6bc7cae8c2`。只读调查业务源码、现有测试和 Git 对象；本轮允许写当前任务规划、父任务子链接及 manifest 的 RND-503 条目。建议分支 `md2word/RND-503` 只记录，不切换。未使用子代理、未 start、未提交或 push。

初始 `git status --short` 为 310 条：302 项已暂存删除、5 项已有修改，以及 `.serena/`、父任务目录、RND-501 目录三项未跟踪目录。父任务目录在工作树存在而索引仍暂存删除；这不是本轮产生的状态。保存了初始 status、暂存补丁、tracked 文件哈希及 manifest/父 task.json 前像于系统临时目录，最终与其比较，不恢复或重新暂存这些既有改动。

## 依赖与历史

- manifest：RND-503 原为 todo，唯一依赖 IR-204 为 done，有 2026-10-20 人工接受实现/风险并授权收尾的记录。
- 本地没有 manifest 所指 `.trellis/tasks/archive/2026-10/10-15-ir-204-caption-reconciler`。通过 `git show 5c5e64e:<该路径>/task.json`、`closeout.md`、`validation.md` 确认归档 completed、人工接受及实际实现提交 **17cde1f2a93fa007add9e8adb885d225594bfdc6**。调查早期发现的 9ea4519 是历史实现版本，不能替代最终接受提交。
- `git merge-base --is-ancestor 17cde1f HEAD` 返回 1，当前树缺 `caption_reconciler.py` 和其新增测试；不能把 manifest done 写成本树已集成。依赖状态门通过，实施基线尚未就绪；本轮不集成任何依赖代码。实施前必须在独立获授权的依赖集成结果上复核本规划，保留当前 TR-406/CON-104/RND-502 合同，不能整文件覆盖 renderer/evidence/execution。
- 已读最终接受版本的 DocumentIR 合同 §13、renderer evidence 及 reconciler。`caption_reconciliation` 是可选源证据，含 status、bindings/candidates、source locator、donor/target、evidence_only；独立段落的 evidence-only **不得复制或搬入**图片 captions。`caption_binding_uncertain` 是普通 QA flag，不能自动升级成已绑定/已批准。
- 父任务存在，复用 `10-12-datasheet-docx-delivery-quality`。创建前遍历本地任务记录，未发现 RND-503 slug；用 create --parent --no-start 创建唯一子任务。
- RND-501 仍 planning，其修订3集成设计将修改相同 renderer/evidence/execution 路径，并依赖尚未合入本树的输入来源模型；RND-503 不实施或依赖 RND-501 的未来接口。开始实现前重新核对共同文件所有权与新基线。

## 已读取的真源

已读取根 AGENTS、RTK、workflow、backend/frontend/guides index、backend 目录/错误/质量/Word 规则、数据库现行结果身份合同、跨层 guide、父任务三件套、RND-501 设计及 RND-503 专用提示词。用户指定的 11 份产品、冻结决策、总计划、backlog、执行指南、manifest、ADR、IR 合同、DOCX 设计、质量发布设计和验收策略均已打开，不按标题推断。

优先级裁决：目标 PRD FR-008、DOCX 设计 §7 和本次明确要求选用无边框图片布局表格。当前 Word Spec COL-003、冲突矩阵、legacy 附录仍规定制表位/禁止恢复图片布局表格，属于被当前任务明确替代的旧图片实现约定；实施时只修订图片例外，COL-002 普通正文原生双栏保持。该裁决不改变已冻结产品或 ADR，不构成停止条件。实际 Word/预览视觉签字不可由 XML 测试替代。

## 当前主链路及差距

| 定位 | 实际行为 | 与本任务目标的差距 |
|---|---|---|
| `layout_plan.py:37`、`:79`、`:215` | v2 用 bbox/column hint 构建 region，页内按 y/x/order 排序；v1 缺布局顺序回退 | 没有独立的源顺序图片组计划、阈值版本和拒绝 evidence |
| `word_renderer.py:549`、`:657` | 只在纯图片 two_col region 对左右序列 zip；只要求纵向有交集；有任一多 annotation 就拒绝图片行 | 非严格行判定；多 caption/footnote 走原生栏；无法表达一般 N 图组和逐图定位 |
| `image_renderer.py:96` | 一行两图用 25%/75% center tab；后续共用一条 caption 段落，每图只取 annotations[0] | 没有无边框表格、独立单元格 caption/note 容器 |
| `image_renderer.py:23`、`:186` | 单图 add_picture 只指定宽度，比例保持；当前栏/bbox 限宽；正常路径遍历全部 annotation；missing/invalid 只显示首个 fallback | 失败路径会丢其余 caption/note；没有组/单图拒绝证据；没有逐图实际字节/位置映射 |
| `word_renderer.py:131`、`:160` | 禁止图片自动压缩；单次 RenderContext 管理 caption SEQ/REF 及公式来源 | 应继续复用；cell 不能伪装成有 sections 的 Document，必须显式传 root context/有效 cell 宽度 |
| `evidence.py:49`、`:75`、`:104` | 图片总数对账；IR table 数与 DOCX 全部 w:tbl 数严格相等 | 插入布局表格会误阻断；仅总数也不能证明图/注绑定 |
| `docx_quality.py:129` | 任意 table_count>0 即认为有可编辑内容 | 纯图片布局表格不能冒充原生数据表，掩盖 image_only_suspected |
| `execution.py:3131`、`:3176`、`:3260`、`:3310`、`:3409` | 同次 result 含 bytes/formula_report；检查后登记 candidate，receipt 选唯一身份；三种恢复入口验证新公式报告 | 新图片报告应接同一验证/恢复边界；不能改变 first-valid、generation、最终 IR、历史指针或锁内 I/O 约束 |
| `formal_mineru_conversion.py:213`、`:358` | 本地适配与正式 Worker 共用 renderer/evidence | 只加必要报告参数，不另建本地分组算法 |

API：router 现有文件 quality evidence 是白名单投影（`router.py:826`），无需新增图片端点、前端页面或 generated types。DB 使用既有 file/sqlite/MySQL payload 和状态列，无图片组数据库实体/DDL。配置沿用固化模板和符号资源；不新增开关/环境变量/依赖。脚本已经复用正式 adapter，不迁移 legacy runtime。

## 本轮实际验证

### 现有定向基线

2026-10-23，用 `.venv/bin/python -B -m unittest` 运行以下现有测试，**9 tests / OK，0.098s**：

- renderer：`test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order`、`test_render_to_bytes_keeps_multi_annotation_images_in_native_columns`、`test_render_to_bytes_uses_bbox_width_for_images_and_annotations`、`test_render_to_bytes_uses_native_columns_for_v2_region`、`test_layout_merges_single_side_tail_before_paired_images_into_one_column_flow`、`test_layout_keeps_text_after_image_only_region_outside_image_flow`、`test_render_to_bytes_links_unique_caption_references_with_native_fields`。
- converter：`test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout`、`test_convert_zip_reassociates_only_strict_numbered_image_groups`。

这些通过证明当前制表位/原生栏基线，**不证明目标布局表格已实现**。未编写新的业务测试。

### 内存反例探针

使用现有模型、真实 renderer、1×1 合成 PNG 和 python-docx，在 stdin 执行，无业务文件落盘：页 400×600，left bbox=(10,80,170,180)，right=(220,125,380,140)，分别标 left/right。实际 region=two_col、pairs=1、table_count=0、tabs_count=2、inline_shapes=2、blocking_flags=[]。高度比仅 0.15，却被当成一行图片；本规划严格阈值应拒绝。

将上述 DOCX 在内存追加一个 1×2 原生表格，原图片保持不变，再执行 build_renderer_evidence，得到 `ir_docx_integrity:table_count_mismatch`，证明新增布局表格需要正向分类验证，不能直接豁免所有表格。

将单图增加 `footnotes=['Synthetic footnote']`、loader 返回 None，实际输出不含该 footnote；失败路径只保留第一个 fallback。需在当前图片 writer 范围内保护所有注释，并保持缺图最终完整性失败。

## 样本授权与证据分层

当前 checkout 的 component manifest 仅有最小 OPA228 smoke，不含目标图对。Git 对象 `180c90a` 已接受 IR-207 manifest 的 `zk7044-caption-pair` 为 source_derived_deidentified，authorization=deidentified_approved，原图像素已换 neutral PNG；只授权去标识结构，不授权原文/原 PDF 再分发。其源图5/6同属首 chart 的单串边界不可靠，IR-204 最终验证明确保留 uncertainty；本任务应顺序单图并保留原题注，不能预修 fixture 后宣称已正确重绑。

图5/6、图24/25的明确独立 caption 分组可用 IR-204 已接受合成正式 ZIP 回归覆盖；附加横竖不同像素比例的中性 PNG 验证宽高比。结构回归与实际 ZK7044 Word 视觉分别记账。既有样本可按授权从 Git 对象复用到受控测试目录，不把引入整个 IR-207/TAB 功能当成本任务前置或交付物。

结论：有明确 renderer、完整性和失败注释保真差距，不能建议 skipped_existing。依赖未集成与当前真 Word/预览视觉未验证须显式保留，不因此重复实现 IR-204 或增加 PreviewProvider。

## 独立规划审查补充

2026-10-23，用户要求全新architect独立审查。`/root/rnd503_architect_review`以fork_turns=none审阅v1，确认两项P2：新报告缺生成时非IR输入绑定、回滚将开发基线与可部署兼容构建混用。主会话实际合成探针核实同一IR在两套模板/格式规则下输出不同尺寸和caption；旧checker误计布局表的既有探针在同HEAD下复用。三件套已修订v2，审计/复验状态见[planning-review.md](../planning-review.md)。这不代表新报告或B1已实现。

同时核实IR-204新增metadata键缺省None与旧metadata.get缺键相等，不把固定新增键单独计为确认缺陷；非空验证/回执与旧reader忽略的形态是集成验收输入，当前没有对应实际生产记录。当前HEAD、业务/测试/脚本/Spec均未改，原9项基线结果可复用，不为文档修订重复跑同一业务测试。
