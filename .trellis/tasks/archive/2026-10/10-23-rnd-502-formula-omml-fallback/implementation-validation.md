# RND-502 v2 实施验证

最新复审与当前源门禁以 post-implementation-review.md 为准（311 定向、202 release，1P1/2P2 均修复并独立复验）。下文原 306 项冻结快照为前一版历史证据，保留不覆盖。

当前结论：当前任务实现及可执行本地门禁完成，manifest 停 review，Trellis 保持 in_progress，等待人工评审；外部/人工门未验证。已审核三件套原字节保留，当前实施授权见 implementation-authorization.md。

## 基线和保护

- 依赖 BAS-001：manifest done、HEAD 归档 completed，工作提交在 c56e128 HEAD 可达；用户已接受其证据与风险。
- 实施分支 md2word/RND-502；基线 c56e12832ff30212cc067d0909430cf5f091f79b。
- 当前子任务准确 start，session 指针是 codex_01a166c3-673e-7191-a780-0a1f04bd0f16；其它任务未 start。
- 原暂存树及 dirty 哈希快照：`/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd502-implementation-7_pvoing`。
- 中途保护检查：原暂存树相同，非本任务已有文件均未改动，45 个 manifest 条目中只有 RND-502 变化；三件套与用户批准 v2 快照完全相同。

## 验证证据分层

- 结果/状态新增 3 个 unittest（含多 subtest）通过：三恢复入口同锚点改值拒绝、四质量状态单调、file/SQLite/fake MySQL 摘要往返、历史明确指针跨代不导入旧摘要；见 `tests/tmp/rnd502/result-targeted.log`。
- 相关执行/持久化/状态/下载/本地工具首轮 81 项：80 通过，1 个旧用例的“一次 ensure”假设因新增 receipt 复检失效；更新为 quality_checking 与 uploading 两次并保留登记先后/主任务成功断言，单项通过。最终合并门禁待更新。
- Translator 负责范围首轮 122 项通过；核心首轮 19 新 formula + 51 renderer 通过。最终 check 修复后的计数另记，不能累加为独立总量。
- Component：1/1 成功，`tests/tmp/rnd502/component/report.json`；最小 fixture 不含公式/表格，不以此证明公式验收。
- Direct phase2-core：5/5 生成成功、0 P0 issue，原始报告 `tests/tmp/rnd502/matrix/report.json`；样式/人工积压仍使 phase3_entry_ready=False。
- 矩阵 RS2G04 的旧无报告重扫显示 2 条 LaTeX 残留。另用正式单次 adapter 生成并留存报告：143 次公式=141 OMML+2 text_fallback（invalid_syntax），带报告校验未登记残留 0；见 `tests/tmp/rnd502/local-report-audit.json` 及 report-audit 下 DOCX/私有公式报告。两种证据均保留，不修改旧矩阵判定器来消告警。
- Golden preflight：阻断码 golden_sample_auth_missing / golden_sample_api_unreachable；4份PDF库存完整。当前未配置管理员凭据、未运行API，按仓库规定不启动服务；线上 Golden 未执行，见 `tests/tmp/rnd502/golden-preflight.json`。
- Microsoft Word 人工签字、真实 MySQL/InnoDB、部署文件系统与真实 S3：本轮未验证；fake/OOXML 不代替这些证据。

## 独立检查与最终门禁

结果接线专项 critical_reviewer 未发现确认问题，主会话已用真实集成测试核实；完整 trellis-check 正在修复确认边界，见 implementation-review.md。最终冻结版门禁如下；上面的中途计数是历史过程证据，不作为最终版本结论。

## 最终冻结版门禁（2026-10-23）

业务源快照：`4af77e68e8d0d358a237f42f6c76c4508cababec6ac83a2294641ad06d5f42ec`；13个业务/脚本文件的逐文件哈希与 HEAD 见 `tests/tmp/rnd502/final-code-snapshot.json`。HEAD 仍为 c56e128，未提交的实现用本快照标识，不将旧 commit 直接当新实现版本。

| 门禁 | 实际结果 | 证据 |
|---|---|---|
| 计划15模块合并定向 | 306项，34.959s，exit 0 | tests/tmp/rnd502/final-targeted.log |
| scripts/ops/check_release.py | exit 0；202项，6.606s；OpenAPI current | tests/tmp/rnd502/final-release.log |
| 组件样本 | 1/1，exit 0 | tests/tmp/rnd502/final-component/report.json |
| direct phase2-core | 5/5，0 P0 issue，exit 0；phase3仍因原P1/P2积压未ready | tests/tmp/rnd502/final-matrix/report.json |
| 正式报告补充审计 | RS2G04：143次=141 OMML+2 invalid_syntax降级；未登记残留0 | tests/tmp/rnd502/final-local-report-audit.json |
| 独立 check / readonly review | 120 focus通过；5项确认问题独立复验全部闭合 | implementation-review.md |
| diff/context | git diff --check通过；task validate implement/check各8，无警告 | 最终主会话保护检查 |

最终 RS2G04 审计 DOCX SHA-256：`d1a77be606a8eac6c18a0205afa32bf46ee3e44683a2fd883a79ca3201be307f`；报告哈希 `0dbcc34dd13884b8e568c202aacce0654407610ed2231be038a3287eb0f17507`。文件和私有报告保留在 `tests/tmp/rnd502/final-report-audit/`。旧矩阵无报告重扫仍记2残留，实际是已登记、带提示、完整原文的2次降级；没有屏蔽旧扫描或修改矩阵规则。

最终15模块为：formula_rendering、document_ir_word_renderer_layout、document_ir_mineru_converter_layout、golden_sample_manifest、document_job_execution_stages、document_job_result_persistence、document_job_delivery_state、document_job_download_availability_api、conversion_sandbox_dev_tools、protected_tokens、document_ir_translation、translation_integrity、translation_integrity_execution、translation_batch_failure_semantics、formula_translation_boundary。实际命令/退出码/耗时见 final-gates.json；202项与306项有重叠，不相加声称唯一测试总数。

## AC 对照

| 条件 | 证据与结果 |
|---|---|
| AC1 | 全正文/列表/标题/独立公式/原生cell/caption/context/note；重复出现、数字semantic三入口、精确来源与实际锚点测试通过 |
| AC2 | 精确frac/root/script/style/tag/vee/text空格、显式group及命令原子基底测试通过 |
| AC3 | 正文不整段进入OMML，HTML样式与公式顺序、原生表格断言通过 |
| AC4 | unknown/malformed/unsupported/空源、完整literal提示/reason；源缺失仍失败关闭；嵌套不支持组合受控降级 |
| AC5 | 写DOM前预期绑定；数字、脚本、style、提示、源、锚点及额外可见/隐藏节点篡改拒绝；独立24例复验 |
| AC6 | 公式不经术语改写；金额/escaped dollar/路径/underscore/HTML负例及长文本扫描通过 |
| AC7 | 主动恶意fake、eq子树、共享完整scanner/Codec覆盖、跨节点/未保护数学零Provider；真实合成MinerU→IR→fake→native-table DOCX通过 |
| AC8 | 新fallback草稿可内部下载；四质量状态/陈旧passed、unreviewed、owner/admin/download/approve发布合同回归通过 |
| AC9 | 单次context并发隔离；选中receipt质量原子派生；新代清槽；legacy/明确历史指针/receipt三入口及损坏拒绝；旧根计划不覆盖测试通过 |
| AC10 | 内容、图片、原生表格、布局/模板/字段回归与release通过；无新API/schema/DDL/Provider或Codec规则 |
| AC11 | 所有本地可执行计划门已留证；线上Golden认证/API阻断，真Word签字及真实MySQL/S3未验证，准确保留待验 |

## 实际范围和影响

- 13个业务/脚本文件：新增 formula.py/table_expansion.py，修改 mineru_content、translator、text/table/image/word renderer、docx_quality/evidence、execution/result_state、formal adapter。image仅传来源上下文；大表只共享原展开内容投影，保留原阈值/几何/原生表格。没有承接RND-501/其它backlog。
- 10个测试文件：新增两个公式专项，维护renderer/converter、执行/持久化/交付、Worker完整性、批次失败和fastapi OOXML语义用例。两处w:t-only断言改读w:t+m:t，仍验证内容及顺序。
- 文档：DOCX设计、Word/翻译Spec与当前任务证据更新；三件套保留批准v2原字节。新增/实质修改的注释、docstring及错误文案使用中文，协议字段保留原名。
- OpenAPI快照无变化；无新endpoint、typed DTO、数据库表/列/迁移、状态枚举、前端、环境变量、依赖或外部调用。公式报告复用现有内部metadata和quality_summary JSON，权限/available actions维持后端权威。
- fresh报告不符归quality_checking/render_failed；receipt/历史新报告损坏归uploading/oss_failed，保留选件；翻译保护调用前失败沿用translation_failed+安全formula_protection，不伪造integrity/审计。
- 幂等、generation、CAS、first-valid-receipt及不可变文件保持；报告I/O在job锁外，摘要由锁内最新记录的已选receipt派生。明确历史指针仍允许跨代复用，按文件原IR校验，不导入旧摘要到新代。

## 残余风险、部署和回滚

- 未完成真Microsoft Word版本/页数/换行/表格视觉签字；OOXML和可打开不等于视觉验收。降级原式可能变长，需要按实际Word检查。当前两个RS2降级保持可见原文和warning，不宣称全功能TeX。
- Golden仅preflight，缺管理员认证/API未运行；不为本轮启动服务。四方向真实供应商翻译质量、线上MinerU/S3及真实InnoDB/部署文件系统不由fake证明。
- 抽取数学item集合变化的活跃旧计划会按原树/来源合同失败关闭，不覆盖同代根计划。部署/回退须暂停入队/内联消费并排空相关在途，或使用理解新报告/旧计划的兼容执行器；不把不识别新合同的旧执行器直接启用。
- 回滚只撤本任务业务增量，保留已生成DOCX、报告、receipt、旧计划和审计；不重写已发布件、不删除历史、不改截图默认。发现依赖失效、冻结产品/ADR冲突或必须破坏性迁移时停止。
- 最终停review，未提交、未push、未归档；人工审核不等于本轮已发布/批准。

## 最终工作区保护结论

`implementation-protection.json` 已实测确认：branch=md2word/RND-502、HEAD仍c56e128；原302项暂存删除的暂存树完全一致，未识别既有dirty零变化；45个manifest仅RND-502改变，另44任务保持；三件套批准v2字节保持；最终测试后的13个业务文件哈希未变。Word摘录源哈希一致。manifest=review，Trellis=in_progress，当前session仍准确指向本子任务。没有commit/push/archive或下一任务启动。
