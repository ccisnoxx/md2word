# 重新部署生产环境

## Goal

把本地已完成的页面样式多文种字体能力与远端最新模板样式治理能力安全整合，发布到 `hostdzire` 生产环境，并用仓库规定的运行时门禁和字体合同检查证明后端、配置中心及 Word 字体槽位均来自同一目标版本；失败时恢复上一版后端和前端。

## Background

- 本地 `main` 当前为 `05c50794`，包含 `b249790d`（多文种字体实现）和 `231d42ae`（字体合同），相对远端领先 5 个提交。
- `origin/main` 当前为 `06e2e7da`，包含新的 admin Word 模板样式管理、严格 schema、draft/publish/default 和 MySQL 版本治理，相对本地另有 3 个提交。
- 两条分支共同祖先为 `85d72e39`。合并预演确认有 7 个内容冲突，涉及模板配置 schema/read service/renderer model、测试和 Trellis 记录；本地字体提交尚未存在于远端，当前不能直接部署或直接推送。
- 生产拓扑由 `hostdzire` 承载 Docker Compose、MySQL、Redis、API、Worker 和静态前端；`dmit` 仅负责公网转发，普通代码发布不修改它。
- 后端 release 从 GitHub commit 导出到 `/root/md2word-releases/<short-sha>`。前端 `dist` 不在 Git archive 或后端镜像中，需独立发布到 `/var/www/md2word-frontend/releases/<release-id>` 并原子切换 `current` symlink。
- 首次发布验证发现生产 MySQL 已保存不可变的 `default@1` payload：其 `layout_config_path` 指向 `resources/template_configs/datasheet_template.yaml`，哈希为旧 seed 内容；字体提交原地改写该文件但未提升 manifest 版本，导致严格 hash 校验以 400 拒绝读取。该次发布已在前端切换前停止并恢复 `cc5896f`。

## Requirements

### R1. 发布代码整合

- 使用不改写既有历史的 merge，把最新 `origin/main` 合入本地 `main`；不得 force push、rebase 已共享历史或丢弃任一分支功能。
- 以远端 `app/domains/templates/layout_config_schema.py` 为模板配置唯一结构 owner，保留其严格校验、dirty changes、draft/publish/default、权限和故障关闭合同。
- 在该新合同中叠加已批准的多文种字体扩展：中文/东亚、西文、复杂文种三类字体；内置 seed 默认值分别为现有中文字体、`Arial`、`Times New Roman`。
- 旧 YAML 缺少新增字段时按字段是否存在执行兼容补齐；显式空字符串继续表示继承 Word 模板，不得用 truthy fallback 改写语义。
- 正式 DocumentIR 与 legacy 渲染继续共享唯一 OOXML 字体槽位写入函数；不得恢复两份 `rFonts` 实现。
- 已发布 seed 版本不可变：恢复 `default@1` 原始 YAML 路径和字节内容，新建独立的多文种字体 v2 YAML，并让 manifest 显式发布 `version: 2`。不得修改 v1 payload/hash、绕过 hash 校验或增加运行时猜测回退。
- 仓库中直接作为“当前内置默认配置”使用的路径 owner 必须指向 v2；历史 v1 路径仅承担已发布版本读取和兼容测试，不作为新任务的隐式当前配置。

### R2. 推送与目标版本门禁

- 合并完成后先通过定向测试、前端构建和 release check，再提交整合结果。
- 提交前展示 commit 范围并取得确认；push 前再次取得明确授权。不得把未验证或未获授权的本地提交推到 `origin/main`。
- 部署目标必须是 push 后 `origin/main` 的完整 SHA，且必须包含 `b249790d` 和 `06e2e7da`；以 `git ls-remote` 结果为准。

### R3. 生产发布

- 只通过 SSH alias `hostdzire` 连接目标机；不得读取、复制或输出私钥、密码、token、`.env` 内容或内部账号内容。
- 执行前只读确认当前后端 release、前端 symlink、Compose 状态、运行版本和目标 commit 可获取性，并记录回滚目标。
- 从远端 bare repo 对目标 SHA 执行 `git archive` 创建全新 release；不得在历史 `/root/md2word` worktree 上 pull/reset，也不得覆盖已存在 release。
- 复用当前 release 的 `.env` 和 `deploy/auth_internal_users.json`，仅更新非敏感 `APP_VERSION`、`DEPLOYMENT_ID`；不删除或重建 MySQL/Redis/应用数据 volume。
- Python/资源变更必须重新构建并启动 API/Worker；前端从同一已验证工作树构建，单独上传并原子切换静态 release。

### R4. 上线验证

- 后端切换后检查 Compose 服务、API/Worker 日志、内网 `live/ready/metrics`、容器内 `check_release.py --runtime-url` 和公网 `live/ready`。
- `ready` 必须确认 deployment 标识为目标 SHA，MySQL metadata、Celery worker 和 translation batch queue 均无 blocker。
- 使用现有 admin 运维凭据执行只读 layout-config 检查，输出仅保留字段名和非敏感值；确认 schema 与配置均包含三类字体，seed 西文为 `Arial`、复杂文种为 `Times New Roman`。
- bootstrap 后先验证 `default@1` 仍能按原 hash 读取、`default@2` 已发布且包含 `Arial` / `Times New Roman`；其余后端门禁全部通过后，使用现有 admin API 显式执行 `set-default default@2`，并再次读取默认版本确认指针与字体合同。
- `check_release.py` 必须覆盖多文种字体定向测试和真实 DOCX OOXML 槽位断言；Golden Sample 只执行不创建任务的 preflight，正式 4 样本转换与人工签字不作为本次重部署阻塞项。
- 前端切换后检查 nginx 配置、公开首页/静态资源和配置中心路由可用；不得只更新后端而遗漏静态前端。

### R5. 失败与审计

- 任一构建、启动、健康、release check、字体合同或公网检查失败即停止后续切换并进入回滚，不用 silent fallback 掩盖错误。
- 回滚同时恢复后端旧 release 和前端旧 symlink。由于 Compose 共用 `md2word-p0:latest`，后端回滚必须先从旧 release 重新 build，再 force-recreate API/Worker；只在旧目录执行 `up` 不能作为充分恢复证据。
- 若失败发生在默认指针切到 v2 之后，必须先由仍运行的新后端通过既有 API 把默认指针恢复到已发布的 `default@1` 并验证成功，再回滚旧代码；不得直接让旧代码面对 v2 默认配置。
- 回滚后重新执行内网和公网健康检查；不删除新旧 release、失败证据或持久化 volume。
- 在任务内记录目标 SHA、前后 release 标识、执行命令类别、门禁结果和回滚状态，不记录任何敏感值。

## Acceptance Criteria

- [x] 合并后的目标提交同时包含 `b249790d` 与 `06e2e7da`，远端 `main` 与部署 SHA 一致。
- [x] 远端严格模板样式治理合同保持有效，页面样式三类字体兼容扩展及 `Arial` / `Times New Roman` seed 默认值通过定向测试。
- [x] `default@1` 原始路径/hash 保持可读，manifest/bootstrap 发布独立的 `default@2`，且 bootstrap 不自动改写既有生产默认指针。
- [x] `/root/md2word-releases/<target-short-sha>` 由目标 GitHub commit 导出，API/Worker 运行该版本；前端 `current` 指向同批次静态 release。
- [x] Compose 状态、内网与公网 `live/ready`、运行时 release check 和 Golden Sample preflight 全部通过且无未解释 blocker。
- [x] 生产验证 v1、v2 后显式执行 `set-default default@2`；默认 layout-config 观察到中文、西文、复杂文种字体字段及内置默认值，公开配置中心前端可访问。
- [x] `deployment-audit.md` 记录版本、发布与验证结论且不含敏感信息。
- [x] 若上线门禁失败，旧后端镜像/服务与旧前端 symlink 均恢复并通过健康检查，或明确报告无法回滚的阻塞和当前生产状态。

## Out of Scope

- 不修改 `dmit`、SSH 主机指纹、防火墙、域名、TLS、生产凭据或内部账号。
- 不删除 Docker volume、历史 release、模板历史版本或失败验证证据。
- 不新增第二套部署工具、CI/CD 平台、镜像仓库或长期兼容层。
- 不执行正式 Golden Sample 4 样本转换、人工 Word 签字或字体安装；目标系统缺字时 Word 的字体替换仍属于已知运行环境风险。
