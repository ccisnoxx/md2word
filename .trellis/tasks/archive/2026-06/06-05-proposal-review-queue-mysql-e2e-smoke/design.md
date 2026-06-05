# Proposal Review Queue MySQL E2E Smoke Design

## Deployment Shape

- `dmit` 作为公网前置机，通过 WireGuard / nginx stream 把 80/443 流量转发到 hostdzire。
- `hostdzire` 是实际部署机，目录为 `/root/md2word`。
- 生产服务由 `/root/md2word/docker/prod/docker-compose.yml` 管理。
- MySQL/Redis 使用 Docker volume，E2E smoke 不删除 volume。
- API 由 hostdzire 本机 nginx 反代到 Docker API 端口 `127.0.0.1:18000`。

## Deployment Strategy

1. 优先通过 git 或 rsync 把本地最新代码同步到 hostdzire。
2. 保留 hostdzire 上的 `.env` 与 `deploy/auth_internal_users.json`。
3. 在 hostdzire 执行生产 compose build/up：
   - `docker compose --env-file .env -f docker/prod/docker-compose.yml build`
   - `docker compose --env-file .env -f docker/prod/docker-compose.yml up -d`
4. 检查 compose、API health、nginx。
5. 只在必要时检查 dmit 的 WireGuard/nginx/firewall；不主动改转发规则。

## Smoke Strategy

优先使用真实浏览器访问公网域名完成 UI smoke。若浏览器自动化遇到登录态、选择器或外部网络限制，再使用真实 API 调用补充验证。

测试数据策略：

- 使用真实 MySQL backend 的 proposal API 创建临时 proposal。
- 不创建 document job，不上传 PDF，不触发主流程。
- bulk partial success 通过混合 pending proposal 和已审核 proposal 实现，避免依赖破坏现有 draft 的强冲突状态。
- governance linkage 通过已创建 proposal 的 `observed_*` query 跳转验证。

## Term Rule Category Store Fix

真实 MySQL 环境中存在两套 Term Rule category 来源：

- legacy runtime store：`TermRuleService` / `/term-rule-categories` / `/term-rules`
- versioned Term Rule Set draft：`TermRuleSetVersionService` / `/term-rule-sets/{set_id}/draft`

Proposal 审核最终写入 Term Rule Set draft，因此 proposal 创建、target snapshot 和审核前校验必须以 draft 为准。最小修复策略：

1. `TermRuleProposalService.create_proposal` 解析 `observed_term_rule_set_id` 后读取该 set 的 draft store。
2. create/update proposal 的 `category_id` 校验改为 draft store category。
3. update/disable proposal 的 `target_rule_id` 快照改为 draft store rule，避免 legacy `/term-rules` 与 draft rule id 不一致。
4. `/term-rule-categories` 在 `term_rule_set_version_service` 可用时返回 `DEFAULT_TERM_RULE_SET_ID` draft categories；只有 file/legacy 模式继续使用 `TermRuleService`。
5. 不做数据迁移、不手工修改线上 MySQL，不引入后台同步任务。

这保持 approve/reject/publish 语义不变，只修正 proposal 入口和审核目标不一致的问题。

## Safety

- 不输出服务器凭据。
- 不执行 `docker compose down -v`。
- 不删除服务器数据、证书、nginx 配置或防火墙规则。
- 不修改 `.env` 中真实密钥，除非发现缺少运行必需变量并获得单独确认。
