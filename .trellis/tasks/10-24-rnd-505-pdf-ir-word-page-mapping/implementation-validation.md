# RND-505 实施验证记录

2026-10-24。实际工作树`/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`，分支`codex/rnd505-v2-implementation`。HEAD仍8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf，所有G0和RND-505业务增量均未提交。建议同名分支md2word/RND-505保留原状，原根文件与index未动。

## 批准与基线

用户明确接受v2三件套及独立规划复核，授权隔离G0→实施、测试及独立复审，停review不commit/push。批准三件套hash在implementation-authorization.json；实现未改这些批准文件。

G0起点8fa11d97（RND504当前已验收实现及现RND502/503/TR/CON）复用69906a5e的必要RND501能力，融合而非旧文件整包覆盖。四组403 unittest条目里5次已核实历史failure/0error，release203、component1/direct5通过，critical独立复核通过。真实来源/最终指纹、冲突、非有限历史IR类型化身份及fixture决策见g0-integration.md、g0-source-fingerprints.json、g0-failure-comparison.json和g0-review.md。G0快照tests/tmp/rnd505-g0-b0，之后才task.py start。

## 当前实现验证

| 检查 | 当前结果 | 证据 |
|---|---|---|
| renderer六模块 | 145项通过；随后只补共享header/footer，anchor12项通过，唯一覆盖146，不把重叠相加 | renderer-tests.log、renderer-validation.json |
| mapper/应用/持久化四模块 | 103项全通过，96.398s；最后类型/安全细节后19项通过，6.363s | mapping-tests.log、mapping-final-targeted.log |
| 最终集中定向18模块 | 339项，143.718s，5次已确认历史failure、0error | final-targeted.log |
| 实际独立复审与修复 | 1P2已关闭，checker新增2项及完整受影响14项通过，2.049s；critical独立重放深层反例并通过新增1项 | trellis-check.md、implementation-review.md |
| B1三恢复入口 | 指定实际B1 execution源码，file/SQLite×三入口×五类proof=30子场景，1个test通过，8.198s | b1-three-entry-tests.log |
| B1独立应用进程 | 实际从B1加载execution/preview/block_anchors并核路径与hash；file/SQLite均完成主件/预览、无新proof/mapping，旧manifest reader正常 | b1-application-probe.log、b1-application-results.json |
| renderer B0/B1源码交叉 | B0生成旧件；B0拒绝新图片marker；B1读旧/新件及原proof保持，停止新marker生成，三项通过 | renderer-validation.json、tests/tmp/rnd505-b1-renderer/compatibility-results.json |
| 最终release | 203项通过，7.043s；补丁后再跑203项通过，7.111s，OpenAPI current/changed=false | final-release.log、post-review-release.log |
| component / direct | component1/1；direct phase2-core 5/5、P0=0，automated_matrix_ok=true | final-component.log、final-direct.log、tests/tmp/rnd505-final-* |
| 静态/context | checker36个Python AST通过，git diff --check通过；task validate implement9/check10，无警告 | trellis-check.md、主会话最终命令 |

所有Python命令使用现有venv，cwd明确指向隔离树，未安装依赖。ruff/flake8/mypy/pyright无配置/工具，lint和type-check为N/A，AST不冒充这两项。集中339项在递归边界修复前启动，未将它当新负例证据；修复只改变坏可选证明边界，14项受影响复验+独立反例+B1重建+补丁后release覆盖该修复，其余未变有效输入样本结果复用，不机械重跑。

集中定向命令的模块依次为：renderer_block_anchors、renderer_render_plan、renderer_block_evidence、formula_rendering、image_group_rendering、document_ir_word_renderer_layout、preview_page_mapping、document_job_word_preview、document_job_preview_persistence、document_job_result_persistence、word_preview_provider、document_job_execution_stages、document_job_delivery_state、generated_artifact_identity、translation_integrity_execution、document_job_delivery_state_api、document_job_modes、document_job_download_availability（均加tests.前缀）。

## 历史失败与未验边界

2项execution：automatic_word_discovery_requires_current_generation_and_final_ir、explicit_result_reuses_old_generation_but_checks_file_identity（invalid=None），旧fixture主件有图片布局marker却无报告，仍按原规则拒绝。3次API：operator_approval的file/database及qa_scope，旧断言期待quality_summary={}而实际已有RND502 formula摘要。五项selector/触发/失败断言与G0及融合前基线逐项相同，不是仅按数量归因；不改断言或放宽报告认证。

direct仍phase3_entry_ready=false，P1/P2待办不是本任务新验收通过。真实Word/WPS人工视觉、Golden外部环境、生产预览沙箱/字体、真实InnoDB/部署FS-S3及生产大文档容量未验；fake/本地临时目录/测试loopback不代签。生产保持disabled/production_ready=false。

## 兼容与回滚

B0是未提交统一基线，不是旧HEAD。B0真实reader拒绝新图片marker，因此不能直接退回。统一B1由build_b1_snapshot.py可重现复制当前源码，仅停止新marker和manifest.mapping写入，保留全部reader及原proof；b1-source-fingerprints.json记录app清单。B1三入口动态加载其实际execution，其依赖reader与候选字节相同（仅两处writer差异），独立进程另验证真正加载B1模块及停止生成。旧G0 reader实际读取新manifest、新reader读取旧/未知/坏内层mapping均保留原preview，详应用测试。

回滚停止新写入并保留兼容reader、已有metadata和Artifact；不删历史、不覆盖发布件、不清blocker。B1是已验证源码候选，不是生产部署回滚签字。

## 收口

Trellis task保持in_progress，manifest仅当前RND505为review；依赖完成状态和其他任务不变。未commit/push/archive/add_session，未合回原根。新增/实质触及Python注释、docstring和开发者文本按项目中文规则处理；机器字段保留协议值。最终源指纹与原根保护见candidate-files.json、root-protection-final.json。

## 后续全新独立复审

用户要求的全新critical复审、归并归属认证P2核实修复及最终复验见[post-implementation-review.md](post-implementation-review.md)和[fresh-review-validation.md](fresh-review-validation.md)。本页保留原实施验证历史；最新B1 fingerprints/results由最终源码重建，前版保存在pre-fresh-review-evidence。56项定向、B1三入口30子场景、独立进程及release203/component1/direct5通过。原根保护见fresh-review-protection.json。仍review，未提交/push。
