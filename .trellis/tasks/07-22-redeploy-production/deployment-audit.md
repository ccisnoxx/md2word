# 生产部署审计

## 执行摘要

- 执行时间：2026-07-22 15:39–15:54（Asia/Shanghai）
- 目标提交：`0806832418648542eae31642f2c6a6e005aa5a38`
- `origin/main`：与目标提交一致，且包含 `b249790d` 与 `06e2e7da`
- 目标后端 release：`/root/md2word-releases/0806832`
- 目标前端 release：`/var/www/md2word-frontend/releases/0806832-20260722T073911Z`
- 原后端 release：`/root/md2word-releases/cc5896f`
- 原前端 release：`/var/www/md2word-frontend/releases/cc5896f-20260711T042700Z`
- 最终结论：目标后端通过运行时门禁，但模板版本 hash 合同失败；已回滚后端，前端未切换，生产恢复原版本。

## 发布准备证据

- SSH alias `hostdzire` 连接和只读 probe 通过，无主机指纹冲突。
- 远端 bare repo 已包含目标完整 SHA，目标 release 由该提交导出。
- 目标 release 不包含 `.git`、`.idea`、`.codex`、`.agents`、`.trellis`、`.run`。
- 目标关键 schema 文件与 bare repo 中目标提交内容一致。
- 目标 release 已复用现有忽略配置，并把非敏感发布标识更新为 `0806832` 批次。
- 前端目标 release 已从同一提交的生产构建产物准备完成；切换前一直保留原 `current` symlink。
- Docker Compose、nginx、磁盘空间和 MySQL/Redis 基础状态均通过预检。

## 目标后端门禁

- API/Worker 使用 `/root/md2word-releases/0806832` 与目标镜像启动成功。
- 内网 `live/ready/metrics`：通过。
- 运行版本：`0806832`。
- `deployment_init_ready=true`、`p0_document_jobs_ready=true`。
- metadata：MySQL；Worker：Celery；翻译批次队列：`document-translation-batches`。
- `readiness_blockers=[]`、`p0_document_jobs_blockers=[]`。
- API/Worker 启动日志无启动错误；仅观察到既有 Starlette 弃用警告。
- 生产镜像 `check_release.py --runtime-url`：通过，36 个目标、182 个测试通过。
- Golden Sample preflight：通过；4 个 manifest 样本齐全，admin token 鉴权与运行时基线通过，未创建转换任务。

## 阻塞项

admin-only `GET /api/v1/templates/default/layout-config` 返回 `400`：

```text
模板版式配置 hash 不匹配: default@1
```

根因是生产 MySQL 已把 `default@1` 的旧 YAML hash 固化为不可变版本，而目标提交在 manifest 仍默认为 version 1、路径仍为 `resources/template_configs/datasheet_template.yaml` 的情况下修改了该文件内容。严格 hash 校验按设计失败，不能通过忽略 hash 或覆盖历史记录继续上线。

目标前端因此未切换，公网仍持续提供原前端 release。

## 回滚证据

- 在旧后端 release `cc5896f` 重新执行 Compose build，恢复共享 `md2word-p0:latest`。
- 强制重建旧 API/Worker；未执行 `down -v`，未删除 MySQL、Redis、应用 volume、目标 release 或失败证据。
- 回滚后 API 容器工作目录恢复为 `/root/md2word-releases/cc5896f/docker/prod`。
- 内网 `ready=ok`，运行版本 `cc5896f`，P0 门禁通过且无 blocker。
- 公网 `live=ok`、`ready=ok`，公网版本 `cc5896f`。
- 旧版 admin layout-config 接口恢复 `200`。
- 前端 `current` 始终指向 `cc5896f-20260711T042700Z`，无需执行前端回滚。

## 后续决策门禁

继续上线需要先修复 seed 版本合同：保留 `default@1` 对应的旧 YAML 内容和路径，把多文种字体 seed 作为新的不可变模板版本登记，并通过明确获批的默认版本切换启用。不得修改既有 published v1 payload/hash，也不得加入跳过 hash 的兼容分支。
