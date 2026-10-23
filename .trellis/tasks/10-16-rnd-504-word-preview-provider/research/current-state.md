# RND-504 当前调查与复用证据

2026-10-23，仅调查/规划。所有“当前”指 `/Users/sc/PycharmProjects/md2word`、分支 `md2word/RND-503`、HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`；历史源另标 SHA，不把其他分支实现当作当前代码。

## 1. 指令、文档和现有工作区

先执行 `pwd`、`git status --short`，读取根 AGENTS.md、`.trellis/workflow.md`、`/Users/sc/.codex/RTK.md`，加载 trellis-start/brainstorm。读取 guides、backend、frontend index；按本项需要检查数据库、错误、质量、模式/阶段、Word 输出与日志规范。项目中文文档/只规划/不 start/不提交/push 边界优先。

核对的产品/设计/实施真源：

| 文档 | 本项约束 |
|---|---|
| `docs/product/prd.md` | FR-012/013/015/016：只读预览、发布需有效预览、blocked/unreviewed 内部下载、Microsoft Word 验收。 |
| `docs/product/scope-and-decisions.md` | PD-001..020：一主 DOCX、direct 零 AI、唯一 MinerU、原生表格、四状态和非目标。 |
| `docs/implementation/implementation-plan.md` | 阶段 5 adapter/Artifact/可重试与 preview required；失败保留 DOCX 并阻断发布。 |
| `docs/implementation/codex-task-backlog.md` | RND-504 完整定义为可替换 provider、timeout/sandbox、Artifact、retry、IR 解耦；505/506 和 QA 任务职责另列。CON-104 已接受 D1 保留核心 eligible 与可执行 enabled 分离。 |
| `docs/implementation/codex-execution-guide.md` | 调查/复用优先、复杂三件套、最小 context、真实测试/兼容/迁移及评审门。 |
| `docs/implementation/codex-task-manifest.yaml` | 当前 RND-504=planning，CON-103=done；旧 RND-504 notes 与实际 Git 历史存在漂移，不能据其断言未实现。 |
| `docs/decisions/architecture-decisions.md` | ADR-001/002/003/004/010/012/015/016：模块化单体、唯一主件、IR 真源、发布不可变、preview 基建 port、二进制独立存储。 |
| `docs/contracts/document-ir-contract.md` | Provider、进程和 Word 专有策略不进入 IR；不改 v2 schema、block/order/source 或资产语义。 |
| `docs/design/docx-rendering-template-design.md` | §14 WordPreviewProvider：PDF/可选 PNG、页数/失败摘要；保留当前 RND-502/503 公式/图片合同。 |
| `docs/design/quality-review-release-design.md` | 预览失败 blocker、质量合成、批准/发布条件、预览失败审计；公开 preview/review/publish 属后续任务。 |
| `docs/engineering/testing-acceptance-strategy.md` | L1..L8、fake/组件/权限/并发/OpenAPI/样本/线上及人工分层；专有样本不入库。 |

父任务 `.trellis/tasks/10-12-datasheet-docx-delivery-quality` 的 task/prd/design/implement 已读取。父任务 status=planning，当前 children 中原未链接 RND-504；此次仅补当前子项，不改变父状态或其他子任务。

开始时工作区有大量既有 staged 删除和 dirty 文档（manifest/backlog、CON-104 prompt、工作日志、父任务、RND-501、.serena 等）。保护快照记录 350 个 porcelain -uall 路径，其中 296 个索引状态 D；主分支/HEAD、cached diff SHA-256、所有原 dirty 文件 hash、父 task 和 manifest 原字节保存在本次临时目录 `rnd504-planning-bv1bs4je`。该计数不把 status 的目录折叠项误当文件总数。没有 stash、删除、覆盖或提交这些改动。

## 2. 依赖与历史任务身份

- CON-103 当前 manifest done，resolution 为已实现/人工接受，非 skipped_existing。
- `git show 28a2239:<归档CON-103>/task.json` 给出 completed；completion.md 记录人工接受 `bd828da4e3a3025856afd758e0b0a686ff6ccb72` / `80b82dbc0bf388c97b4f5b8d8e6654625cad9186`、允许归档和保留真实 MySQL/部署 FS 未验门。
- `git merge-base --is-ancestor bd828da HEAD` 返回 1；当前代码已存在同等状态/复核/receipt 能力，但原提交不在祖先链。依赖准入为通过；实施前仍核对当前功能合同，不强制整体合入旧依赖树。
- 当前根、注册 worktree 与已知 worktree 目录均无 active RND-504；`git log --all -- app/services/preview` 找到 `931d2f6`，其父基线为已接受 CON-103 所在 `033cb61`；`48818e9` 归档旧任务到 `.trellis/tasks/archive/2026-10/10-16-rnd-504-word-preview-provider`。
- 归档 task/prd/validation 明确记录 2026-10-17 已人工验收，adapter_contract_ready=true、production_ready=false。源实现曾修复 metadata 不可确认误完成、成功复用未消费 key、UTF-16 活动内容预检绕过，最终复核接受。以上是 Git 原件中的历史证据，本轮未重新执行独立实现复核。
- 同一 ID/slug/父关系仍有效，故复用原 `10-16` 身份并恢复为当前规划目录，不 create 新 `10-23` 子任务。历史原字节在 research/history，含 accepted-task-metadata.json；当前授权字段已单独置 planning/未授权。
- 恢复 child 保留原 parent 后，`task.py add-subtask` 因 child 已有 parent 拒绝；核对脚本为无副作用拒绝，随后仅修复父 children 的单侧缺失，不解绑其他关系或修改脚本。

## 3. 当前代码定位与差距

| 当前路径/符号 | 已有行为与本项目标的差距 |
|---|---|
| `app/services/preview/` | 当前不存在。历史源已有 5 个文件，禁止重建另一套 port/执行协议。 |
| `app/domains/document_jobs/execution.py:_render_and_save_word`（3059）、`_finish_prepared_result`（3265） | 原质量检查→候选→receipt→物化/原件认证→completed；没有 preview。插入点只在选定原件重验之后、completed 前。 |
| `execution.py:_validate_render_result_file`（3315）、`_get_existing_result_file`（3434） | 当前公式和图片报告必须绑定原文件 IR/冻结输入；源旧文件不含后续认证，不能整文件覆盖。 |
| `models.py:DocumentJobRecord`（123） / `delivery_state.py` | 四状态和 summary、approved/ready/published 校验；没有 word_preview_state。 |
| `result_state.py:patched_job`（65） | 当前锁内从 winner receipt 合并公式摘要、fallback 仅 passed→warning。源质量合成需要适配这段，不能吞 warning 或把自身 blocker 存成基础 blocker。 |
| `service.py:_build_publish_action`（2034附近） | CON-104 D1：eligible 核心资格；enabled=false，preview/publication 未接通原因。预览接入不自动启用发布。 |
| `service.py` / `router.py` files/download | owner/Admin、tenant/company、临时 Token、classification/warning 和审计已存在；新预览需严格当前 manifest 引用，不能复用宽泛 generation fallback。 |
| `files/models.py:DocumentFileType`（12） | 无三个 word_preview 类型。公开 response 的文件类型为 string，不意味着内部 Literal 可不更新。 |
| `files/service.py:register_generated_content`（378）、`_generated_object_key_for`（802） | 当前共享对象键已包含 file_id，支持重复同名生成件独立内容；新 preview 要接 metadata-first，不移入旧 source 的 preview 特例路径。 |
| `files/result_registration.py` | 已有 result candidate、不可变 descriptor、过期/删除规则；源新增 preview marker 只扩展这类内部 pending。 |
| `repository.py` 和三 document_jobs adapter | 当前有 TR-406 的批次树/lease/CAS、CON-103 复核/质量投影；没有 preview 窄 claim/finish。现有原子边界不能退化。 |
| `app/core/config.py`, `runtime.py`, `app/main.py` | 当前无 preview Settings/注入；源已有默认 disabled 实现。 |
| `scripts/dev/run_local_mineru_quality_matrix.py:build_visual_qa_evidence`（538附近） | 生成 LibreOffice+Poppler 外部 render_docx.py 命令和人工检查说明，不登记业务 preview Artifact，也没有任务重试/沙箱合同。 |
| `tests/` | 当前有 delivery/download/identity/execution/receipt/retention 等测试；源三个 preview 模块不存在。新集成不能只跑旧源测试。 |
| MySQL/SQLite schema | document_jobs 的四字段投影及 payload、document_files payload；无 preview 强类型表/列要求，本项不需要 DDL/backfill。 |

## 4. 复用清单与必要适配

`integration-inventory.json` 按源提交 37 个实际变化路径保存 source、source parent、当前 HEAD 的 Git blob；当前 absent 12 个（8 个业务模块、3 个测试模块、1 个 preview Spec），已有 25 个。它是只读比较，不是应用补丁或合并成功证明。

必须保留的较新 owner：

- CON-104 action/download classification/reason_code/审计，不混入 source 的旧 service/router 全文。
- TR-406 翻译批次方法/条件提交与共享锁，不用源旧 repository/adapter 替换。
- RND-502 锁内公式摘要、受控 fallback、receipt 与三恢复入口；RND-503 图片认证/冻结输入/原件读取。
- 当前所有生成件 file_id 唯一 key；只接 preview metadata-first/lifecycle，不改变已完成共享身份修复。
- 当前 event/公开文件 evidence 白名单；历史 source 的自由 metadata/object_key 展开不能恢复到普通事件。

不存在必须扩张产品范围的设计冲突；新生产依赖不能从本机可执行文件推断授权。规划按已接受端口和 disabled adapter 完成，真实启用保持另门。

## 5. 本轮实际检查

### 当前目标基线

cwd 为仓库根，使用当前 `.venv/bin/python`，`PYTHONDONTWRITEBYTECODE=1`：

```text
python -m unittest tests.test_document_job_delivery_state tests.test_document_job_download_availability tests.test_generated_artifact_identity
Ran 22 tests in 0.416s — OK
```

验证现有状态/批准/下载分类/不可变生成件相关基线，不是当前预览验收。未运行完整 execution、release、前端或线上套件；本次未改业务，源/目标接口差异已明确，无需以全量门禁代替规划。

### 已接受源的只读快照

由 `git archive 931d2f6 app tests resources scripts sitecustomize.py requirements.txt` 提取到本次临时目录的 source-931d2f6；不写当前业务路径，不复制 .env/客户样本。测试 cwd 和 PYTHONPATH 明确指向该快照，解释器为现有仓库 venv。

```text
python -m unittest tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence
Ran 40 tests in 23.636s — OK
```

包含生产 adapter→tests-only 子进程协议、正式最小 DOCX fake 应用、真实 file/SQLite 与 fake MySQL 合同；错误日志是故障注入预期，不是隐藏失败。没有真实 Office 排版、SaaS、MinerU/AI/生产存储外呼或部署；TestClient 临时 fixture 不是线上服务。

### 只读环境观察

`shutil.which` 发现 `/opt/homebrew/bin/soffice`、`pdftoppm` 和 `docker`，另有 `/Applications/LibreOffice.app`；bwrap/mutool 未找到。只查路径，没有启动、查询版本、拉镜像、安装或切换依赖。生产 Docker/env 示例未定义 preview 配置或批准隔离引擎；不能据此推断部署可用。

## 6. 结论与证据限制

现有源实现可复用，当前目标尚不满足验收；本轮规划是复用集成与验证收口，非从零建设，也非当前已完整满足后的 skipped_existing。源历史验收不等于本次当前集成验收。尚无当前业务候选，因此本轮不安排独立实际 diff 复核，后续候选须按 implement.md 执行。

真实 engine/validator/fonts/sandbox、真实 MySQL/InnoDB/部署 FS/S3、线上 Golden、Microsoft Word 人工视觉和生产回退未在本轮验证。它们是启用/交付证据门，不因本地 tests-only 成功而变 ready。当前没有真实 publish API，不能称“发布 E2E 已过”；CON-104 disabled 和 blocked 批准拒绝才是可核对的当前边界。
