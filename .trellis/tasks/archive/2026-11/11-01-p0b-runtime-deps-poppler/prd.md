# P0b：运行时依赖声明与 Poppler 部署

## 目标与业务结果

让当前 `main` 构建出的生产/开发镜像能够启动，并具备代码已经依赖的 PDF 裁切工具；运维能从 readiness 直接看出 PDF 裁切工具是否可用；同类“依赖只在本地间接存在”的问题由测试提前拦截。本任务不改变转换算法。

## 背景与证据（基线 `2f2c5763`，含 P0a）

- `requirements.txt` 未声明 Pillow。用 pip dry-run 解析其完整依赖闭包（53 个包）后确认不含 Pillow；本地 venv 中的 Pillow 12.2.0 只是 `pdf2image` 带入的。
- `app/main.py` 顶层导入 `app/infrastructure/pdf_crop.py`，后者以及 `artifact_validator.py`、`table_placeholder.py` 都在顶层 `from PIL import ...`。因此按当前 `docker/prod/Dockerfile` 构建的镜像，API 与 Worker 启动时会 `ImportError`。
- PIL 顶层导入始于 2026-10-23（`e1f5079b`，RND-503），`main.py` 接入 Poppler 裁切始于 2026-10-30（`b5a83e97`）。
- `docker/prod/Dockerfile`、`docker/dev/Dockerfile` 基于 `python:3.11-slim`，未安装 `poppler-utils`。`PopplerPdfTableCropProvider` 在找不到 `pdfinfo`/`pdftoppm` 时抛出 `table_placeholder_crop_failed`：缺表格 HTML 且无参考图的任务会以 `document_ir_failed` 失败，且 readiness 中没有任何信号。

### 生产核实（2026-11-01 经授权只读 `ssh hostdzire`）

- 运行镜像 `md2word-mixed-lines:d6cddcd5a9ba`（API/Worker，2026-10-31 切换），Debian 13 trixie、Python 3.11.18；容器内 Pillow 12.2.0、`/usr/bin/pdftoppm`/`pdfinfo`（Poppler 25.03.0），无 `pdfminer`。
- 线上镜像不由仓库 Dockerfile 构建：根镜像 `md2word-p0:polling-f119a3ac1906` 来自 pub2 固定升级包（离线 wheel、哈希锁定的 12.3kB requirements），Pillow 由单独的 `pub2-pillow` 层 `--no-deps` 安装并断言 12.2.0；Poppler 由 2026-10-30 `table-crop` 层临时 `apt-get install poppler-utils`；之后各版本以 `COPY` 增量叠加继承。
- 结论：线上转换失败不是缺依赖导致的；仓库自身的 Dockerfile + `requirements.txt` 无法复现可启动镜像，正确性依赖仓库外发布流程。P0b 修复的是仓库可复现性与可观测性。
- `app/` 中直接导入但未直接声明的其余第三方模块（`starlette`、`pydantic`、`pydantic_core`、`botocore`、`lxml`、`kombu`、`billiard`）均属于已声明包的必然传递依赖；`pdfminer` 是有意的可选依赖（缺失时页面质量观测返回 unavailable）。

## 范围与要求

1. `requirements.txt` 直接声明 Pillow，版本范围覆盖生产已验证版本 12.2.0。
2. 生产与开发 Dockerfile 安装 `poppler-utils`，提供 `pdfinfo`、`pdftoppm`；不引入其他系统包。
3. readiness 增加非阻断检查：`pdfinfo` 与 `pdftoppm` 均可在 PATH 中找到时为可用，否则产生 warning（不阻断就绪，因为它只影响表格占位裁切路径）。
4. 新增依赖声明守卫测试：`app/` 中所有非标准库、非 `app` 的顶层导入，必须由 `requirements.txt` 直接声明，或列入带父依赖说明的传递依赖白名单，或列入可选依赖白名单；新增未声明导入时测试失败。
5. 更新运维文档中对系统依赖的说明。

## 非目标

- 不声明 `pdfminer.six`、不启用页面质量观测（属于功能启用决策）。
- 不部署、不推送、不改动生产服务/编排/现有镜像标签；不把线上 pub2 发布流程迁入仓库。
- 构建验证仅在 hostdzire 上以隔离标签进行（见 AC2），用户已授权该主机的核实与验证构建。
- 不修改 `PopplerPdfTableCropProvider` 的几何限制或错误语义，不新增图片回退（属 P0c 及以后）。
- 不把其余传递依赖改为直接声明。

## 验收条件

- AC1：`requirements.txt` 含 Pillow 声明；依赖闭包解析包含 Pillow。
- AC2：两个 Dockerfile 安装 `poppler-utils`。在 hostdzire 上用本分支源码与 `docker/prod/Dockerfile` 构建隔离标签镜像（不 pull 基础镜像，复用线上同源 `python:3.11-slim`），一次性容器（`--rm`、`--network none`、不挂载卷、不读 `.env`）中：`import app.main` 成功、Pillow 为 12.x 且可编解码 WebP、`pdftoppm -v` 可执行、`PopplerPdfTableCropProvider` 对测试 PDF 裁切成功；验证后删除测试镜像与临时目录，生产容器、`md2word-*` 既有标签与 compose 均不变。
- AC3：readiness `checks` 返回 PDF 裁切工具可用性；工具缺失时出现对应 warning，`readiness_blockers` 不变。
- AC4：守卫测试在当前代码上通过；去掉 Pillow 声明或新增未声明导入时失败（以测试内构造输入证明）。
- AC5：既有 health/readiness 相关测试与基线结果一致。

## 不变量

- 不放宽任何 MinerU 安全校验或裁切几何校验。
- readiness 现有 blocker 集合与语义不变。
