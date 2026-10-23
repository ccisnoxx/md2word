# RND-504 当前实现验证

2026-10-23。目标代码位于 `/Users/sc/.codex/worktrees/rnd504-current-integration/md2word`，分支 `codex/rnd504-current-integration`、HEAD基线 `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`。未提交候选的文件SHA见 research/candidate-files.json；批准修订4三件套保持原hash。CON-103依赖仍done。本文件只记录当前目标，历史40项快照不作为当前通过。

## 1. 环境与实际命令

所有新工作树检查使用现有解释器 `/Users/sc/PycharmProjects/md2word/.venv/bin/python`，cwd及PYTHONPATH明确指向上述目标，`PYTHONDONTWRITEBYTECODE=1`。未安装依赖或启用生产配置。TestClient、fake S3/MySQL、tests-only协议子进程/loopback fixture 是离线测试证据，不是线上服务/真实存储或生产引擎。

| 检查 | 当前结果与证据 |
|---|---|
| 初始delivery/download/identity基线 | 22项通过；实施代理记录0.371s。 |
| 三组预览集中测试 | `python -m unittest tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence`，55项通过44.579s，research/rnd504-preview-final.log。 |
| 完整应用组受影响重跑 | 随后增加完整预览最短TTL并完善错误一致性/脱敏；`python -m unittest tests.test_document_job_word_preview`，28项通过31.437s，research/rnd504-preview-app-final.log。未变Provider/持久化结果复用；当前loader独立覆盖共56项，不宣称最后一次集中跑56。 |
| Trellis check定向复验 | 10个selector通过13.119s，research/trellis-check-targeted.log；覆盖修订4登记中断/CAS、生命周期/未知存储/后验失效、公式桥接、完整TTL。未自修业务。 |
| 当前既有10模块合同回归 | 最终集中113项52.980s，6failure、0error；全部与未改HEAD复现列表逐项一致，见下一节，不能称113项全通过。research/final-contract-regression.log。 |
| component OPA228 | `scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir tests/tmp/rnd504-integration-component --no-timestamp`，1/1成功、DOCX可打开；research/rnd504-integration-component-evidence.json。 |
| direct phase2-core | CLI dry-run先退出1（工作树无ignored样本）；后用现有脚本模块MatrixConfig、仅将module.ROOT作为输入查找根指向原工作区，代码/模板/输出仍为当前工作树；direct实际转换5/5成功，P0=0、automated_matrix_ok=true，P1/P2仍有标题样式/LaTeX提示、phase3_entry_ready=false。research/rnd504-integration-direct-evidence.json；不是视觉签字。 |
| release聚合门 | `python scripts/ops/check_release.py`退出0，203项通过7.030s；OpenAPI current/changed=false（164 paths/324 schemas）、frontend contract和smoke mock通过。research/release-check.log。无公开schema变化，未改docs/api/openapi.json。 |
| 静态与Trellis | 触及Python可解析，git diff --check通过；task.py validate implement/check各12条，无警告。未配置lint/typecheck工具或入口，两项N/A，不将编译/AST称类型检查。 |

最终合同回归命令：

```text
python -m unittest tests.test_document_job_execution_stages tests.test_document_job_result_persistence tests.test_document_job_delivery_state tests.test_document_job_modes tests.test_document_job_download_availability tests.test_document_job_download_availability_api tests.test_document_job_delivery_state_api tests.test_generated_artifact_identity tests.test_artifact_retention tests.test_translation_integrity_execution
```

## 2. 基线失败与本次修复

现有113项首次运行发现实质公式桥接缺陷，已修复为读取锁内非预览基础，不能由completion调用方passed覆盖pending/blocked。普通默认disabled新增pending/manifest使旧无预览fixture前置变化，已明确构造legacy snapshot隔离，保留主件写计数/完整性/权限/状态原断言，并新增真实默认与成功预览组合测试。没有允许通用summary改写producer贡献。

最终5个selector共6次failure在未改HEAD独立只读快照复现：

- execution的automatic_word_discovery、explicit_result_reuses_old_generation：旧fixture含新图片标记但缺报告；原件认证没有放宽。
- execution的zero_translation_units：空MinerU触发mineru_content_empty，未伪造输入成功。
- delivery API的operator_approval、qa_scope：旧_assert_defaults要求quality_summary={}，HEAD的RND-502已经投影formula摘要；file/database展开共3次failure。未删除旧断言。

精确selector及逐项比较见 research/baseline-failure-comparison.json；HEAD日志为research/rnd504-head-baseline.log（3项1.386s）及rnd504-head-api-baseline.log（2项1.001s）。原始首轮/修正中间日志保留，最终结果以前述当前集中113项为准。没有把基线失败计为通过，也不扩张本任务修其他合同。

## 3. 修订4与当前合同证据

R1：当前attempt在PDF/page/失败manifest首副作用前窄CAS标registering；只有同来源/run/attempt manifest确认才完成。真实最后attempt登记中断覆盖file/SQLite×PDF/page/manifest×插入前后/写后/确认前后；旧失败manifest不能替代新attempt，登记未知/耗尽/同key重放不变成功。预登记耗尽只在原deadline内失败留证，不增加Provider/attempt/deadline。

R2：有效主件及完整当前manifest/PDF/必需页面锁外观测，再锁内比较source/current/revision及最早期限；真实90天主件/1天manifest、三类文件过期/删除/明确缺失可由新key有界恢复。未知存储/完整性失败不消耗新key伪装缺失；旧key历史与available分开，后验删除返回不可用。完整必需证据最短TTL同时约束两个既有S3签发点。

质量顺序保留receipt公式fallback warning、自身blocked恢复、并发同值blocked、批准不复活；CON-104 classification/eligible/enabled、TR-406同锁、RND-502/503认证、共享含file_id对象键及普通pending/generated_word规则保留。无DDL/迁移/新HTTP API/前端/页映射/发布/DocumentIR变更。

## 4. 未执行与剩余门禁

真实生产引擎/完整PDF解码器/字体与批准隔离、真实MySQL/InnoDB竞争/断连、部署FS与S3、线上Golden、Microsoft Word人工视觉和部署回滚没有执行。fake/子进程合同不证明这些属性。生产保持backend=disabled、production_ready=false；即使adapter_contract_ready，也不能直接启用。

独立实际diff复核结论及处理见 implementation-review.md；仅review等待人工验收，不提交/push/archive/add_session或启动其他任务。原根dirty/暂存内容与输入文件保护见最终保护报告及research/root-index-verification.json。


## 5. 独立复核后的最终差异与复验

独立critical reviewer确认IR1列表平方读取、IR2存储异常路径泄露、IR3旧终态initial新UUID误判三项P2，主会话逐项用独立反例核实，实施代理仅修改service.py/preview.py/preview_state.py及应用测试。冻结三件套不改，属于原范围局部修复；完整审查记录见implementation-review.md和research/implementation-review-round1.json。

- IR1：单次列表只取一次完整观测、匹配完整Record。3页=6次读取/3次PNG解码，10页=13次读取/10次解码；原10页156次读取。部分/旧run/跨scope、失效/损坏/未知整组、stale Record仍拒绝。无全局缓存，单件/Token继续独立重验。
- IR2：新预览窄I/O把已识别存储异常转换固定安全错误；17个initial和4个独立重试故障子例不泄露canary，保留oss_failed/receipt/pending；明确对象缺失、ValueError契约与BaseException不混淆。
- IR3：file/SQLite旧succeeded/failed/unavailable current initial在完整有效证据下，新UUID同锁补证后alias或新run；不增加原run预算/期限，不升级旧running未知。
- 完整应用组最终35项通过41.451s，research/rnd504-review-delta-app-final.log，新增7个selector均包含；复用未变Provider和持久化模块的成功结果，当前loader三模块合计63项。首轮7selector两处fixture前置失败与修正已记录，未把中间日志算通过。
- Trellis checker再次短复验四文件AST/引用/中文/原测试合同与diffcheck，无发现、自修0；复用35项完整成功日志，不重复本轮重跑。
- post-review release再跑：203项7.401s全通过，OpenAPI current/changed=false、前端contract/smoke mock通过，research/post-review-release-check.log。
- post-review既有10模块再跑：113项53.878s，仍6failure、0error，失败列表与HEAD对照及前次当前运行完全相同，research/post-review-contract-regression.log；没有新增回归，也不能称全绿。

component/direct不涉及本轮四文件行为，输入和renderer未变，复用前述实际成功证据；不再重复视觉或未获准生产验证。最终指纹见research/candidate-files.json，主会话及审查者均按该候选核对。
