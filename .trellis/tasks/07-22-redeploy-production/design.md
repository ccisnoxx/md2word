# 技术设计

## 1. 总体边界

本任务包含两个顺序不可交换的阶段：先把分叉的本地/远端主线整合为一个可发布 commit，再按仓库既有 release 目录流程切换生产。任何生产动作都以整合测试通过、commit 获批并成功 push 为前提。

```text
local main (字体扩展) + origin/main (严格模板样式治理)
  -> 无历史改写的 merge
  -> 定向测试 + frontend build + release check
  -> 用户确认 commit / push
  -> GitHub target SHA
  -> hostdzire 后端 release + 独立前端 release
  -> v1/v2 不可变性 + 内网门禁
  -> 显式 set-default default@2
  -> 前端原子切换
  -> 公网与字体合同验证
```

## 2. 合并不变量

### 2.1 结构 owner

远端 `layout_config_schema.py` 是合并后的唯一配置模型、编辑 schema 和严格校验 owner。`app/services/renderer/template_config.py` 保持远端的 re-export 形态，不恢复本地旧分支中的重复 Pydantic 模型。

冲突解决按以下所有权处理：

- `layout_config_schema.py`：保留远端 strict model/patch 合同，加入 paragraph、header、footer 的西文和复杂文种字段、编辑标签、长度/空值规则及兼容归一化。
- `read_service.py`：保留远端版本治理、CAS、staging 和 draft 流程，字体补齐调用 schema owner，不保留旧 full-config POST 分支。
- `template_config.py`：保留远端 re-export；新增字段只定义在 schema owner。
- `tests/test_fastapi_jobs_backend.py`：同时保留远端 admin/patch/draft 权限验证和本地旧 YAML/空字符串/字体读回验证，并把请求形状改为 dirty changes 合同。
- Trellis spec/journal 冲突以保留双方记录为原则，最终 spec 合并为“严格版本治理 + 多文种字体”一个合同。

### 2.2 字体兼容语义

兼容归一化必须检查 key 是否存在，不能使用 `value or fallback`：

- 段落类旧配置缺 `western_font_name` / `complex_script_font_name` 时，补为同组 `font_name`。
- 页眉缺 `title_western_font_name` / `title_complex_script_font_name` 时，补为 `title_font_name`。
- 旧页脚缺全部字体字段时补为空字符串，继续继承模板既有字体。
- 显式 `""` 原样保留，编辑校验允许新增的西文/复杂文种字段为空；主 `font_name` 继续服从远端非空约束。
- seed 显式写入 `Arial` 和 `Times New Roman`，避免内置新配置依赖兼容回退。

OOXML 写入仍由 `app/conversion/docx_rules/run_fonts.py` 唯一负责：`eastAsia` 使用中文字体，`ascii/hAnsi` 使用西文字体，`cs` 使用复杂文种字体。

### 2.3 已发布 seed 的版本边界

生产首次验证证明模板版本 payload 会持久化资源相对路径和 SHA-256，读取与任务资源解析都以该 payload 做严格校验。因此 bundled seed 的版本号、文件路径和文件字节共同构成不可变合同：

- `resources/template_configs/datasheet_template.yaml` 恢复为 `default@1` 发布时的原始字节，继续满足生产已有 payload/hash。
- 新增独立的 v2 YAML，内容使用当前多文种字体配置；`templates_manifest.yaml` 显式声明 `version: 2` 并指向该文件。
- 应用设置和无版本任务路径等“当前内置配置” owner 改为 v2 路径；读取已发布版本时仍以数据库 payload 为唯一资源路径 owner。
- 复用现有 `bootstrap_manifest_versions()`：缺少 v2 时创建发布记录；生产已有默认 v1 时不自动切换默认指针。
- 不改变 hash 校验，不用旧路径内容探测、版本猜测、双路径 fallback 或 silent default 掩盖 seed 版本错误。

本地测试应同时证明：v1 文件 hash 固定；v2 schema 与字体默认值正确；已有 v1 默认记录时 bootstrap 只发布 v2、不改变默认；空数据库初始化行为继续服从既有服务合同。

## 3. Git 与发布目标

- 执行开始时刷新 `origin/main`。若它不再是规划时观察到的 `06e2e7da`，先检查新增提交；如影响冲突范围、schema 或部署合同，则更新规划并重新评审。
- 采用 merge 而非 rebase/force push，保留双方已存在提交身份和可审计历史。
- 合并后的新 commit 是唯一发布目标。push 后用 `git ls-remote origin refs/heads/main` 锁定完整 SHA，并在远端 bare cache 验证该对象存在。
- Trellis 规划文件和产品整合改动在提交前分清范围；任何 unrecognized dirty file 不进入 commit。

## 4. 后端 release

通过 `ssh hostdzire` 执行文档中的 GitHub archive 流程：

1. 从运行中 API 的 Compose label 解析当前 `.env` 和旧 release，不猜固定当前目录。
2. 记录当前 APP_VERSION/DEPLOYMENT_ID 的非敏感摘要、Compose 状态和旧 release 路径。
3. fetch bare repo 的 `main`，校验目标 SHA 后导出到新的 `/root/md2word-releases/<short-sha>`。
4. 检查开发目录未进入 release，复制当前 `.env` 与内部账号 JSON，更新发布标识。
5. 在新 release 构建 `md2word-p0:latest`，执行 `up -d`，不执行 `down -v`。

MySQL、Redis 和 `md2word-var` 均继续使用 Compose 命名 volume。目标代码若执行既有幂等 schema bootstrap，失败必须让启动/ready 明确失败；不得回退到 file backend。

## 5. 前端 release

`docker/prod/Dockerfile` 不复制 `frontend`，`.gitattributes` 导出的后端 release 也不包含本地 ignored 的 `frontend/dist`，因此前端必须独立处理：

1. 在整合后的干净目标工作树执行 `npm --prefix frontend run build`。
2. 只打包 `frontend/dist` 内容并上传，不上传 `node_modules`、源码、凭据或开发目录。
3. 在 `/var/www/md2word-frontend/releases/<deployment-id>` 解压，统一 root 所有权、目录 `755`、文件 `644`。
4. 先通过后端内网门禁，再原子切换 `/var/www/md2word-frontend/current`，执行 `nginx -t` 和 reload。

后端先就绪再切前端，避免新页面调用尚未上线的 API 合同。切换前记录旧 symlink target 作为前端回滚点。

## 6. 验证合同

### 6.1 本地整合门禁

- schema、legacy renderer、DocumentIR renderer、配置 API 和远端模板版本治理定向测试。
- 前端 unit/build，确认 schema-driven 表单仍能展示 text 字段并生成生产 dist。
- `scripts/ops/check_release.py` 和 `git diff --check`。

### 6.2 生产内网门禁

- Compose `ps`，API/Worker 最近日志无启动异常。
- `/health/live`、`/health/ready`、`/health/metrics`。
- 生产镜像内运行 `check_release.py --runtime-url http://md2word-p0-api-1:8000 --golden-sample-preflight`，使用现有凭据且不输出值。
- 从 ready deployment 对象确认 `version=<target-short-sha>`、deployment id 为本批次，MySQL/Celery/translation queue 无 blocker。
- admin-only layout-config GET 只投影并记录字段集合和字体值，不保存 draft、不改变默认版本。
- 先读取显式 `version=1` 并核对旧 payload/hash，再读取 `version=2` 并核对三类字体。全部构建、健康、release check 和 preflight 门禁通过后，调用既有 admin `set-default` API 把 `default@2` 设为默认，并重新读取无 version 的默认配置确认迁移结果。

### 6.3 公网门禁

- `https://md2word.962850.xyz/api/v1/health/live` 与 `ready`。
- 首页、带 hash 的静态资源和 `/settings/word-page-styles/default` SPA 路由返回可用内容。
- 若已有安全的已登录浏览器会话，再人工确认“中文字体 / 西文字体 / 复杂文种字体”标签；没有会话时以 admin API 字段投影和前端 build 结果作为非写入证据，不绕过认证。

## 7. 回滚设计

后端和前端回滚点在切换前同时记录。触发条件包括服务不健康、release check 失败、目标版本不符、字体字段合同不符、nginx/静态资源失败或公网 ready 失败。

- 默认指针未迁移时：直接按后端/前端 release 回滚流程恢复。
- 默认指针已迁移到 v2 时：保持目标后端在线，先调用既有 admin API 将默认指针恢复为已发布的 v1，读回确认后再回滚代码。若指针恢复失败，停止旧代码切换并报告生产阻塞，避免制造配置与代码的未知组合。
- 后端：进入旧 release，先重新执行 Compose build 以恢复旧源码对应的共享 `md2word-p0:latest`，再 `up -d --force-recreate api worker`。
- 前端：把 `current` symlink 原子恢复到旧 target，`nginx -t` 后 reload。
- 回滚后重跑内网和公网 live/ready，并记录实际恢复版本。

仅执行文档原有的旧目录 `up` 不足以恢复后端，因为新旧 Compose 共用同一个 mutable image tag；任务执行时同步修正文档中的该条回滚说明。

## 8. 取舍与延期

- 不引入镜像仓库或 immutable image tagging 改造；本次用旧 release rebuild 修复现有 `latest` 回滚缺口。
- 不运行会创建真实转换任务的 4 样本 Golden Sample 正式回归；多文种 OOXML 由生产镜像内定向测试证明，真实运行时由只读配置 API 和健康门禁证明。
- 不负责在服务器安装 `Arial` 或 `Times New Roman`。生成文件声明相应 OOXML 槽位，实际字体缺失时由 Word 客户端替换。
