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

## 第二次发布：不可变 seed v2

### 执行摘要

- 执行时间：2026-07-22 16:25–16:31（Asia/Shanghai）。
- 目标提交与 `origin/main`：`13b6a65b1081c5953d2276146808ce6dbd67b2b1`。
- 后端 release：`/root/md2word-releases/13b6a65`。
- 前端 release：`/var/www/md2word-frontend/releases/13b6a65-20260722T082535Z`。
- 原后端/前端回滚点仍为 `cc5896f` 批次；第一次失败 release 和证据均未覆盖或删除。
- 最终结论：后端、默认模板版本和前端均已切换到目标批次，生产默认模板为 `default@2`。

### 发布与运行时门禁

- `git ls-remote`、远端 bare repo 和 Git archive 均锁定目标完整 SHA；release 未包含开发目录。
- v1 YAML SHA-256 为 `1a9ce13488a491367fbfde8d143d22b6cf7c0ce064c99c224ae09ef93f5b3818`；v2 为 `132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d`；manifest 显式绑定 version 2。
- API/Worker 工作目录均为目标 release，Compose 状态正常；启动日志错误扫描为空。
- 内网与公网 `live/ready` 通过，运行版本为 `13b6a65`，deployment id 为本批次；MySQL、Celery 和 `document-translation-batches` 正常，readiness/P0 blockers 均为空。
- 首次运行 release check 时误用了 Compose service 环境，生产配置覆盖了测试默认值，形成 5 个环境污染型测试失败且 preflight 访问了错误的容器内地址；服务健康和默认指针未受影响。改用隔离 `docker run`、空 `.env` 和仅限 preflight 的既有 admin token 后重跑通过：36 个目标、182 项测试，Golden Sample 4 个样本 preflight 通过且未创建转换任务。

### 模板版本迁移

- 迁移前显式读取 `default@1` 与 `default@2`：v1 按原 hash 正常读取且为默认；v2 为 published、hash 正确且未自动成为默认。
- v1 旧字体字段按兼容合同归一化；v2 的正文、标题、表格、图注、页眉和页脚均确认西文字体为 `Arial`、复杂文种字体为 `Times New Roman`。
- 在其余后端门禁全部通过后，通过既有 admin API 执行 `set-default default@2`，审计理由为“启用多文种字体内置默认配置”。
- 写入后默认 layout-config 与 ready 均读回 `default@2`，配置 hash 和字体字段符合合同；未修改或删除 v1。

### 前端与公网门禁

- 前端通过临时 symlink 加 `mv -Tf` 原子切换，`nginx -t` 与 reload 通过。
- 公网首页、目标 hash 静态资源和 `/settings/word-page-styles/default` 均返回 200。
- 公网 `live/ready` 通过，版本为 `13b6a65`、默认模板为 `default@2`，无 readiness blocker。
- 未触发 Phase J 回滚；MySQL、Redis、应用 volume、历史 release 和失败证据均保留。

### 独立只读复核与残余风险

- 独立复核再次确认本地/远端 SHA、Compose 状态、运行版本、deployment id、前端 symlink、nginx、公网首页/静态资源/健康接口和 `default@2` 指针均符合目标。
- 默认 v2 的正文、标题、表格、图注、页眉和页脚字体投影均符合 `Arial` / `Times New Roman`；显式 v1 仍按固定 hash 返回 200。
- API/Worker 最近 300 行日志未发现 `ERROR`、`CRITICAL`、`Traceback` 或 `Exception`。
- ready 中 `deployment.environment` 仍为部署前既有的 `dev`。本次未扩大范围修改生产环境标签；版本、deployment id、公开部署模式与所有运行时门禁均来自目标 release，后续如需治理该标签应单独核对其配置 owner 和影响范围。
