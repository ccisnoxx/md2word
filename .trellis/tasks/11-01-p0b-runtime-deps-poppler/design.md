# P0b 技术设计

## 1. 责任边界

- Python 依赖唯一来源：`requirements.txt`（两个 Dockerfile 都 `pip install -r`）。
- 系统依赖唯一来源：`docker/prod/Dockerfile`、`docker/dev/Dockerfile`。
- 工具可用性的运行时 owner 仍是 `PopplerPdfTableCropProvider`（用 `shutil.which` 解析路径）；readiness 只观测、不改变其行为。
- readiness owner：`app/services/health_service.py` 的 `READINESS_NON_BLOCKING_CHECKS` 与 warnings 组装；告警文案 owner：`frontend/src/utils/displayText.ts::readinessCodeText`。

## 2. 依赖声明

```
pillow>=12.2,<13
```

按文件现有风格加入（字母序位置与上下限风格一致）。上限防止未验证的主版本升级；下限为生产容器实际运行并经 pub2 发布包断言的 12.2.0。代码使用的 `Image.open/verify/load`、`DecompressionBombWarning`、`Image.MIME` 等 API 在该范围内稳定。

## 3. Dockerfile

两个文件在 `pip install` 之前加入同一层：

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

- 只装 `poppler-utils`，`--no-install-recommends` 控制体积；清理 apt 列表。
- 生产镜像在切换到 `md2word` 用户之前安装（需要 root）。
- 不固定 Debian 包版本：基础镜像标签决定发行版，固定版本会在发行版滚动后失效；裁切实现已用 `pdfinfo` 输出解析与尺寸校验失败关闭。

## 4. readiness

- 新检查键 `pdf_crop_tools_available`：`shutil.which("pdfinfo") is not None and shutil.which("pdftoppm") is not None`，加入 `READINESS_NON_BLOCKING_CHECKS`。
- 不可用时追加 warning `pdf_crop_tools_missing`；不进入 blockers。理由：只影响“缺 HTML 且无参考图”的表格占位裁切路径，其他转换不受影响；阻断会让无 Poppler 的开发环境整体不就绪。
- warning 经既有逻辑汇入 `readiness_warnings_present` 运维告警，无需额外接线。
- 前端 `readinessCodeText` 增加 `pdf_crop_tools_missing: "PDF 表格裁切工具（Poppler）缺失"`。

## 5. 依赖声明守卫测试

`tests/test_runtime_dependency_declarations.py`：

- 用 `ast` 扫描 `app/**/*.py` 的 `import`/`from ... import`（含函数内延迟导入；忽略相对导入、标准库 `sys.stdlib_module_names`、`app` 自身）。
- 用 `importlib.metadata.packages_distributions()` 把顶层模块映射到发行包名，规范化（小写，`_`→`-`）后与 `requirements.txt` 声明名比对。
- 白名单两类，均需写明理由：
  - `TRANSITIVE_IMPORTS`：`{模块: 声明的父依赖}`——`starlette`/`pydantic`/`pydantic_core`→`fastapi`，`botocore`→`boto3`，`lxml`→`python-docx`，`kombu`/`billiard`→`celery`。测试同时断言父依赖确实在 `requirements.txt` 中。
  - `OPTIONAL_IMPORTS`：`{"pdfminer"}`，有意可选（缺失时页面质量观测返回 unavailable）。
- 核心比对逻辑写成纯函数，供测试用构造输入证明“缺 Pillow 声明时报告 PIL”。
- 映射依赖本地已安装的包；未安装且不在白名单的模块直接判为未声明。

## 6. 文档

- `docs/runbooks/backend.md` 补充系统依赖说明（Poppler 用途、缺失表现、readiness 告警代码）。
- `docker/README.md` 注明镜像内置 `poppler-utils`。

## 7. 兼容、风险与回滚

- 镜像体积增加 `poppler-utils` 及其库（数十 MB 量级，构建时实测记录）。
- 线上 pub2 发布流程与镜像链不在本任务范围；其 `table-crop` 层与本 Dockerfile 使用同一安装命令，二者行为一致。
- 无数据、API 字段（`dependency_checks` 为自由字典）、状态机变化；OpenAPI 不受影响。
- 回滚即回退提交；已部署镜像需重建。
- 生产主机已核实具备 Pillow 12.2.0 与 Poppler 25.03.0（见 PRD）；部署属后续统一推送后的独立步骤。
