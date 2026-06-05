# Proposal Review Queue MySQL E2E Smoke

## Goal

把本地已提交的 proposal review queue 最新代码部署到真实线上 MySQL 环境，并补一次真实后端联调 smoke。

本任务只验证 proposal 审核队列增强，不触发 pdf-mineru 解析、翻译或 Word 生成主流程。

## Requirements

- 读取现有部署文档、compose 配置和服务器连接信息，确认 hostdzire / dmit 分工。
- 将本地最新业务代码部署到 hostdzire 的 `/root/md2word`。
- 重新构建并启动生产 Docker Compose，保持 MySQL/Redis 数据 volume，不执行 `down -v`。
- 检查 hostdzire 上的 Docker Compose、nginx、MySQL readiness。
- 必要时只读检查 dmit 的 WireGuard/nginx/firewall 转发状态，不做破坏性防火墙调整。
- 使用真实线上 API + MySQL backend 做 proposal review queue E2E smoke：
  - 登录 admin。
  - 创建或准备 Term Rule Proposal 与 Translation Term Proposal 测试数据。
  - 验证 Term Rule bulk approve / bulk reject partial success。
  - 验证 Translation bulk approve / bulk reject partial success。
  - 验证审核页到治理页 CTA 和治理页回跳审核页。
- 修复真实 MySQL 环境中 Term Rule legacy category store 与 Term Rule Set draft category store 不一致导致 Term Rule Proposal create-to-approve 断链的问题。
- 不在最终报告中输出服务器账号、密码、私钥、token 或完整敏感配置。

## Acceptance Criteria

- [x] 生产 compose 已使用最新代码重建并启动。
- [x] `/api/v1/health/live` 与 `/api/v1/health/ready` 可访问；ready 若有非本任务 blocker，需明确记录。
- [x] 真实 MySQL backend 下 Term Rule proposal bulk 审核 smoke 通过。
- [x] Term Rule Proposal 创建、审核和前端 category 下拉统一使用 Term Rule Set draft 的 category 语义，不依赖 legacy store 同步状态。
- [x] 真实 MySQL backend 下 Translation Term proposal bulk 审核 smoke 通过。
- [x] 治理页联动和回跳在真实页面通过。
- [x] smoke 不触发 pdf-mineru / 翻译 / Word 生成主流程。
- [x] 不执行真实文件删除或 Docker volume 删除。

## Notes

- 部署主机：hostdzire。
- 前置机：dmit。
- 参考文档：`docs/deploy/hostdzire-dmit-md2word.md`、`docs/deploy/p0-docker-deployment.md`。
