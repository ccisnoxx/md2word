---
doc_type: refactor-scan
refactor: 2026-05-31-project-directory-restructure
status: pending-user-selection
scope: repository root layout, versioned resources, runtime state, tests/docs/deploy layout, app package boundaries, and persistence adapters
summary: 9 structural findings; structure 9 / performance 0 / readability 0
---

# project-directory-restructure scan

## 总览

- 扫描范围：仓库根目录、`app/`、`scripts/`、`docs/`、`tests/`、`deploy/`、`docker/`、`template/`、`template_configs/`、`prompt/`、`data/`
- 发现 9 条优化点：结构 9 / 性能 0 / 可读性 0
- 按风险：低 2 / 中 4 / 高 3
- 建议先做：#1 #2 #3 #4（根目录、资源、运行态、测试资产边界清晰，能为后续 app 迁移降噪）
- 建议慎做 / 后做：#6 #7 #8 #9（涉及 domain-first、persistence 和 core/schema 边界，必须拆阶段验证）
- 前置检查：第 3 条“跨模块问题”和第 6 条“范围太大”命中；本 scan 不能直接作为单次 apply 清单，必须进入 staged design。

## 条目

### #1 把本地运行入口迁到 scripts/dev

- **位置**：`run_api.py`、`run_worker.py`、`run_document_worker.py`、`scripts/`
- **分类**：结构
- **现状**：3 个本地进程入口直接散在仓库根目录，`scripts/ops/` 只承载运维脚本。
- **问题**：根目录已有 17 个顶层项目/文件入口；运行入口与 README、配置、资源目录混在同一级，且当前规范把旧布局当目标状态。
- **建议**：新增 `scripts/dev/`，把开发直跑入口迁为 `scripts/dev/run_api.py`、`scripts/dev/run_stage_worker.py`、`scripts/dev/run_document_worker.py`，同步更新文档和 IDE 运行说明，不保留根目录 shim。
- **建议映射的方法**：M-L3-06（Layer Rectification 分层纠偏）
- **风险**：中（会影响本地命令、文档和可能存在的 IDE 配置）
- **验证**：AI 自证（导入 `scripts.dev.run_api` / `scripts.dev.run_stage_worker` / `scripts.dev.run_document_worker`，并运行最小启动导入测试）
- **范围**：约 3-8 文件

### #2 把根级 conversion config 迁入 app/conversion

- **位置**：`config.py`、`app/conversion/runtime_runner.py`、`app/conversion/runtime/llm_client.py`
- **分类**：结构
- **现状**：根目录 `config.py` 只被 conversion runtime 使用，但文件名像全局配置；后端全局配置已经在 `app/core/config.py`。
- **问题**：同仓库存在两个配置入口，`config.py` 与 `app/core/config.py` 语义冲突；调用点集中在 2 个 conversion 模块和 1 个测试，说明它不是全局 root 模块。
- **建议**：将 `config.py` 移为 `app/conversion/runtime_config.py`，所有调用改为包内导入；根目录不保留 re-export。
- **建议映射的方法**：M-L2-04（Move Function 搬移函数）
- **风险**：低（调用点少，测试可直接覆盖）
- **验证**：AI 自证（跑 `tests.test_llm_client_characterization` 和 conversion runtime 相关 characterization tests）
- **范围**：约 4 文件

### #3 把版本化资源收敛到 resources

- **位置**：`template/`、`template_configs/`、`prompt/`、`app/core/config.py`、`app/conversion/runtime_helpers.py`、`app/conversion/runtime/llm_client.py`
- **分类**：结构
- **现状**：DOCX 模板、模板 YAML、术语 YAML/CSV 和翻译 prompt 分散在 3 个根目录。
- **问题**：版本化输入资产和根目录入口并列；`app/core/config.py` 至少有 7 个默认路径指向旧资源目录，测试和文档也直接引用旧路径。
- **建议**：建立 `resources/`，按 `templates/`、`template_configs/`、`term_rules/`、`prompts/` 分桶；更新默认路径、测试 manifest 和文档引用，不保留旧路径 fallback。
- **建议映射的方法**：M-L3-06（Layer Rectification 分层纠偏）
- **风险**：中（路径引用多，容易漏测试/文档/manifest）
- **验证**：AI 自证（`rg "template_configs|template/|prompt/"` 无非归档旧引用；跑资源配置、模板、术语、LLM prompt 相关测试）
- **范围**：约 15-30 文件

### #4 把运行态 data 改为 var

- **位置**：`data/`、`.gitignore`、`.dockerignore`、`app/core/config.py`、deploy/docker/docs/tests 中的运行态路径
- **分类**：结构
- **现状**：本地运行态目录叫 `data/`，包含 `config/`、`jobs/`、`stage_messages/`、`tmp/`、metadata/object artifacts 等可变状态。
- **问题**：`data/` 容易与版本化样例数据和业务输入资产混淆；当前 `.gitignore` 忽略 `data/`，但代码默认值和文档大量引用 `data/`。
- **建议**：将运行态根改为 `var/`，目标子目录为 `var/config/`、`var/jobs/`、`var/stage_messages/`、`var/tmp/`、`var/object_artifacts/`、`var/metadata.sqlite3`；同步更新 ignore、默认配置、docker volume 文档和测试。
- **建议映射的方法**：M-L3-06（Layer Rectification 分层纠偏）
- **风险**：中（运行态路径多，涉及本地开发、Docker 和健康检查）
- **验证**：AI 自证（运行 backend config/path tests、health tests、local file storage integrity tests；`rg "data/"` 只剩历史归档或明确示例）
- **范围**：约 12-25 文件

### #5 把测试样例迁到 tests/fixtures

- **位置**：`tests/golden_samples/`、`tests/p1_translation_samples/`、`tests/.tmp/`、`scripts/ops/run_golden_sample_regression.py`
- **分类**：结构
- **现状**：测试代码和样例资产同级；临时目录使用隐藏的 `tests/.tmp`。
- **问题**：测试资产目录有 2 个顶层样例包，manifest 中硬编码旧路径；脚本默认值也引用 `tests/golden_samples`。
- **建议**：迁移为 `tests/fixtures/golden_samples/`、`tests/fixtures/p1_translation_samples/` 和 `tests/tmp/`，同步更新 manifest、测试和回归脚本默认路径。
- **建议映射的方法**：M-L3-06（Layer Rectification 分层纠偏）
- **风险**：低（路径集中，测试可直接覆盖）
- **验证**：AI 自证（跑 `tests.test_golden_sample_manifest`、`tests.test_p1_translation_sample_manifest`，检查 regression 脚本导入）
- **范围**：约 6-10 文件

### #6 分离当前文档和历史规划文档

- **位置**：`docs/`
- **分类**：结构
- **现状**：`docs/api/`、`docs/dev/`、`docs/deploy/`、`docs/testing/` 与 `docs/planning/`、`docs/runbook.md` 混在当前文档树下。
- **问题**：`docs/planning/` 记录的是过去 PRD/技术草案，与当前可执行指南并列；`docs/runbook.md` 是当前运维文档但不在 runbooks 分类下。
- **建议**：保留 `docs/api/`、`docs/dev/`、`docs/deploy/`、`docs/testing/`；新增 `docs/runbooks/`；将历史规划迁入 `docs/archive/planning/`。
- **建议映射的方法**：M-L3-07（Single Responsibility Split 职责分离）
- **风险**：中（文档内部链接和路径引用需要批量校正）
- **验证**：AI 自证（`rg "docs/planning|docs/runbook.md"` 找出并更新当前引用；人工抽查 README/docs index）
- **范围**：约 8-20 文件

### #7 用 files 样板验证 domain-first app

- **位置**：`app/api/v1/routers/files.py`、`app/schemas/files.py`、`app/services/files/`、`app/core/file_models.py`、`app/repositories/protocols.py`
- **分类**：结构
- **现状**：files 资源横跨 API router、central schema、service package、core model 和 repository protocol。
- **问题**：一个业务域的类型和行为分布在至少 5 个技术层位置；这会放大新增字段或状态时的跨层跳转成本。
- **建议**：以 `app/domains/files/` 做第一条 domain-first 样板，收拢 `router.py`、`schemas.py`、`models.py`、`service.py`、`retention.py`、`validation.py` 和 repository port；`app/api/v1/router.py` 只 include domain router。
- **建议映射的方法**：M-L3-06（Layer Rectification 分层纠偏）
- **风险**：高（会改变大量 import，是 domain-first 能否成立的样板）
- **验证**：AI 自证（跑 files/document_jobs/API 相关测试；OpenAPI 导出比较 HTTP 合同）
- **范围**：约 8-15 文件

### #8 拆分 all-purpose repository adapters

- **位置**：`app/repositories/protocols.py`、`app/repositories/file_job_repository.py`、`app/repositories/database_job_repository.py`、`app/repositories/mysql_job_repository.py`
- **分类**：结构
- **现状**：protocols 已按端口细分，但 file/sqlite/mysql 三个 adapter 仍以 “JobRepository” 名义同时实现 jobs、files、document_jobs、stage messages、audit、resource versions 等多类端口。
- **问题**：`FileJobRepository` 单类超过 200 行，`DatabaseJobRepository` 超过 480 行，`MysqlJobRepository` 超过 650 行；一个后端 adapter 承担 6+ 个业务存储职责，命名也只表达 jobs。
- **建议**：设计 `app/infrastructure/persistence/{file,sqlite,mysql}/`，按 backend 分组、按 domain/port 分文件；domain 定义 repository port，infrastructure 实现具体 adapter 和 schema bootstrap。
- **建议映射的方法**：M-L3-05（Repository Extraction 仓储层抽取）
- **风险**：高（存储架构重写，涉及 schema 初始化、runtime wiring、测试 fake 和迁移脚本）
- **验证**：AI 自证（repository tests、metadata shadow copy tests、FastAPI integration tests；每个 backend adapter 可独立实例化）
- **范围**：约 15-35 文件

### #9 收窄 core 并消除 central schemas

- **位置**：`app/core/*_models.py`、`app/schemas/`、`app/services/*`、`app/api/v1/routers/*`
- **分类**：结构
- **现状**：`app/core/` 同时放真正基础配置和业务模型；`app/schemas/` 集中放所有 API contract，并通过 `api_v1.py` 做 re-export。
- **问题**：`job_models.py`、`document_job_models.py`、`file_models.py`、`template_models.py`、`translation_models.py` 等是业务域模型，不是 cross-domain core；central schemas 让 domain router 无法自包含。
- **建议**：`app/core/` 只保留 config/logging/errors 等基础能力；业务模型和 schemas 迁到 owning domain；最终删除 `app/schemas/`，不保留长期 facade。
- **建议映射的方法**：M-L3-07（Single Responsibility Split 职责分离）
- **风险**：高（跨全 app 的 import 迁移，需分 domain 阶段执行）
- **验证**：AI 自证（逐 domain 测试、全局 `rg "app.schemas|app.core.*_models"` 收敛检查、OpenAPI 导出比较）
- **范围**：约 30+ 文件，必须拆阶段
