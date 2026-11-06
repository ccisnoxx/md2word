# 源码审查证据矩阵

## 基线、方法和状态

- 来源：用户在 2026-11-06 提供的《源码分析结论》，其审查基线为 2026-11-02 的 `79f20cef…`。
- 本轮基线：本地 `main@79f20cef9ca0bb1a59af635e2408e130c4935e2d`，初始工作区干净。未 fetch，不能据此断言远端截至今日无新提交。
- 方法：阅读维护中的源码、调用接线、项目 Spec、测试定义及相关任务；不导入应用、不启动服务、不运行应用测试、不访问生产。不将测试定义存在视为测试通过。
- 状态：**证实**表示静态事实有直接依据；**部分成立**表示事实存在但推论或覆盖范围过大；**待验证**表示需要运行/环境/产品证据；**不采纳**表示与本轮授权或产品约束冲突。
- 下列 `文件:行号` 相对仓库根目录，锁定上述 commit。A 编号覆盖原报告主要论点；B 编号指向 `../design.md` 的整改批次。综合“强/高/成熟”等评级不当作可验收事实。

## 逐项核实

| ID / 原报告主题 | 状态与实际结论 | 关键证据 | 处理 |
|---|---|---|---|
| A01 产品定位与 SaaS | 部分成立：技术 PDF 内部工作台定位准确；README 明确不扩为 SaaS，不能把企业 SaaS 就绪当作现有目标。 | `README.md:3`、`README.md:10`、`README.md:14` | 保留产品边界；B09 仅条件触发。 |
| A02 模块化单体与 Worker | 证实：架构文档明确模块化单体，生产 Compose 定义 API/Worker/MySQL/Redis，main 组合根装配。配置不代表运行环境已启用。 | `docs/architecture/system-architecture.md:11`、`docker/prod/docker-compose.yml:4`、`app/main.py:146` | 保留，不引入微服务。 |
| A03 DocumentIR | 证实：v1/v2、source span、页面/layout/资产/质量等合同存在；正式 owner 已在 Spec 明确，无须重新建设 IR。 | `app/services/document_ir/models.py:15`、`app/services/document_ir/models.py:197`、`.trellis/spec/backend/word-generation-rules.md:5` | B04/B05 必须保留 v1 兼容；v1 不是旧 runtime。 |
| A04 ZIP 输入边界 | 证实：条目、声明/实际大小、路径、特殊/加密条目、目标身份碰撞、选中 JSON 唯一性和哈希检查存在。不是本轮安全攻防验收。 | `app/services/document_ir/mineru_package.py:17`、`app/services/document_ir/mineru_package.py:134`、`app/services/document_ir/mineru_package.py:189`、`app/services/document_ir/mineru_package.py:205` | 保留现有 owner；不另写解压器。 |
| A05 结果 URL 白名单与回调 | 部分成立：回调入口验证 HTTPS/host/checksum；正式主动轮询取回 full_zip_url 后直达下载器，未复用同一 URL 校验。下载器直接 requests.get，未显式约束重定向目的地址；本地已安装 requests 源码也注明默认允许重定向。不能把回调校验扩写为所有下载路径安全。 | `app/domains/jobs/mineru_callback.py:9`、`app/api/mineru_callback_guards.py:27`、`app/api/mineru_callback_guards.py:81`、`app/domains/document_jobs/execution.py:321`、`app/domains/document_jobs/execution.py:729`、`app/clients/mineru_client.py:104` | B03/P1：边界一致性优先于大拆分；尚未证明可利用攻击或生产暴露。 |
| A06 翻译技术完整性 | 证实机制，限制评级：编码、严格返回、逐项计数、证据绑定与 fan-in 重验存在；仅覆盖已定义语法，不能推出任意型号/公式、参数关联或译文语义必然正确。 | `app/domains/translation/integrity.py:191`、`app/domains/translation/document_ir_translator.py:281`、`app/domains/document_jobs/execution.py:2501`、`.trellis/spec/backend/translation-integrity-validator.md:3` | 保留 fail-closed 和整批一次回填；不重做 TR-402/403。 |
| A07 表格翻译上下文 | 部分成立：DOM 文本节点生成 html 序号 item，Provider 只有 id/text 无行列表头字段；存在质量风险，但“比正文差多少”无对照证据。不能将短型号 Vos 本身默认视作应翻译自然语言。 | `app/domains/translation/document_ir_translator.py:578`、`app/domains/translation/provider.py:191`、`docs/implementation/codex-task-backlog.md:390` | B06 复用既有 TR-404 待办，先样本，再受控上下文合同。 |
| A08 Renderer 计划与证据 | 证实：资源/布局/表格/渲染计划、collector、锚点和公式上下文存在；内容定位证据不等于真实 Word 页码或视觉验收。 | `app/services/renderer/word_renderer.py:108`、`app/services/renderer/word_renderer.py:181`、`app/services/renderer/block_anchors.py:1` | 保留，不另造 writer。 |
| A09 python-docx 私有依赖与回归 | 部分成立：底层 OOXML/私有挂载和宽版本范围确实存在；并非没有 characterization/OOXML/golden 资产。也没有证据证明当前版本已不兼容。 | `requirements.txt:9`、`app/services/renderer/word_renderer.py:210`、`tests/test_document_ir_word_renderer_layout.py:2118`、`tests/test_render_table_from_html_characterization.py:322`、`tests/fixtures/golden_samples/manifest.yaml:1` | B02 复用定向测试，比较规范化 OOXML 语义；不要求原始 ZIP 字节相同。 |
| A10 整页降级 | 证实并补充：不可编辑提示、整页图、闭包与默认 0.5 阈值存在；单页开关、比例及渲染尝试已配置化；direct 的渲染降级明确排除翻译模式及完整性/超时等错误。真实 Word 分页仍未验。 | `app/services/document_ir/page_degradation.py:11`、`app/services/document_ir/page_degradation.py:25`、`app/domains/document_jobs/execution.py:3403`、`app/domains/document_jobs/base_quality.py:136`、`.trellis/tasks/11-02-poppler-readiness-degradation-policy/prd.md:5` | 复用已有任务；blocked 与 internal_draft 分属质量/交付维度，不能混为执行失败。 |
| A11 并发、代次与幂等 | 证实机制，运行可靠性待验证：同 job 锁、条件更新、receipt、attempt/lease、发布/新代账本存在；不能从 FOR UPDATE 推出全部交错正确。 | `app/infrastructure/persistence/mysql/document_jobs.py:104`、`app/infrastructure/persistence/mysql/document_jobs.py:136`、`.trellis/spec/backend/translation-batch-lifecycle.md:1`、`.trellis/spec/backend/database-guidelines.md:1` | B04/B05 不移动原子边界；真实 MySQL/旧 Worker 排空属于另行授权证据。 |
| A12 schema 与 JSON 持久化 | 证实：LONGTEXT、字符串时间、启动 bootstrap/补列/索引维护存在；无版本迁移账本。JSON + 投影并不自动等于缺陷。 | `app/infrastructure/persistence/mysql/schema.py:9`、`app/infrastructure/persistence/mysql/schema.py:550`、`app/infrastructure/persistence/mysql/backend.py:37`、`.trellis/spec/backend/database-guidelines.md:41` | B08 条件专项；不预选 Alembic/ORM，不承诺所有 DDL 可逆。 |
| A13 巨型执行器 | 证实 4,218 行/214,081 字节、多阶段与副作用集中；不能仅据大小指定 StageContext/StageResult/Registry 全套架构。 | `app/domains/document_jobs/execution.py:144`、`app/domains/document_jobs/execution.py:201`、`app/domains/document_jobs/execution.py:1371`、`app/domains/document_jobs/execution.py:3167` | B04 小范围职责提取；保持 repository 和领域规则原 owner。 |
| A14 两套链路 | 部分成立：legacy runtime 仍由 main 装配且有 stage worker 入口，但当前 v1 router 已不公开 /jobs。正式 Renderer 还复用 conversion 的规则/解析。 | `app/main.py:370`、`scripts/dev/run_stage_worker.py:33`、`app/api/v1/router.py:35`、`tests/test_openapi_export.py:39`、`app/services/renderer/table_renderer.py:22`、`app/conversion/runtime_runner.py:84` | B05 盘点残余调用、队列和共享依赖，不整体删除 conversion；不把旧 HTTP 下线再做一遍。 |
| A15 大 Vue 页面与路由 | 证实大小与静态导入；首包实际体积、加载耗时及用户影响未测。 | `frontend/src/pages/OpsDashboardPage.vue:1`、`frontend/src/pages/JobDetailPage.vue:1`、`frontend/src/pages/FileRetentionPage.vue:1`、`frontend/src/router/index.ts:7`、`frontend/vite.config.ts:1` | B07 先路由/一个页面；性能改善必须有同基线对比。 |
| A16 构建可复现性 | 证实：Python 宽范围、未跟踪完整锁；pip upgrade、普通镜像标签及未固定 apt 源/包版本会留下漂移。前端已有 package-lock。 | `requirements.txt:1`、`docker/prod/Dockerfile:2`、`docker/prod/Dockerfile:10`、`docker/prod/Dockerfile:16`、`docker/prod/docker-compose.yml:78`、`frontend/package-lock.json:1` | B02 分清依赖解析可复现与整镜像逐字节复现，不混为一项。 |
| A17 CI、lint、typecheck | 不采纳 CI/全量测试建议。无 pyproject 不代表必须迁移；前端已有 vue-tsc 构建检查，不能写成全项目无类型检查。 | `frontend/package.json:9`、`AGENTS.md:1`；Git 跟踪清单未见 .github/pyproject/uv.lock/poetry.lock | 本轮和候选默认验证均排除 CI、全仓测试、聚合发布脚本。 |
| A18 JWT localStorage | 证实存储方式；静态审查未证实可利用 XSS，内部系统也不因此自动安全。迁移 Cookie 会改变认证/CSRF/跨域合同。 | `frontend/src/utils/authStorage.ts:1`、`app/api/dependencies.py:30` | B09 先部署与会话威胁边界，再决定是否迁移。 |
| A19 Provider 密钥与审计 | 部分成立：JSON 明文及尝试 chmod 0600 存在；配置 API 限 admin、响应掩码、修改审计已经存在。实际文件权限/备份访问面未核查。 | `app/domains/translation/provider_config.py:161`、`app/domains/translation/provider_config_router.py:29`、`app/domains/translation/provider_config_router.py:47` | B09 不重复建设审计；不读取真实密钥，不预选 Secret Manager。 |
| A20 Provider Base URL | 证实检查路径中 base_url 为普通字符串，标准化后传给 SDK；配置入口为 admin，不能描述成任意匿名输入 SSRF。部署出站限制未核查。 | `app/domains/translation/provider_config_schemas.py:27`、`app/domains/translation/provider_config.py:117`、`app/domains/translation/provider.py:77` | B09 盘点兼容端点、信任模型，再决定 URL 策略；与 A05 分开。 |
| A21 文档漂移 | 证实 Token 模块首行与实际调用不符，gap 清单仍称 Codec 缺失；但 gap/架构文档已有 baseline_commit 和 last_reviewed，不能建议“从零加版本标识”。 | `app/domains/translation/protected_tokens.py:1`、`app/domains/translation/document_ir_translator.py:30`、`docs/implementation/current-gap-analysis.md:1`、`docs/implementation/current-gap-analysis.md:64`、`docs/architecture/system-architecture.md:1` | B01 修正当期状态或明确历史引用；不全量归档仍被引用文档。 |
| A22 仓库卫生 | 证实 IDE/run 配置与 test-results 跟踪，ignore 不会取消已跟踪文件；工具目录和共享运行配置并非天然垃圾。 | `.gitignore:19`、`.run/Local MinerU Direct.run.xml:1`；git ls-files 输出见下方 | B01 先用途/引用清单，保留 Trellis/Skills/共享 run 配置；未知临时 shell 未核定，不泛删。 |
| A23 LICENSE | 证实本次顶层检查未发现 LICENSE/同名常见变体；不能推导默认开源许可，也不能替所有者选择许可。 | 顶层路径与 git ls-files 核查 | B11 仅在外部分发/开源意图确定后决策。 |
| A24 publication 扫描 | 证实 MySQL 文件保护查询读取全量 protected_file_ids 后 Python 判断；存在增长成本，未证明当前瓶颈。 | `app/infrastructure/persistence/mysql/files.py:81`、`app/infrastructure/persistence/mysql/document_jobs.py:306`、`app/domains/files/retention.py:87` | B10 先定向测量，再考虑结构化索引；保持删除/发布锁序。 |
| A25 质量指标与容量 | 部分成立：已有 health metrics 入口、quality summary 和源页/降级计数，不能从零另造指标系统；完整五类质量指标覆盖与大文档/并发容量未核实。 | `app/api/v1/routers/health.py:31`、`app/services/health_service.py:476`、`app/domains/document_jobs/base_quality.py:114`、`.trellis/tasks/11-02-source-page-counts/prd.md:1` | B10 定义分母和现有数据映射，缺失再增补；本轮无压测。 |
| A26 Docker 与启动保护 | 证实非 root、默认回环绑定、healthcheck、必填密码及生产禁 open 的配置/代码存在；不代表已部署正确。 | `docker/prod/Dockerfile:31`、`docker/prod/docker-compose.yml:29`、`docker/prod/docker-compose.yml:91`、`app/main.py:136` | 保留；B02 不弱化。 |
| A27 后端权限与前端一致 | 部分成立：后端角色权限集中定义、前端按权限过滤；全路由逐项授权对齐和绕过测试未执行，不能总体认证“完全一致”。 | `app/services/auth/permissions.py:11`、`frontend/src/navigation/appShell.ts:123`、`app/api/dependencies.py:30` | B07/B09 定向保护所改动作/路由，不做全站权限重写。 |
| A28 Poppler 最新变更 | 证实 HEAD 提交主题及已有专项任务涉及就绪/配置化降级；已有任务打勾不是本轮生产验收。 | `.trellis/tasks/11-02-poppler-readiness-degradation-policy/prd.md:1`、`docker/prod/Dockerfile:10` | 保留原任务；不重复实现/归档/部署。 |
| A29 总体评级与全部 P0 | 待验证/重排：“功能成熟、并发可靠、外部化就绪”等不能由本轮抽查量化；没有足够证据把全套重构、CI、迁移列为立即 P0。 | A01–A28 的证据边界 | 采用 design 中优先级定义；未发现足够新增 P0 证据不等于证明无 P0。 |

## 已核实规模和文件清单

| 路径 | 行数 | 字节数 |
|---|---:|---:|
| app/domains/document_jobs/execution.py | 4218 | 214081 |
| frontend/src/pages/OpsDashboardPage.vue | 3004 | 121527 |
| frontend/src/pages/JobDetailPage.vue | 2995 | 113803 |
| frontend/src/pages/FileRetentionPage.vue | 2329 | 96975 |
| frontend/src/pages/IncidentTriagePage.vue | 2059 | 65562 |
| frontend/src/pages/JobsPage.vue | 2106 | 63213 |

已跟踪测试输出：`frontend/test-results/.last-run.json`、`frontend/test-results/core-flow-operations-redes-34b6f-blet-and-mobile-screenshots-chrome/trace.zip`。本轮只核对路径，不打开 trace 内容，不删除。

本地辅助证据：`.venv/lib/python3.11/site-packages/requests/api.py:48` 说明 allow_redirects 默认 True；这是本机安装源码，不是锁定依赖或生产版本证明。A05 的核心依据仍是仓库中下载入口缺少统一校验；未向任意目标发送探针。

## 未验证边界

真实供应商/四语言译文语义、Word 人工排版、真实 MySQL 交错与断连、文件系统跨进程锁、S3、Worker 崩溃恢复、生产版本/权限/网络出口、重定向实际利用、首包与性能、依赖重新安装、Docker 构建、运行中的 Poppler 均未验证。没有发现的能力不直接记作“缺失”，历史成功不直接记作本轮通过。

## 2026-11-06 B03 后续进展同步

以上为原始审查与既有任务盘点时点。B03 后经用户独立批准实施，四个既有回调夹具另经批准修复；现两个任务均为 completed（本地实现和批准定向验收完成），未提交、推送或归档。A05 的初始缺口已完成本地修复验收；换代并发/真实生产证据边界仍保留。详见 [总计划进度](../progress.md) 与 [B03 逐项对账](../../11-06-mineru-download-boundary/acceptance-reconciliation.md)。本轮只同步记录，未运行测试，未改变其他既有任务及产品 manifest。
