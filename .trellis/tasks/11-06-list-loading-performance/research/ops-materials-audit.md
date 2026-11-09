# Research: 运维材料归属、冻结证据与本地整理审计

- Query: 审计本任务未提交运维材料及对应 Spec，形成两类提交归属建议；核对冻结摘要、时间语义、验证复用、明显敏感信息与过时状态入口。
- Scope: internal；只读本地任务材料、相关 Spec 和直接源码。仅创建本报告；不运行 Git、SSH、网络、容器、业务测试或任何运维脚本。
- Date: 2026-11-09
- 授权边界：用户本轮仅授权本地材料整理、任务记录与待批准提交计划；不 stage、commit、push，不改生产。主会话与本研究并行工作，本报告不覆盖其修改。

## Findings

### 1. 证据来源及文件归属

以下使用 `T=.trellis/tasks/11-06-list-loading-performance`、`R=T/research` 缩写。

- **主会话已核事实，本研究未执行 Git 重查：** 初始 `HEAD/main=b8b2779a`、index 为空；初始差异全部归属本任务，共 6 个 tracked 修改、23 个 untracked 文件。产品代码没有本轮新增差异。
- **本研究直接核对：** 本地文件内容、JSON 可解析性、SHA-256、现有验收采样的统计及时间关系、Markdown 本地链接、明显凭据/标识/业务内容候选。
- **既有记录，不是本轮重跑：** 本地产品测试、真实 MySQL 定向验证、镜像导入、恢复与生产执行及浏览器验收，均由原报告承载；本研究没有重新访问其执行环境。

| 文件/文件组 | 职责与归属 |
| --- | --- |
| `.trellis/spec/backend/document-job-list-query-v2.md` | 当前查询/迁移/外置运维合同；本次唯一初始有差异的 Spec |
| `T/production-switch-plan.md` | 已补上线后状态入口的审批方案；正文含构建/审批时快照 |
| `R/release_ops/{common.py,migrate.py,snapshot.py,query_diff.py,test_release_ops.py,README.md}` | 原 6 文件冻结运维包；当前 SHA 与 manifest 一致 |
| `R/release_ops/{window_helpers.py,test_window_helpers.py}` | 窗口文件系统与真实角色矩阵辅助实现及直接测试；有独立审查 SHA |
| `R/{window-lib.py,window-production-switch.py}` | 已执行窗口载体的本地快照；有独立审查 SHA，依赖当时受限远端状态 |
| `R/{production-build.md,production-build-manifest.json,production-execution-plan.md,approval-package-manifest.json,release-ops-manifest.json}` | 构建、审批及运维包冻结身份，含当时未执行字段 |
| `R/{release-ops-review.md,window-helpers-review.md,window-switch-review.md,window-readiness.md}` | 分阶段独立审查及窗口排空字段研究；结论有各自观察时点 |
| `T/{prd.md,design.md,implement.md,task.json,local-commit-handoff.md,production-execution.md}` | 要求、授权演进、实施状态与最终生产结果 |
| `R/{production-acceptance-result.json,production-browser-acceptance.json}` | 最终主机验收与浏览器原生采样；包含首次测量和纠正后的采样 |

### 2. 建议两类提交分组

这些是供主会话形成具体待批准计划的逻辑分组，不代表已经取得提交授权；单文件不跨组拆分。

**A：运维载体、冻结资产和执行合同（初始 21 项）**

建议主题：`chore(ops): preserve list loading release tools and frozen inputs`。

- `.trellis/spec/backend/document-job-list-query-v2.md`
- `T/production-switch-plan.md`
- `R/production-build.md`
- `R/production-build-manifest.json`
- `R/production-execution-plan.md`
- `R/approval-package-manifest.json`
- `R/release-ops-manifest.json`
- `R/release-ops-review.md`
- `R/window-helpers-review.md`
- `R/window-switch-review.md`
- `R/window-readiness.md`
- `R/window-lib.py`
- `R/window-production-switch.py`
- `R/release_ops/common.py`
- `R/release_ops/migrate.py`
- `R/release_ops/query_diff.py`
- `R/release_ops/snapshot.py`
- `R/release_ops/test_release_ops.py`
- `R/release_ops/README.md`
- `R/release_ops/window_helpers.py`
- `R/release_ops/test_window_helpers.py`

**B：生产验收、任务状态和材料交接（初始 8 项，加本轮新整理材料）**

建议主题：`docs: record list loading production acceptance and handoff`。

- `T/design.md`
- `T/implement.md`
- `T/prd.md`
- `T/task.json`
- `T/local-commit-handoff.md`
- `T/production-execution.md`
- `R/production-acceptance-result.json`
- `R/production-browser-acceptance.json`
- 本轮主会话新增的材料索引、待批准提交计划、当前输入清单、独立保存的验收截图，以及本报告。
- 若本轮主会话修改 `R/verification-summary.md`，其历史状态入口修正也归 B；既有验证内容继续保留。

不能再次把原产品提交已经包含的应用源码、直接测试、迁移实现或其他任务文件作为这批新增工作列入。原 `T/commit-plan.md` 是 2026-11-07 产品提交计划，已由 `T/local-commit-handoff.md:4` 记录落地；本次应使用新的待批准计划，不能把旧确认当成当前材料提交许可。

### 3. 时间语义与冻结身份

#### 构建、审批和最终验收是不同记录

| 证据 | 记录的时点/语义 | 本轮处理原则 |
| --- | --- | --- |
| `R/production-build-manifest.json:7`、`:129` | 固定源码构建输入与完成时间，UTC 日期跨到本地次日 | 保留时间、源码/镜像标识与当时运行态 |
| `R/production-build-manifest.json:513` | Compose `applied=false` 是准备完成时尚未应用 | 不改为 true |
| `R/production-build-manifest.json:573` 及 `nginx-review.json` 子对象 | 原生产容器未变、候选仅语法检查、未 reload | 不用上线后状态覆盖构建快照 |
| `R/approval-package-manifest.json:2`、`:11` | 审批包完成于 `2026-11-06T17:53:40.574229+00:00`，当时生产停写/迁移/切换未执行 | `production_stop_migration_cutover_executed=false` 保留 |
| `R/release-ops-manifest.json:2`、`:44` | 6 文件归档身份与旧/新 CLI 导入通过，尚未执行生产 | `production_execution=false` 保留 |
| `R/production-acceptance-result.json:2`、`:3`、`:4`、`:5` | 后续真实生产切换、浏览器证据和主机收尾验收 | 作为最终结果，和历史 false 并存 |
| `T/task.json:14`、`:44`、`:45`、`:46` | 任务本地日期与 UTC 事件时间 | 不以字段日期不同推断冲突 |

浏览器 JSON 的 `at` 与主机结果的 `browser_evidence_at` 完全一致。按原时间静态计算：

- 恢复入口：`2026-11-07T01:18:34.979889+00:00`。
- 浏览器证据：`2026-11-07T01:32:44.560Z`，比原截止时间早 **38.985271 秒**。
- 主机收尾验收：`2026-11-07T01:38:49.566242+00:00`，比原截止时间晚 **326.020971 秒**。

因此可以表述浏览器验收在截止前完成、主机收尾随后完成；不能笼统声称所有收尾均在截止前完成，也不能为对齐叙述改写截止或验收时间。`T/production-execution.md:40`、`:42` 已分别记录两者。

#### 当前 SHA 核对结果

- `R/release-ops-manifest.json:3` 所列 **6/6 文件 SHA 匹配**，包括冻结 README 与原测试。
- `R/window-helpers-review.md:8` 所列 `window_helpers.py`、`test_window_helpers.py` **2/2 匹配**。
- `R/window-switch-review.md:35` 所列 `window-production-switch.py`、`window-lib.py` **2/2 匹配**。
- `R/approval-package-manifest.json:3` 所列文档 **3/4 匹配**：`production-build.md`、`production-execution-plan.md`、`release-ops-review.md` 当前字节均匹配。
- 唯一失配为 `T/production-switch-plan.md`：历史期望 `7676626e955638aa6c45f78170caf3baa3b37e87dbe780b9dee99c902bced6b1`，本次读取实际 `3da5754a8424c6a2bb5cf6e89f9f8c28944e36a8d41cc52c9f59b2dd971bd82b`。该文档 `:3`、`:129`、`:133` 明示后续上线状态与历史边界，但本研究没有取得原审批正文副本，**不能证明差异仅含这些状态文字**。

建议新索引/当前输入清单明确区分“历史审批 SHA”与“当前文件 SHA”，不要覆盖历史 manifest；不要把失配隐去或宣称 4/4 匹配。当前本地缺少原审批正文副本不等于生产验收失败；最终验收有独立证据文件。

已执行 Python 快照与冻结包继续保留原字节。`R/window-production-switch.py:2`、`R/window-lib.py:4`、`:5` 直接依赖特定发布目录和当时状态文件；它们是历史载体，不能当作通用脚本直接复跑。主会话本轮未授权改写或运行这些脚本。

### 4. 已有验证的输入与复用边界

| 已有证据 | 关联输入及本轮核对 | 可复用范围/不能推出的结论 |
| --- | --- | --- |
| 普通列表 99 离线 + MySQL 模块 12 项（其中 8 项真实引擎），`R/key-integration.md:50`、`:58`、`:60` | 当前共享 SQL SHA 与该报告 `:17` 的最终 SHA 匹配；主会话确认本轮没有产品差异 | 复用已有直接合同和 8.4.13 合成引擎证据；不能把它表述为本轮重跑、全仓通过或生产 8.4.9 证明 |
| 异常读取会话 35 离线 +2 真实 MySQL、8 对正常/4 对错误差分，`R/incident-session-implementation.md:41`、`:51`、`:66` | 原报告与本地交接记录说明最终七模块源码身份核对；本研究未重建忽略目录中的完整冻结夹具 | 复用原事务/错误/观察合同证据；不将 37 与旧 111 简单相加成当前总覆盖；不把合成计时等同于线上收益 |
| 原运维包 12 离线用例与 5 文件 AST，`R/release_ops/README.md:73`、`R/release-ops-review.md:36` | 原 6 文件当前全部匹配冻结 manifest | 复用同输入离线结果；AST 不等于 typecheck，离线 helper 不等于真实恢复演练 |
| 窗口辅助 10 项直接回归，`R/window-helpers-review.md:8`、`:25` | 2 个实现/测试 SHA 均匹配 | 复用目录 size 比较修正等直接回归；真实 Linux/ACL/xattr 恢复由原生产执行记录证明 |
| 窗口执行器独立静态复核，`R/window-switch-review.md:35`、`:37` | 2 个脚本 SHA 均匹配 | 复用静态合同审查；该 review 当时未运行 Tests/Lint/TypeCheck，不改写成通过 |
| 固定镜像依赖/import、341/340 运行文件和 6 次 CLI 导入，`R/production-build.md:22`、`:30`、`:46` | 当前 `requirements/locks/cp311-linux-amd64.txt` SHA 匹配构建 manifest `:112`；当前未重验远端镜像/wheel 集合 | 复用既有构建产物证明；本轮本地文件 hash 不证明远端现状 |
| 生产 8.4.9 恢复 O/C/R、109 场景双跑、生产迁移/保真，`T/production-execution.md:25`、`:26` | 最终执行记录与结果文件相互引用 | 作为 2026-11-07 的历史执行证据复用；未重新访问原始受限远端报告 |
| 正常认证浏览器与错误 loading，`R/production-browser-acceptance.json` | 两组各 3 条 200、transferSize>0；静态重算中位数/页面范围与 `production-acceptance-result.json` 一致 | 普通 API 中位 1508.9ms、页面 2060.4–2447ms；异常 API 中位 1022.7ms、页面 1235–1563.2ms。只证明记录中的样本，不称 p95，不代表本轮再次验收 |

本轮新增或更新纯材料索引、说明、计划、输入清单，不需要借提交准备重跑业务/运维套件。主会话若新增原字节复制的截图，可通过复制前后 hash 记录同一图像；本研究不把“复制文件成功”视为重新进行浏览器验收。

### 5. 版本控制前的明显敏感内容核对

只报告类别与位置，不在本节回显标识值或敏感内容。

- 在初始 29 个路径中，未检出明显私钥块、JWT、生产认证材料、真实用户名列表、业务文件名或完整业务原文。JSON 结构核对显示浏览器材料主要保存接口路径、计时、状态、数量及行为布尔值；其 URL 未含 userinfo，查询键为分页/排序/归档标志。
- 凭据字面量候选 `R/release_ops/test_release_ops.py:126` 已由上下文确认为本地合成测试参数；业务 payload 候选 `:177`、`:178` 为合成 fixture 变更断言。`R/release_ops/README.md:52`、`:53` 为明确的真实账号 ID 格式占位，不是真实账号资料。
- **内部协作身份/本机目录归属信息：** `T/task.json:11`、`:12`、`:17`，`T/local-commit-handoff.md:21`。这些不是认证凭据，但属于可关联的协作与本机路径信息。
- **运维拓扑/实例和存储位置元数据：** `T/production-switch-plan.md:18`、`:20`、`:28`，`R/production-build-manifest.json:3` 起的构建/容器清单，`T/production-execution.md:5`、`:44`，`R/production-acceptance-result.json:56`。应与用户本次整理运维证据的范围一并审阅，不把它们误称业务 payload 或秘密本身。
- **禁止纳入的真实内容载体：** `R/release_ops/README.md:48` 说明真实 cases 文件仅留受限目录；`R/window-helpers-review.md:17`、`:21` 说明文件系统 manifest、真实用户 ID 和搜索词仅落受限 JSON。本地当前运维脚本引用这些文件名不等于对应受限文件已进入当前材料。
- 主会话计划新增的 PNG 在本研究检查时尚未纳入初始清单；视觉内容与复制后身份由主会话单独核对，不能由上述文本扫描自动覆盖。

### 6. 实质过时入口与链接

以下是文档可读性问题，不是已经证实的产品缺陷：

1. **当前 Spec 的第 8 节仍写候选未部署及生产待授权。** `.trellis/spec/backend/document-job-list-query-v2.md:99`、`:107` 与最终执行记录冲突。主会话已通知将只修时态并引用最终记录，不改变原验证内容。
2. **本地验证摘要缺少历史时点入口。** `R/verification-summary.md:3`、`:10`、`:14` 仍直接写未 commit/未部署/任务 in_progress；应增加历史阶段说明及最终记录链接。主会话已负责该改动。
3. **其余阶段报告应由新增索引统一解释。** `R/production-build.md:3`、`:36`，`R/production-execution-plan.md:14`、`:264`，`R/release-ops-review.md:3`、`:31`，`R/window-helpers-review.md:27`，`R/window-switch-review.md:14`、`:38` 均是各自阶段的快照。后续“已执行”不能反向修改当时的“未执行”。其中前三份属于审批文档冻结 SHA 范围，独立 review 也应保留观察时点。
4. **冻结 README 的状态已过时，但不得直接改写。** `R/release_ops/README.md:3`、`:57`、`:63` 为冻结包形成时的真实边界；当前 SHA 匹配，宜由索引链接最终执行记录，避免改 README 导致归档身份失配。
5. `T/design.md:3`、`T/production-switch-plan.md:3` 已有最新结论/历史提示；`T/prd.md:57` 起、`T/implement.md:67` 起、`T/local-commit-handoff.md:47` 起明确最终阶段。材料索引应优先指向这些入口和 `T/production-execution.md`。

静态检查本任务全部 `.md` 与两份相关后端 Spec 的 Markdown 本地路径链接，**未发现缺失目标文件**。远端发布目录、忽略的 `research/data`、官方文档 URL 及 GitHub 页面不属于本轮本地链接存在性检查；未进行网络断链验证。

### 7. 代码模式与相关 Spec

- `R/release_ops/common.py:23`、`:37`：每条实际 owner 连接核对库名/UUID，再设置并读回 RR、读写模式和两类锁等待；不是先验证另一条连接。
- `R/release_ops/migrate.py:24`、`:28`：调用所选完整镜像内原迁移 owner，透传双游标及报告；不复制投影版本算法。
- `R/release_ops/snapshot.py:63`、`:69`、`:140`：恢复全列模式与迁移原列模式显式区分，scope 混用失败。
- `R/release_ops/query_diff.py:120`、`:173`、`:184`：真实角色完整 router 响应、任一错误不通过、恢复实例拒绝生产 UUID；不等同 HTTP/JWT 认证。
- `R/window-production-switch.py:24`、`:60`、`:70`：有效环境/挂载渲染检查在生产迁移前，启动前再次检查渲染不变；`:110` 保留入口恢复失败后的 freeze 处理。
- 相关规范：`.trellis/workflow.md` 的证据持久化与提交计划；`.trellis/spec/backend/document-job-list-query-v2.md:14`、`:42`、`:87`、`:109` 的本轮运维路径、原列/全列 scope、O/C/R、当前业务基线回退与回调排空合同；`.trellis/spec/backend/database-guidelines.md:88` 起的读取会话、`:199` 起的派生事实和双表重建合同。

### 8. 外部参考及版本

本轮没有联网；仅核对既有研究所引用的官方资料名称与其版本适用范围，没有刷新官方页面：

- `R/production-execution-plan.md:257`–`:260`：MySQL 8.4 `mysqldump`、`server_uuid`、Docker volume、Redis persistence 官方文档；现场原记录为 MySQL 8.4.9、Redis 7.4.9。
- 同文件 `:237`：Docker stop、Celery worker shutdown；仓库锁定 Celery 5.6.3。
- `.trellis/spec/backend/document-job-list-query-v2.md:97`：Docker 容器运行约束、Linux capabilities 语义；静态文档不能替代现场只读挂载/能力检查。

## Caveats / Not Found

- 本轮没有运行 Git；初始 29 路径、HEAD、index 和 Spec 净差异来自主会话已经核对的基线。本报告创建后及主会话并行修改后的完整路径集合，以主会话最终 status/当前输入清单为准。
- 历史审批方案原文副本本轮未取得；当前方案与历史 SHA 失配已如实记录，未重算覆盖旧摘要，也未伪称已还原原审批文档。
- 无 SSH、网络、Docker、数据库、业务测试、运维测试或运维脚本执行；没有生产现状、远端原始报告、GitHub 状态或外部 URL 的新鲜验证。
- 敏感信息检查是对明确范围的明显内容核对，不证明任意编码、外部受限文件或新截图没有敏感信息；具体新截图由主会话视觉核对。
- 本研究仅新增此中文报告，没有修改既有脚本、manifest、review、Spec、任务状态或其他文件。没有需要改动产品或重跑既有成功验证的新发现。

## 2026-11-09 追加定向复核：新索引、提交计划与当前清单

- Query: 核对主会话整理后的 `T/ops-records-commit-plan.md`、`R/ops-materials-index.md`、`R/ops-materials-inventory.json`，以及直接关联的截图、Spec 与历史摘要状态入口。
- Scope: internal；沿用本报告授权边界，仅做本地读取、集合/摘要/链接及文件格式检查，追加本节；不运行 Git、业务/运维测试、运维脚本、网络或远端命令。
- Date: 2026-11-09

### 最终分组与批准边界

初审第 2 节的 21+8 是当时建议，**本次以主会话形成的 16+19、合计 35 路径计划为最新方案**；原建议保留用于说明审计过程，不再作为最终待提交清单。

- 第一批 16 项为载体、6 文件冻结清单、窗口快照、独立审查、就绪研究和共享 Spec。
- 第二批 19 项把构建/审批 4 份文档与切换方案、最终生产验收、任务记录、本轮索引/审计/输入清单和截图放在同一提交，便于共同审阅时间线。`release-ops-manifest.json` 仍在第一批。
- 35 路径是在初始 29 个差异基础上，增加本轮 5 个新材料文件，以及此前未变的 `R/verification-summary.md` 的历史入口修改；不是新增 35 个文件。
- 直接抽取计划两段路径块，与输入清单的 `commits[].paths` **逐项、按顺序一致**：16/16、19/19，合计 35 个唯一文件全部存在，无重复或跨组重叠。
- `T/ops-records-commit-plan.md:3`、`:10`、`:81` 起明确待批准、尚未 stage/commit/push、获批后才创建新记录分支及逐路径提交；旧产品提交许可不扩展为本批许可。未把分支创建、提交或归档写成已执行。
- 计划第 43 行原先多计构建/审批材料的措辞已由主会话纠正为不含错误数量的描述；实际路径分组始终是 16+19。

### 状态与历史证据闭环

- `.trellis/spec/backend/document-job-list-query-v2.md:99` 已明确 2026-11-06 设计、2026-11-07 验收；`:107` 引用实际执行记录，并保留未来生产操作单独授权。初审第 6 节第 1 项已关闭。
- `R/verification-summary.md:1`、`:3` 已明确历史记录及最终结果链接；原用例数、计时、失败修复和当时尚未部署描述仍保留。初审第 6 节第 2 项已关闭。
- `R/ops-materials-index.md:18`–`:38` 把构建/审批、原冻结 README、阶段 review 与最终验收分开说明，保留历史 false、审批文档 3/4 匹配及原审批正文未取得的边界；没有通过重算历史 manifest 隐去差异。
- 索引 `:55`、`:57` 保留最终采样与首次/测量上界试验的区别，以及浏览器早于截止、主机收尾晚于截止的时间语义。未冒称 11 月 9 日重新验收或重新探测生产。
- 新索引及计划没有把已有离线、真实引擎、镜像导入、静态复核和生产历史结果混为本轮新执行。原 111 与补充 37 项仍分开说明。

### 截图格式与链接闭环

本轮发现初始新副本 `R/production-acceptance.png` 的字节实际为 **JPEG/JFIF、1200×500**，PNG 扩展名不符。主会话已仅将本地副本重命名为 `R/production-acceptance.jpg`，同步计划、索引、输入清单及 `T/production-execution.md:50` 的链接；未转码或修改图片字节，原外部文件保持不变。

直接复核结果：JPEG 签名字节正确；当前 SHA-256 仍为 `19fbc282a12488c928895420948794d758a699a2c1d04079e166692e2f67ee3b`，与主会话提供的原图 SHA 相同；旧本地 `.png` 副本已不存在。该格式问题已关闭。截图视觉内容由主会话核对为页头/统计，无凭据或业务文件名；本研究核对格式、字节身份及引用，没有重新进行浏览器验收。

对最终计划、索引、生产执行记录、历史验证摘要及相关 Spec 的 Markdown 相对链接做本地存在性检查，未发现断链；两份路径清单都引用 `.jpg`。新文档及相关修订文件末尾换行和行尾空白检查未发现问题。外部 URL 不在本次检查范围。

### 当前输入清单的最后边界

`R/ops-materials-inventory.json` 可解析，`status=plan_pending_approval`、基线与拟议分支和计划一致，显式声明排除清单自身，以避免循环哈希。本研究最后读取时 `content_hashes` 仍为有意保留的空草稿，**尚不能宣称 34 项当前内容摘要已经完整或核验通过**。

主会话将于本报告最终落盘后一次性填入其余 **34 个文件**的 SHA/字节数并做本地一致性检查。该写入及核验由主会话完成，不由本报告提前代写通过。本次追加完成后，本研究不再修改报告，便于主会话冻结当前输入。

定向复核没有尚待修复的明确文档或路径问题；最后剩余工作仅为上述已计划的清单内容填充和主会话最终检查。没有形成需要产品修改、重复测试、重跑运维载体或访问生产的新发现。
