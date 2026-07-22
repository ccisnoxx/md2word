# 实施清单

## Phase A：刷新基线并整合主线

- [x] 用 `git fetch origin main` 刷新远端；确认规划基线仍为 `origin/main=06e2e7da`，如发生影响 schema/部署合同的变化则停止并更新规划。
- [x] 确认工作区除当前 Trellis 任务外无未识别改动，记录 `HEAD`、merge base 和双方提交。
- [x] 执行不改写历史的 `git merge origin/main`，逐个解决 7 个预演冲突。
- [x] 以远端 `layout_config_schema.py` 为唯一 owner，合入三类字体模型、schema、兼容归一化和显式空字符串语义。
- [x] 保留远端 draft/patch/CAS/权限/版本持久化，移除冲突中旧 full-config 保存路径。
- [x] 保留共享 `run_fonts.py` 及正式/legacy 两条渲染调用，确认全仓没有第二个 OOXML 字体槽位 owner。
- [x] 合并 seed、backend/frontend spec、测试和 Trellis journal；更新部署文档的后端/前端完整回滚步骤。

## Phase B：本地验证与 Git 门禁

- [x] 运行字体与严格 schema 定向测试（为规避既有测试桩模块污染，四个模块使用独立 Python 进程执行）：

```bash
.venv/bin/python -m unittest \
  tests.test_template_layout_config_schema \
  tests.test_text_render_characterization \
  tests.test_render_config_characterization \
  tests.test_document_ir_word_renderer_layout
```

- [x] 运行模板配置 API/版本治理相关精确测试；完整 `tests.test_fastapi_jobs_backend` 另观察到 6 个与本任务无关的既有 callback 测试失效，正式 release check 不受影响。
- [x] 运行前端 unit 与生产构建：

```bash
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

- [x] 运行聚合发布门禁与文本检查：

```bash
.venv/bin/python scripts/ops/check_release.py
git diff --check
```

- [x] 审阅 diff，确认无旧保存兼容层、第二 schema、silent fallback、secret、无关文件或未说明行为变化。
- [x] 向用户展示 commit 计划并取得确认后提交整合结果；提交后再次确认是否 push。
- [x] 用户手动 push 后以 `git ls-remote` 锁定目标完整 SHA，确认目标包含 `b249790d` 与 `06e2e7da`。

## Phase C：生产只读预检与发布准备

- [x] 通过 `ssh hostdzire` 执行只读 probe；遇到 host-key conflict 立即停止，不修改 known_hosts。
- [x] 解析并记录当前后端 release、APP_VERSION/DEPLOYMENT_ID 非敏感摘要、前端 `current` symlink target、Compose 状态和内网 ready。
- [x] 确认 release root、bare repo、Docker/Compose、nginx、磁盘空间和目标 SHA 可用；不得读取或输出 `.env`、token、密码或内部账号内容。
- [x] 从同一已验证目标工作树构建 `frontend/dist`，创建仅含 dist 内容的临时 tar 包。
- [x] 在 hostdzire 创建新的 Git archive 后端 release，校验开发目录均被排除，复制当前忽略配置并仅更新发布标识。
- [x] 上传前端 tar 到临时路径并解压到新的静态 release，收敛所有权和权限；暂不切换 `current`。

## Phase D：后端切换与内网门禁

- [x] 在新后端 release 执行 Compose build、`up -d`、`ps` 和 API/Worker 日志检查。
- [x] 检查内网 `live/ready/metrics`；确认 deployment version/id、MySQL、Celery、translation batch queue 和 blockers 符合合同。
- [x] 在生产镜像中运行 runtime release check 和 Golden Sample preflight，遮蔽 release `.env` 的测试加载路径且不输出凭据。
- [ ] 使用现有 admin 运维凭据只读 GET 默认模板 layout config，安全投影 schema/config，确认三类字体字段及 `Arial` / `Times New Roman` 默认值。
- [x] 任一检查失败立即执行 Phase F，不切换前端。

## Phase E：前端切换与公网门禁

- [ ] 原子切换 `/var/www/md2word-frontend/current` 到新静态 release，执行 `nginx -t` 和 reload。
- [ ] 检查公开首页、静态 asset、配置中心 SPA 路由和公网 `live/ready`。
- [ ] 能复用安全已登录会话时人工核对三种字体标签；否则记录 admin API 投影和前端构建为替代只读证据，不尝试绕过认证。
- [x] 把目标 SHA、后端/前端 release、Compose/健康/release check/字体合同结果写入 `deployment-audit.md`，不写敏感信息。

## Phase F：失败回滚

- [x] 后端失败：进入旧 release，重新 Compose build，再 `up -d --force-recreate api worker`，确保 shared `latest` 恢复为旧代码。
- [ ] 前端已切换时：恢复旧 `current` symlink，`nginx -t` 后 reload。
- [x] 重跑内网与公网 `live/ready`，记录恢复的版本、失败门禁和剩余影响。
- [x] 不执行 `down -v`，不删除新旧 release、volume 或失败证据。

## Phase G：修复已发布 seed 的不可变版本合同

- [x] 将 `resources/template_configs/datasheet_template.yaml` 恢复为生产 `default@1` 已发布的原始内容，并用固定 SHA-256 测试锁定该合同。
- [x] 新建独立的多文种字体 v2 YAML；manifest 显式声明 `version: 2` 并指向 v2，不原地改写 v1。
- [x] 将应用设置和 runtime helper 中真正代表“当前内置配置”的默认路径更新为 v2；逐个核对直接路径调用，历史兼容/临时 fixture 不做无证据的机械替换。
- [x] 增加 bootstrap/读取测试：已有 v1 默认时创建 v2 但不自动改默认；v1 hash 可读；v2 包含中文、西文、复杂文种字体及 `Arial` / `Times New Roman`。
- [x] 运行定向 backend 测试、frontend unit/build、`scripts/ops/check_release.py`、`git diff --check`，并审阅 diff 中的路径 owner、hash、fallback 和无关改动。

## Phase H：第二次 Git 门禁

- [x] 展示 seed v2 修复和 Trellis 文档的 commit 范围，取得用户确认后提交；不得混入未识别 dirty 文件。
- [x] 提交后取得 push 授权或由用户手动 push，再用 `git ls-remote` 锁定新的 `origin/main` 完整 SHA。

## Phase I：第二次发布、显式迁移与最终门禁

- [x] 为新 SHA 创建全新的后端和前端 release；不得覆盖第一次失败 release 或其审计证据。
- [x] 构建并启动后端，完成 Compose、日志、内外网健康、runtime release check 和 Golden Sample preflight。
- [x] 使用 admin 只读检查显式 `default@1` 与 `default@2`：v1 hash/内容合同保持有效，v2 已发布且字体默认值为 `Arial` / `Times New Roman`。
- [x] 其余后端门禁全部通过后，使用既有 admin API 执行 `set-default default@2`，理由记录为“启用多文种字体内置默认配置”；读回默认版本确认指针和字体合同。
- [x] 原子切换同 SHA 前端 release，执行 nginx、首页、静态资源、配置中心路由及公网健康检查。
- [x] 在 `deployment-audit.md` 追加第二次目标 SHA、release、v1/v2 验证、默认迁移和最终门禁结论，不记录凭据。

## Phase J：第二次发布回滚

- [ ] 若失败发生在 `set-default` 前，按既有 release 回滚流程恢复旧后端/前端。
- [ ] 若失败发生在 `set-default` 后，先保持新后端在线并通过 admin API 恢复 `default@1`；读回成功后再重建旧镜像、force-recreate 服务并恢复旧前端。
- [ ] 若默认指针无法恢复，停止旧代码切换并报告阻塞；任何路径均不删除 volume、release 或失败证据。

## 关键风险文件与回滚点

- 合并冲突核心：`.trellis/spec/backend/index.md`、`.trellis/spec/backend/template-layout-configuration.md`、`.trellis/workspace/777/index.md`、`.trellis/workspace/777/journal-1.md`、`app/domains/templates/read_service.py`、`app/services/renderer/template_config.py`、`tests/test_fastapi_jobs_backend.py`。
- 结构 owner：`app/domains/templates/layout_config_schema.py`。
- bundled seed 版本 owner：`resources/template_configs/templates_manifest.yaml`；v1/v2 文件路径和 hash 属于已发布 payload 合同。
- 发布配置：`docker/prod/docker-compose.yml`、`docker/prod/Dockerfile`、`deploy/nginx/md2word-api.962850.xyz.conf`。
- 后端回滚点：切换前解析出的当前 release；前端回滚点：切换前 `current` symlink target。

## `task.py start` 前门禁

- [x] `prd.md`、`design.md`、`implement.md` 已完成最终评审。
- [x] `implement.jsonl` 与 `check.jsonl` 已包含真实 spec/research 条目。
- [x] 用户在后续消息中明确批准本规划进入实施；规划审批不自动等同于 push 审批。
