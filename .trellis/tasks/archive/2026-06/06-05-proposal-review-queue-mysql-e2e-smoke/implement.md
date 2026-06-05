# Proposal Review Queue MySQL E2E Smoke Implementation Plan

## Gate

当前 task 已通过 `task.py start` 进入 `in_progress`。本轮先修复阻断真实 MySQL smoke 的 Term Rule category 双存储缺陷，再完成真实页面 E2E smoke。

## Execution Log

- 2026-06-05: 确认 active task 为 `.trellis/tasks/06-05-proposal-review-queue-mysql-e2e-smoke`，业务代码 HEAD 为 `8c5f797`。
- 2026-06-05: hostdzire 通过 tar-over-SSH 覆盖同步最新业务代码；保留远端 `.env` 和 `deploy/auth_internal_users.json`，未删除 Docker volume 或真实文件。
- 2026-06-05: hostdzire 执行 `docker compose --env-file .env -f docker/prod/docker-compose.yml build && docker compose --env-file .env -f docker/prod/docker-compose.yml up -d`，API/worker 重新创建，MySQL/Redis 保持原 volume 并 healthy。
- 2026-06-05: 本地执行 `npm run build` 通过；上传 `frontend/dist` 到 `/var/www/md2word-frontend/releases/20260605T025549Z/dist` 并切换 `current` symlink，`nginx -t` 与 reload 成功。
- 2026-06-05: 公网 `https://md2word.962850.xyz/` 返回 200，静态资源为 `index-DzO05rHE.js` / `index-C_maKYtn.css`。
- 2026-06-05: 公网 `/api/v1/health/ready` 返回 ok，`effective_repository_backend=mysql`、`stage_message_store=mysql`、`readiness_blockers=[]`。
- 2026-06-05: 通过远端 API 容器生成短期 admin JWT，用于 smoke 调用；token 只写入本地临时文件，未回显。
- 2026-06-05: 真实 API/MySQL smoke run `20260605T03128856` 完成：
  - Term Rule `bulk-approve`: 真实线上数据阻断，`total=1/succeeded=0/failed=1`，失败 proposal 保持 `pending_review`。
  - Term Rule `bulk-reject`: `total=2/succeeded=1/failed=1`，已拒绝失败项保持 `rejected`。
  - Translation `bulk-approve`: `total=2/succeeded=1/failed=1`，失败项为 `translation_term_proposal_conflict`，proposal 保持 `pending`。
  - Translation `bulk-reject`: `total=2/succeeded=1/failed=1`，已拒绝失败项保持 `rejected`。
  - Translation Term Set proposal compatibility 返回 `compatibility=conflict`。
- 2026-06-05: 真实环境发现 Term Rule legacy category 与 Term Rule Set draft category 不一致：legacy category count `15`，draft category count `1`，intersection `0`。这会阻断 Term Rule Proposal create-to-approve 正向路径，属于线上数据/双存储同步问题，不在 smoke 中绕过。
- 2026-06-05: Browser 打开公网前端正常重定向到 `/login`；由于没有应用明文密码，尝试通过同域 token 写入完成登录态被 Browser 安全策略阻止，未继续绕过。真实浏览器交互闭环仍需应用登录密码，或用户明确允许创建临时 smoke admin 账号并重启 API。
- 2026-06-05: 本轮生成的本地临时 JWT 和 SSH key 副本已清理；源凭据文件未修改。
- 2026-06-05: 用户提供应用 admin/operator 登录账号密码，允许继续真实浏览器登录 smoke；敏感值不写入文档或最终报告。
- 2026-06-05: 将 task 范围扩展为修复 Term Rule category 双存储缺陷：proposal 入口与 category API 统一使用 Term Rule Set draft 语义，不做线上手工数据迁移。
- 2026-06-05: 修复 Term Rule category 双存储缺陷：
  - `TermRuleProposalService.create_proposal` 改为以目标 Term Rule Set draft store 校验 category 和 target rule snapshot。
  - `/api/v1/term-rule-categories` 在版本化服务可用时返回 `electronics-default` draft categories。
  - `TermProposalsPage` 的 Term Rule proposal 表单改为从 draft rules 加载 target rule 候选。
- 2026-06-05: 本地最小验证通过：
  - `python -m unittest` 覆盖 Term Rule category drift、bulk approve partial conflict、bulk reject partial preserve。
  - `python -m unittest` 扩展覆盖 7 个 Term Rule Set / Term Rule Proposal 相关用例。
  - `npm run build` 通过；保留既有 Rollup pure annotation 和 chunk-size warning。
- 2026-06-05: hostdzire 重新同步修复后代码，执行生产 compose build/up，API/worker 重新创建，MySQL/Redis volume 保持不变。
- 2026-06-05: 上传修复后前端 `dist` 到 `/var/www/md2word-frontend/releases/20260605T034103Z/dist` 并切换 `current` symlink，`nginx -t` 与 reload 成功。
- 2026-06-05: hostdzire compose `ps` 显示 API healthy，公网 `/api/v1/health/ready` 返回 ok；`effective_repository_backend=mysql`、`stage_message_store=mysql`、`readiness_blockers=[]`。
- 2026-06-05: 真实 API/MySQL smoke run `20260605T034353Z` 通过：
  - Term Rule `bulk-approve`: `total=2/succeeded=1/failed=1`，失败项为 `term_rule_proposal_conflict`，失败 proposal 保持 `pending_review`。
  - Term Rule `bulk-reject`: `total=2/succeeded=1/failed=1`，已拒绝失败项保持 `rejected`。
  - Translation `bulk-approve`: `total=2/succeeded=1/failed=1`，失败项为 `translation_term_proposal_conflict`，失败 proposal 保持 `pending`。
  - Translation `bulk-reject`: `total=2/succeeded=1/failed=1`，已拒绝失败项保持 `rejected`。
  - Translation Term Set proposal compatibility 返回目标 proposal `compatibility=conflict`。
- 2026-06-05: 真实浏览器页面 smoke 通过：
  - 通过公网 `/login` 使用真实 admin 表单登录，进入 `/jobs`，未使用 token 注入。
  - Term Rule review tab：批量 Approve 成功 `2/0/2`，两条 proposal 从 pending 列表消失。
  - Term Rule review tab：批量 Reject 成功 `2/0/2`，两条 proposal 从 pending 列表消失。
  - Term Rule conflict proposal 详情可打开治理上下文；`/settings/term-rule-sets` URL 携带 `set_id/proposal_id/source_term/return_tab`，banner 和返回按钮可见，返回到 `term-proposals?tab=review&proposal_id=...`。
  - Translation review tab：批量 Approve 成功 `2/0/2`，两条 proposal 从 pending 列表消失。
  - Translation review tab：批量 Reject 成功 `2/0/2`，两条 proposal 从 pending 列表消失。
  - Translation conflict proposal 详情可打开治理上下文；`/settings/translation-term-sets` URL 携带 `set_id/proposal_id/observed_version/return_tab`，banner、返回按钮和 compatibility conflict 可见，返回到 `term-proposals?tab=translation-review&proposal_id=...`。
- 2026-06-05: 补齐代码注释/类型后再次同步 hostdzire 并重建 API/worker；首次 ready 请求发生在 API `health: starting` 阶段返回连接重置，等待后重试通过，compose 显示 API healthy，公网 ready 仍为 ok。

## Current Blocker

- 无当前 blocker。
- 已确认 Term Rule approve 正向路径不再受 legacy category store 与 draft category store 不一致阻断。
- 浏览器 UI smoke 已通过真实登录表单完成，不再依赖 token 注入绕过。

## Checklist

1. Local preflight
   - 确认工作区干净或仅含本 task 文档。
   - 确认最新业务 commit 在本地。
   - 读取服务器连接信息但不回显敏感值。

2. Server discovery
   - 连接 hostdzire，确认 `/root/md2word`、git 状态、compose 服务、nginx 配置、MySQL readiness。
   - 连接 dmit，只读检查 WireGuard/nginx/firewall 转发状态。

3. Deploy latest code
   - 将本地最新代码同步到 hostdzire。
   - 保留 hostdzire `.env` 和 `deploy/auth_internal_users.json`。
   - 执行生产 compose build/up。

4. Health verification
   - 检查 compose `ps`。
   - 检查 API `/health/live` 和 `/health/ready`。
   - 检查公网域名可访问。

5. Real MySQL E2E smoke
   - [x] admin 登录。
   - [x] 创建或准备 Term Rule Proposal 测试数据。
   - [x] 验证 Term Rule bulk approve/reject partial success。
   - [x] 创建或准备 Translation Term Proposal 测试数据。
   - [x] 验证 Translation bulk approve/reject partial success。
   - [x] 验证治理页 CTA 和回跳。

5a. Term Rule category blocker fix
   - [x] `TermRuleProposalService.create_proposal` 改用目标 Term Rule Set draft store 校验 category 和 target rule。
   - [x] `/term-rule-categories` 在 Term Rule Set 服务可用时返回 default draft categories。
   - [x] 补最小后端回归测试覆盖 legacy/draft category 不一致时 create-to-approve 成功。

6. Cleanup and report
   - [x] 不删除真实文件或 Docker volume。
   - [x] 可保留已审核 smoke proposal 作为 audit 记录；如需清理，只做非破坏性标记或后续单独任务。
   - [x] 记录验证结论、失败项和 residual risk。

## Validation Commands

- hostdzire: `docker compose --env-file .env -f docker/prod/docker-compose.yml ps`
- hostdzire: `curl -sS http://127.0.0.1:18000/api/v1/health/live`
- hostdzire: `curl -sS http://127.0.0.1:18000/api/v1/health/ready`
- local/browser: real page smoke against `https://md2word.962850.xyz`

实际已运行：

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_uses_draft_categories_when_legacy_store_diverges tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_approve_partial_success_and_conflict tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_reject_partial_success_preserves_failed_item`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_set_draft_rule_crud_only_mutates_draft tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_set_draft_rule_crud_auth_backend_and_validation_errors tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposals_persist_and_approve_into_draft tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_update_disable_snapshots_and_reject_reason tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_approve_partial_success_and_conflict tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_uses_draft_categories_when_legacy_store_diverges tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_reject_partial_success_preserves_failed_item`
- `cd frontend && npm run build`
- hostdzire: `docker compose --env-file .env -f docker/prod/docker-compose.yml build && docker compose --env-file .env -f docker/prod/docker-compose.yml up -d`
- hostdzire: `docker compose --env-file .env -f docker/prod/docker-compose.yml ps`
- hostdzire: `curl -sS http://127.0.0.1:18000/api/v1/health/ready`
- local: `curl -k -sS https://md2word.962850.xyz/api/v1/health/ready`
- local/browser: real UI smoke against `https://md2word.962850.xyz/login` and proposal governance pages.

## Explicitly Out Of Scope

- 不触发 pdf-mineru 解析、翻译或 Word 生成。
- 不执行 `docker compose down -v`。
- 不删除服务器文件、MySQL 数据、Docker volume、证书或 nginx 配置。
- 不修改 dmit 转发配置，除非发现线上不可达且用户另行确认。
