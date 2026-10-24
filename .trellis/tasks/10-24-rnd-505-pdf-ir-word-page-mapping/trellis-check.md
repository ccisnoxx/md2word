# RND-505 Trellis 检查与局部修复

2026-10-24。检查者：`rnd505_trellis_check`。唯一写入仓库为批准的隔离 worktree；未提交、暂存、推送、归档或记账，未修改原根目录。结论供主会话合并最终验证和人工 review 使用，不代替人工验收。

## Findings (fixed)

- **P2：深层坏可选证明越过非阻断边界**
  - File：`app/services/renderer/block_anchors.py:313`。
  - Issue：`validate_block_anchor_evidence` 的预算 JSON 编码可因深层嵌套抛 `RecursionError`，原异常列表没有捕获。主会话/独立风险复核提供反例后，本检查者独立复现：合法 JSON 中 `extra` 含 990 层数组，经 5 层调用进入验证时异常逃出。该证明本应局部不可用；逃出后可使主件恢复/预览在 uploading 阶段变为 oss_failed。
  - Fix：只在原可选证明验证边界增加 `RecursionError` → `None`。原主件、原 aggregate、公式/图片报告、hash、存储及权限异常仍沿原路径处理，没有扩大 catch 到外层业务流程。
  - Tests：`tests/test_renderer_block_anchors.py:307` 新增真实 renderer/plan/trace 的深层坏证明负例；原内容认证通过、trace 保持 complete、可选证明省略。`tests/test_document_job_result_persistence.py:1152` 新增 file/SQLite 的实际 IR 和 generated_word 登记负例：只在内存记录中替入坏证明，再执行完整 `_validate_render_result_file` 和 preview `_mapping_source`，确认原 aggregate/公式图片认证仍执行，安全 warning 出现，plan/trace 保留、anchors=None，metadata 不被回写。测试刻意不通过无关的 metadata 编码器序列化深层值。

## Findings (not fixed)

- 文档同步点（已交主会话处理）：`docs/design/docx-rendering-template-design.md:260` 仍以将来式说通用 bookmark/映射 Artifact 留给 RND-505，与同文件新增实现段落冲突。建议表述为 RND-501 的历史边界并引用当前 RND-505 合同。遵守本次文档写入分工，本检查者未重复修改该文件。
- 本轮未发现其他已确证的新增业务阻断。真实 Word/WPS、Golden、部署预览引擎/字体/批准隔离、真实 InnoDB/部署 FS-S3、真实大文档容量仍未验；这是批准计划保留的环境证据门，不将离线通过升级为生产就绪。
- 补丁后 B1 快照重建、完整三恢复入口及主会话统一定向/发布证据由主会话收口；本记录不把补丁前日志冒称补丁后运行。G0 原有 5 次失败仍按已记录的逐 selector/同签名归因保留，不改断言以求全绿。

## 审查范围与结论依据

已读取批准 v2 三件套、check.jsonl 的全部指向、backend 索引/质量/数据库/日志/错误/Word 专项合同、当前映射合同，以及 G0 研究、集成、独立审查和指纹证据。包探测结果是单仓库，受影响层为 backend。

对 `HEAD 8fa11d97` 到工作树的组合范围复核，并将 `tests/tmp/rnd505-g0-b0` 与当前代码比较以区分新增行为：已有 app 路径中只有 execution、preview、block_evidence、evidence、image_evidence、word_renderer 六个文件在 G0 后继续改变；新增 page_mapping/block_anchors 也逐段审查。其余 G0 融合复用已有独立审查、同签名失败归因和内容守恒指纹证据，没有再覆盖整份历史模块。

- **内容与归属**：marker 在最终 save/freeze 前由真实 LocalTarget 创建；原 RND-501 v1 的首名/targets 数量和 role/封闭 Reason/word_page=None 保持。独立证明不由旧首名或模板同名生成。图片兼容投影只排除精确命名、唯一配对、无内容/额外属性的新 marker；原专用图片锚点、run/drawing、各 cell/注释、资产/尺寸认证继续执行。新件仍强制 runtime ownership；持久读者不伪造同次创建事实。
- **身份与算法**：页映射绑定选定 receipt、原 IR/plan/DOCX、当前 run/attempt/profile 及已登记 PDF。正文顺序取最终 document.xml 的真实目标；typed spans、legacy layout、未知来源保持不同档位。稀疏源页按 rank、S≤1 输出比例、缺来源最近 owner 平局选前、比例平局低页均与合同一致；多页全部 low，range=null，无目标保留 entry，无 trace/超限使用小型对象。
- **失败与生命周期**：原 IR 跨 scope 不读字节，缺失/过期只降低映射；未知 I/O、字节/hash 不符继续失败。映射计算位于原登记 CAS 后、manifest finish 前且在锁外；alias/历史 key 重放复用原 manifest。未增加状态账本、DB 字段、HTTP 路由、配置或质量/发布贡献。
- **隐私与兼容**：完整 proof/mapping 只进入原受权 Artifact；renderer/失败事件和 files 摘要沿白名单，执行事件显式排除新增私有键。原 manifest/hash/权限/当前引用认证保持；内层 reader 单独检查 schema/hash/binding/页范围/计数和预算，局部不可用不写回历史对象。B1 必须保留 reader、原 metadata 和内容认证，停止新 marker/mapping 生成；不把 G0/B0 自然当作安全回退版本。
- **Spec/模板触点**：新增 page-mapping Spec 和详细合同、backend 索引、Word 规则、render-plan/preview 合同均有当前 owner/触发入口。未修改平台配置或模板 seed，不存在本任务需同步的平台生成模板、DDL 或前端 build。

## Verification

- **Lint：N/A / 未运行**。仓库只有 requirements.txt，无 pyproject/setup.cfg/tox/ruff/flake8 配置；当前解释器确认 ruff、flake8 均未安装。未安装依赖，AST 检查不冒充 lint。
- **TypeCheck：N/A / 未运行**。当前解释器确认 mypy、pyright 未安装，仓库无对应配置；不以 AST 解析冒充类型检查。
- **Tests：局部修复后通过**。
  - `.venv/bin/python -m unittest tests.test_renderer_block_anchors tests.test_document_job_result_persistence.DocumentJobBlockAnchorRecoveryTests.test_deep_optional_proof_stays_local_in_recovery_and_preview_source`：14 tests，2.049s，OK。包含 anchor 全模块和新增 file/SQLite 应用负例；与已有 renderer 结果有重叠，不累加为唯一测试总数。
  - 最初新增两条 selector 单独执行：2 tests，0.573s，OK；后续应用负例加强后以上述 14 项为本检查者最终结果。
- **Static：通过**。36 个触及/新增 Python 文件可由 AST 解析；`git diff --check` 通过；最终检查工作树未发现本检查者范围外的写入。只新增中文测试说明/注释，业务异常修复无需新增开发者消息。
- **复用证据，非本检查者重新执行**：G0 403 个条目中 5 次既有同签名 failure；renderer 145 项及末次 12 项重叠后的 146 唯一覆盖；mapping/application 103 项及末次 19 项通过；已有 release 203 项、component 1/1、direct 5/5。主会话另运行统一 339 项（5 次已知 failure）并收口补丁后的受影响检查。各日志与最终代码指纹由主会话更新，不能混淆运行先后。
- **未运行/N-A**：本子代理没有重复重全套 release/component/direct、启动 API/Worker/数据库/浏览器或安装 Office；前端未改，前端 build/Vitest/Playwright 不适用。真实环境门如上保持未验，生产预览继续 disabled。

当前已停止 app/tests 编辑；主会话可据本补丁固定 B1 和最终源码指纹。
