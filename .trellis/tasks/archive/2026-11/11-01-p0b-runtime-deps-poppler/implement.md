# P0b 实施计划

## 1. 有序任务

1. 守卫测试先行：新增 `tests/test_runtime_dependency_declarations.py`，在未改 `requirements.txt` 时应报告 `PIL` 未声明（证明守卫有效）（AC4）。
2. `requirements.txt` 声明 `pillow>=12,<13`，守卫转绿（AC1/AC4）。
3. 两个 Dockerfile 安装 `poppler-utils`（AC2）。
4. readiness：`pdf_crop_tools_available` 检查与 `pdf_crop_tools_missing` warning；前端文案（AC3）。
5. 文档：`docs/runbooks/backend.md`、`docker/README.md`。

## 2. 计划修改文件

- `requirements.txt`
- `docker/prod/Dockerfile`、`docker/dev/Dockerfile`
- `app/services/health_service.py`
- `frontend/src/utils/displayText.ts`
- `tests/test_runtime_dependency_declarations.py`（新）
- readiness 定向测试：`tests/test_fastapi_jobs_backend.py` 中新增一例（mock `shutil.which` 覆盖可用/缺失）
- `docs/runbooks/backend.md`、`docker/README.md`

## 3. 验证

- 定向：守卫测试；readiness 新用例；`tests.test_fastapi_jobs_backend` 中 `-k readiness`/`-k health` 既有用例，与基线对比。
- 依赖闭包：`pip install --dry-run --ignore-installed --report` 解析结果包含 Pillow。
- 前端：`vitest` 跑 `displayText` 相关测试；`npm run build`。
- 镜像级（AC2，hostdzire，已授权）：
  1. 本地 `git archive` 本分支提交 → `scp` 到 `/root/md2word-p0b-verify-<sha>/`（不放入 `/root/md2word-releases`）。
  2. `docker build --pull=false -f docker/prod/Dockerfile -t md2word-p0b-verify:<sha> .`，记录日志与镜像大小。
  3. `docker run --rm --network none md2word-p0b-verify:<sha>` 依次检查 `import app.main`、Pillow 版本与 WebP 编解码、`pdftoppm -v`、对容器内生成的测试 PDF 执行 `PopplerPdfTableCropProvider.crop`（测试 PDF 用 Pillow 生成，坐标与页面一致）。
  4. 核对生产容器 ID/镜像未变，`docker rmi` 测试镜像、删除临时目录及构建缓存中本次新增层（`docker builder prune` 仅限 dangling，不碰既有镜像）。
- 不跑全仓回归、Playwright；除上述隔离构建外不在生产主机执行写操作。

## 4. 回滚点

每步独立可回退；无数据迁移。

## 5. 实施结果与验证（2026-11-01 北京时间）

- 守卫先行：未声明 Pillow 时 `test_app_imports_are_declared` 仅报告 `PIL`；声明后 `tests.test_runtime_dependency_declarations` 6 例通过（含 readiness 工具可用/缺失）。
- 依赖闭包（pip dry-run）：54 个包，解析 Pillow 12.3.0（生产 12.2.0，均在 `>=12.2,<13` 内）。
- 既有 `tests.test_fastapi_jobs_backend -k health/ready/ops_alert` 25 例：2 例失败（P0 回调地址 blocker 断言、文件对象路径），在基线 `2f2c5763` 上同样失败，未处理。
- 前端：`displayText.test.ts` 3 例通过；`npm run build` 通过。
- hostdzire 隔离构建（内容标识 `fe3473f3018a`，仓库 `docker/prod/Dockerfile`，未 pull 基础镜像）：构建成功，镜像 490MB；`poppler-utils 25.03.0-5+deb13u4`、`pillow 12.3.0`。一次性容器（`--rm --network none`，用户 `md2word`）中 `import app.main` 成功、WebP 往返成功、`pdftoppm 25.03.0`、`PopplerPdfTableCropProvider` 裁切输出 PNG 400×200、`pip check` 无冲突。
- 生产影响核对：构建前后 md2word-p0 容器 ID/镜像一致，API healthy；测试镜像已删除、主机镜像集合与构建前一致、临时目录已删除。未执行 `builder prune`（共享构建缓存保留本次层）。
- 未构建“改动前 Dockerfile”对照镜像；改动前不可启动的结论依据依赖闭包解析与 `app/main.py` 导入链。
