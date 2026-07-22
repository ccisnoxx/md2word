# 部署规划证据

## 仓库与分支

- 观察时间：2026-07-22（Asia/Shanghai）。
- 本地 `HEAD`：`05c50794`。
- 远端 `origin/main`：`06e2e7da341d2dddea410027292f4c6774412951`。
- merge base：`85d72e39032f2002f682ab5c081df25b4d34b646`。
- 本地包含字体实现 `b249790d` 和字体合同 `231d42ae`；`b249790d` 不是远端 `main` 的祖先。
- `git merge-tree --write-tree HEAD origin/main` 返回冲突，不能直接 push 或部署当前本地提交。

合并预演列出的冲突：

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/template-layout-configuration.md`（add/add）
- `.trellis/workspace/777/index.md`
- `.trellis/workspace/777/journal-1.md`
- `app/domains/templates/read_service.py`
- `app/services/renderer/template_config.py`
- `tests/test_fastapi_jobs_backend.py`

## 相关历史合同

Trellis memory `019f8860-fc07-7871-b742-16ab62ce4c0a` 记录了已完成字体任务的关键决定：

- `font_name / western_font_name / complex_script_font_name` 分别映射 `eastAsia / ascii+hAnsi / cs`。
- 新字段缺失时回退主字体，显式空字符串继承模板。
- 页眉、页脚和两条渲染链使用共享 helper。
- seed 西文/复杂文种默认值为 `Arial` / `Times New Roman`。
- 当时的配置 API 基于旧 full-config 保存形态。

远端已归档任务 `07-11-word-template-style-management` 的 PRD/design/spec 表明：

- `app/domains/templates/layout_config_schema.py` 是模板配置唯一结构 owner。
- admin GET/dirty changes POST、draft/publish/default、CAS 和 MySQL 版本治理是当前合同。
- `app/services/renderer/template_config.py` 仅 re-export schema owner 的模型。
- 因此合并时必须把字体能力迁移进远端 owner，不能保留旧 full-config 保存实现。

## 部署文档结论

依据 `docs/deploy/hostdzire-dmit-md2word.md`、`docs/deploy/online-first-validation-workflow.md`、`docs/deploy/p0-docker-deployment.md` 和 `docs/runbooks/backend.md`：

- 正常部署目标唯一为 SSH alias `hostdzire`；普通代码发布不修改 `dmit`。
- 后端 release root 为 `/root/md2word-releases`，来源是 GitHub bare repo 的目标 commit archive。
- 当前 release 的 `.env` 与 `deploy/auth_internal_users.json` 被复制到新 release；只更新 `APP_VERSION` 和 `DEPLOYMENT_ID`。
- Compose project 为 `md2word-p0`，API 回源为 `127.0.0.1:18000`，数据位于命名 volume。
- 运行时门禁是内网/公网 live/ready、Compose 状态/日志和生产镜像内 `check_release.py --runtime-url`。
- nginx 静态根为 `/var/www/md2word-frontend/current`；前端必须通过独立 release 和 symlink 发布。

## 已识别运维缺口

- `docker/prod/Dockerfile` 仅打包 Python app/scripts/resources，不包含前端；Git archive 也不包含 ignored 的 `frontend/dist`。只做后端 release 会漏发配置中心静态页面。
- Compose 的 API/Worker 共用 mutable `md2word-p0:latest`。文档当前只在旧 release 执行 `up -d --force-recreate`，这仍可能复用新镜像；可靠应用回滚需先在旧 release 重新 build，之后再 force-recreate。
- 前端回滚需在切换前保存旧 `current` symlink target，并在失败时恢复后执行 nginx config test/reload。

## 安全边界

- 不读取或输出 SSH 私钥；使用 `~/.ssh/config` 的 `hostdzire` alias。
- 不输出 `.env`、JWT、admin token、密码、内部账号 JSON 或 provider 凭据。
- 不执行 `down -v`、历史 worktree reset、force push、release 覆盖或 volume 删除。
