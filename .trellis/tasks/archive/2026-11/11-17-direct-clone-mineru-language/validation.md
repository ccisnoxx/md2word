# 定向验证

## 任务模式与 MinerU 请求

`.venv/bin/python -m unittest tests.test_document_job_modes` 运行 21 项，20 项通过。新增和扩展的语言用例均通过。

- 两种快照均验证 `keep_source_snapshot` 的同文种继承和异文种 409，后者无任务、事件、审计及投递副作用。
- 两种快照均验证 `use_current_defaults` 和 `select_published_versions` 的 direct `zh/en/ru/auto`，版本化路径另外确认显式选择的 published 模板。
- 两种快照均验证四个翻译方向的新建与克隆。Worker 执行前改变配置，实际序列化的 MinerU 请求仍使用创建时冻结的语言。
- 历史语言别名、缺少语言绑定的回退、术语重绑时保留语言均通过。

唯一失败为 `test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot`，在克隆前断言 GET 详情的整个快照等于仓储中的原始快照。详情接口对 `page_quality` 作摘要投影。在未改动的 `57772613` 临时 detached worktree 复跑 `.venv/bin/python -m unittest tests.test_document_job_modes.DocumentJobModesTests.test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot`，同一断言失败。临时 worktree 已清理。

## 克隆 API 既有边界

以下四项定向验证通过。

```bash
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_creates_new_job_without_mutating_source \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_expired_source_and_reports_disabled_reason \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_explicit_resource_selection_requires_admin \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_operator_inheriting_debug_full_text
```

Trellis 上下文校验、`git diff --check`、三个改动 Python 文件的语法编译及独立复核均通过。以上定向测试使用本地 FastAPI、测试仓储、正式 Worker 与 MinerU 客户端序列化，外部 HTTP 由测试替身响应。

冻结语言的验证使用有效语言配置。既有快照读取逻辑将空字符串视为缺失绑定，Worker 在该情况下使用历史回退。

## 真实 MinerU 隔离验收

2026-11-17 复用公开的 TI OPA228 中英文单页 PDF。本地正式 FastAPI 负责创建和克隆，SQLite 覆盖旧版快照，进程内 MySQL 测试适配器覆盖版本化快照和显式模板选择。两种后端均使用独立目录和本地对象存储。设置 `MINERU_LANGUAGE=korean` 后，另建正式 Worker 运行时重读持久化任务。仅观测三条真实 MinerU 请求的 JSON 语言字段、HTTP 状态、业务码和批次状态。

| 策略 | 快照类型 | 克隆文种 | 源绑定 | 克隆创建时默认值 | 克隆冻结值 | Worker 实际语言 |
| --- | --- | --- | --- | --- | --- | --- |
| `keep_source_snapshot` | 旧版 | `auto` | `ch` | `ru` | `ch` | `ch` |
| `use_current_defaults` | 旧版 | `auto` | `ch` | `en` | `en` | `en` |
| `select_published_versions` | 版本化 | `en` | `ch` | `ru` | `en` | `en` |

`select_published_versions` 冻结了显式选择的 `default@1`。异文种的保留快照请求返回 409，原因为 `clone_document_language_conflicts_with_snapshot`。三个有效克隆的 v4 请求均返回 HTTP 200 和业务码 0，MinerU 均达到 `done`。Worker 均登记了 MinerU 结果与 Word 主件，任务达到 `succeeded/completed`，翻译批次均为 0。源任务只用于提供本地快照，真实请求只提交了三个成功创建的克隆。

首轮本地预检使用了非整数模板版本号，克隆 API 在请求发送前拒绝该样例。换用实际发布的整数版本后完成本轮验收。生产与真实 MySQL 未参与。

```bash
PYTHONPATH=. .venv/bin/python tests/tmp/direct-clone-mineru-live-20261117/run_acceptance.py
```

[本地运行证据](../../../../../tests/tmp/direct-clone-mineru-live-20261117/live-evidence.json)

## 版本化 auto 的三种克隆策略

2026-11-17 使用新的隔离目录、进程内 MySQL 测试适配器与真实 MinerU，复用同一组 OPA228 单页样本。源任务均为 direct + `auto`，创建时默认值为 `zh`，其版本化快照同样冻结了 `ch`。三条克隆均显式传入 `document_language=auto`。创建完成后将进程环境中的 `MINERU_LANGUAGE` 改为 `korean`，重新装配 Worker，从仓储读回三个克隆再执行。

| 策略 | 克隆创建时默认值 | 冻结模板 | 快照语言 | 实际请求语言 | 本地任务 |
| --- | --- | --- | --- | --- | --- |
| `keep_source_snapshot` | `ru` | `default@2` | `ch` | `ch` | `docjob_226ec9a2eb8b` |
| `use_current_defaults` | `en` | `default@2` | `en` | `en` | `docjob_1021990dc22f` |
| `select_published_versions` | `en` | `default@1` | `en` | `en` | `docjob_3325cb3e1088` |

三条语言均存于 `request_snapshot.resources.mineru.language`，且分别与发送给 MinerU v4 的顶层 `language` 一致。三条请求均返回 HTTP 200、业务码 0，三个 MinerU 批次均达到 `done`，本地任务均达到 `succeeded/completed` 并登记了解析结果和 Word 主件。翻译批次均为 0。生产与真实 MySQL 未参与。

```bash
PYTHONPATH=. .venv/bin/python -B tests/tmp/direct-clone-mineru-versioned-auto-20261117/run_acceptance.py
```

[版本化 auto 请求与批次证据](../../../../../tests/tmp/direct-clone-mineru-versioned-auto-20261117/live-evidence.json)

## 真实 MySQL 与真实 MinerU 复验

2026-11-17 使用独立的原生 MySQL Community Server 8.4.11，监听本机回环地址并使用临时数据目录。仓库固定摘要的 Docker 镜像尚在下载大层，本轮使用通过官方校验的 macOS ARM64 归档。正式 FastAPI 初始化新库并调用真实 MySQL 仓储，SQL 确认 `document_jobs` 的引擎为 InnoDB。 [官方归档](https://dev.mysql.com/downloads/mysql/8.4.html)

源任务与克隆均为 direct + `auto`。源任务创建时默认值为 `zh`，冻结为 `ch`。三个克隆创建后设置 `MINERU_LANGUAGE=korean`，另建 Worker 运行时从 MySQL 读回三条快照。另用独立 SQL 连接从 `document_jobs.payload` 取出 `request_snapshot.resources.mineru.language`，核对实际发送到 MinerU v4 的顶层 `language`。

| 克隆策略 | 克隆创建时默认值 | 冻结模板 | MySQL 快照语言 | 实际请求语言 | 本地任务 |
| --- | --- | --- | --- | --- | --- |
| `keep_source_snapshot` | `ru` | `default@2` | `ch` | `ch` | `docjob_af2a4a784768` |
| `use_current_defaults` | `en` | `default@2` | `en` | `en` | `docjob_0eccf2b7b208` |
| `select_published_versions` | `en` | `default@1` | `en` | `en` | `docjob_14ada5bd18f5` |

三条真实请求均返回 HTTP 200、业务码 0，MinerU 批次均达到 `done`。执行后再次用 SQL 确认三个任务均为 `succeeded/completed`，数据库批次 ID 与 MinerU 响应一致，冻结语言仍与发出的请求一致。三条任务均登记解析结果和 Word 主件，翻译批次均为 0。验收使用独立数据库、公开样本和本地对象存储。临时实例、数据目录与本轮 MySQL 凭据在退出后清理。

```bash
PYTHONPATH=. .venv/bin/python -B tests/tmp/direct-clone-mineru-real-mysql-20261117/run_native.py
```

[真实 MySQL 与 MinerU 证据](../../../../../tests/tmp/direct-clone-mineru-real-mysql-20261117/live-evidence.json)

## 仓库固定摘要的 MySQL Docker 复验

2026-11-17 在独立 Colima 环境使用开发与生产 Compose 共同固定的 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`。Docker 拉取与容器检查均核对该摘要，实际运行平台为 Linux ARM64。应用通过本机回环端口访问独立 MySQL Community Server 8.4.9，SQL 确认 `document_jobs` 为 InnoDB。

三条待验收任务均为版本化 direct + `auto`，其源任务冻结值均为 `ch`。克隆创建完成后将 `MINERU_LANGUAGE` 设为 `korean`，重新装配 Worker。另用 SQL 从 `document_jobs.payload` 查询 `request_snapshot.resources.mineru.language`，与 Worker 发出的 MinerU v4 请求体逐条比对。

| 克隆策略 | 克隆时默认值 | 冻结模板 | SQL 冻结值 | 实际请求值 | 本地任务 |
| --- | --- | --- | --- | --- | --- |
| `keep_source_snapshot` | `ru` | `default@2` | `ch` | `ch` | `docjob_c8c927866e27` |
| `use_current_defaults` | `en` | `default@2` | `en` | `en` | `docjob_91afec4c0308` |
| `select_published_versions` | `en` | `default@1` | `en` | `en` | `docjob_5b35eb774c49` |

三条真实 MinerU 请求均返回 HTTP 200、业务码 0，批次均达到 `done`。执行后的 SQL 复核显示三个任务均为 `succeeded/completed`，数据库中的批次 ID 与 MinerU 响应一致，冻结值仍与实际请求一致。三个任务均登记了解析结果及 Word 主件，翻译批次均为 0。

首轮预检在发送 MinerU 请求前发现验收脚本缺少 JSON 导入。修正后重新创建临时容器，完成上述复验。验收结束后移除临时容器及其数据、凭据和本轮专用 Colima 环境。

```bash
PYTHONPATH=. .venv/bin/python -B tests/tmp/direct-clone-mineru-pinned-mysql-20261117/run_docker.py
```

[Docker 镜像、SQL 与 MinerU 证据](../../../../../tests/tmp/direct-clone-mineru-pinned-mysql-20261117/live-evidence.json)

## 固定 MySQL 镜像的保留快照冲突反例

2026-11-17 在专用 Colima 环境重试并拉取仓库固定的 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`。容器检查确认实际使用该摘要，SQL 确认 MySQL Community Server 8.4.9 和 InnoDB。主工作区有并行编辑，验收使用 `57772613` 的归档副本叠加本任务的 `request_snapshot.py` 与 `submission.py`；证据记录并复核了两个文件的 SHA-256。预检中的导入错误发生在业务请求前。

在真实 FastAPI 入口创建版本化 direct 源任务 `docjob_a5830226e26f`，其 `document_language=auto`，已冻结 MinerU 语言 `ch`。随后提交 `keep_source_snapshot` 并指定 `document_language=en`。接口返回 HTTP 409、`error_code=conflict`、`error.reason_code=clone_document_language_conflicts_with_snapshot`。

| SQL 表 | 请求前 | 请求后 | 全部有序行内容摘要 |
| --- | ---: | ---: | --- |
| `document_jobs` | 1 | 1 | 一致 |
| `job_events` | 2 | 2 | 一致 |
| `audit_events` | 4 | 4 | 一致 |

源任务创建时，替代队列观测到恰好一次 `enqueue`，用于确认探针接入了真实投递路径。清零后，冲突请求的投递入口、队列 `enqueue`、Worker 执行、MinerU 客户端工厂、MinerU 批量上传和出站 HTTP 计数均为 0。验收使用占位 MinerU 配置和出站请求探针。临时容器、数据、凭据、Colima 环境和归档副本均已清理。

验收从隔离源代码目录执行以下命令，`run_docker.py` 负责启动和清理固定摘要的 MySQL 容器。

```bash
PYTHONPATH=. CLONE_ACCEPTANCE_REPOSITORY_BASE=577726135d657bba909ea5fadd73e28e34a52bcb ../../../../.venv/bin/python -B ../run_docker.py
```

[冲突响应、SQL 与调用计数证据](../../../../../tests/tmp/direct-clone-mineru-pinned-conflict-20261117/live-evidence.json)

## 固定 MySQL 镜像的四种翻译克隆解析回归

2026-11-17 使用独立 Colima 环境和仓库固定的 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`。容器检查确认实际摘要，SQL 确认 MySQL Community Server 8.4.9 与 InnoDB。验收代码来自 `57772613` 加本任务两个产品文件的隔离副本，文件指纹已记录。输入使用公开的中英文 OPA228 单页和本地生成的俄文单页。

源任务显式指定各模式允许的源文种，四个克隆均选用 `use_current_defaults` 并把 `document_language` 改为 `auto`。克隆创建时 `MINERU_LANGUAGE=latin`，Worker 重新装配时改为 `korean`。解析前后独立用 SQL 读取 `request_snapshot.resources.mineru.language`，并比对真实 MinerU v4 批次请求的顶层 `language`。

| 模式 | 源任务文种 | SQL 冻结值（解析前后） | 实际请求语言 | 本地任务 |
| --- | --- | --- | --- | --- |
| `en2zh` | `en` | `en` | `en` | `docjob_0bf217d61da5` |
| `ru2zh` | `ru` | `east_slavic` | `east_slavic` | `docjob_4f5173c986fb` |
| `zh2en` | `zh` | `ch` | `ch` | `docjob_89104e6192f5` |
| `zh2ru` | `zh` | `ch` | `ch` | `docjob_f7ffaa7571d8` |

四条请求均返回 HTTP 200、业务码 0，MinerU 批次均达到 `done`。四个任务均登记了原始解析结果包，SQL 复核任务停在 `running/parsed`，批次 ID 与响应一致。验收脚本在后续 IR 转换入口处停止推进，共命中四次；翻译启动调用和翻译批次均为 0。

首轮预检修正了样本上传辅助函数的调用参数，错误发生在提交 MinerU 之前。临时容器、数据库、凭据、Colima 环境及验收源代码副本均已清理。

```bash
PYTHONPATH=. CLONE_ACCEPTANCE_REPOSITORY_BASE=577726135d657bba909ea5fadd73e28e34a52bcb ../../../../.venv/bin/python -B ../run_docker.py
```

[四种翻译模式的 SQL、请求与解析结果证据](../../../../../tests/tmp/direct-clone-mineru-pinned-translation-20261117/live-evidence.json)

## 固定 MySQL 镜像的翻译保留快照与显式版本复验

2026-11-17 在独立 Colima 环境使用仓库固定的 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`，容器检查确认实际摘要，SQL 确认 MySQL Community Server 8.4.9 与 InnoDB。验收使用 `57772613` 加本任务两个产品文件的隔离副本，复用前一轮的三种语言单页样本。

四种翻译模式各创建两个版本化克隆。`keep_source_snapshot` 沿用源文种和 `default@2`，`select_published_versions` 使用 `document_language=auto` 并显式指定已经发布的 `default@1`。克隆创建时配置为 `MINERU_LANGUAGE=latin`，随后改为 `korean` 并重新装配 Worker。解析前后用 SQL 复核语言、模板版本与批次身份。

| 翻译模式 | 保留快照文种 | 保留快照 SQL 冻结值 / 实际请求 | 显式版本 SQL 冻结值 / 实际请求 |
| --- | --- | --- | --- |
| `en2zh` | `en` | `en` / `en` | `en` / `en` |
| `ru2zh` | `ru` | `east_slavic` / `east_slavic` | `east_slavic` / `east_slavic` |
| `zh2en` | `zh` | `ch` / `ch` | `ch` / `ch` |
| `zh2ru` | `zh` | `ch` / `ch` | `ch` / `ch` |

八条真实 MinerU v4 请求均返回 HTTP 200、业务码 0，批次均达到 `done`，八个原始解析结果包均已登记。Worker 在后续 IR 转换入口前停止，八个任务经 SQL 确认为 `running/parsed`，翻译启动调用和翻译批次均为 0。临时容器、数据库、凭据、Colima 环境与代码副本已清理。

```bash
PYTHONPATH=. CLONE_ACCEPTANCE_REPOSITORY_BASE=577726135d657bba909ea5fadd73e28e34a52bcb ../../../../.venv/bin/python -B ../run_docker.py
```

[八个组合的 SQL、请求与解析结果证据](../../../../../tests/tmp/direct-clone-mineru-pinned-translation-strategies-20261117/live-evidence.json)

## 固定 MySQL 镜像的 direct 显式文种重选复验

2026-11-17 在独立 Colima 环境使用仓库固定的 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`。容器检查确认实际摘要，SQL 确认 MySQL Community Server 8.4.9 与 InnoDB。验收使用 `57772613` 加本任务两个产品文件的隔离副本，复用公开中英文单页和本地生成的俄文单页。

三个源任务均为 direct + `auto`，其版本化快照均绑定 `latin`。各自创建两个克隆并显式指定 `zh`、`en` 或 `ru`。`use_current_defaults` 绑定默认模板 `default@2`；`select_published_versions` 显式绑定已发布的 `default@1`。完成创建后将 `MINERU_LANGUAGE` 从 `latin` 改为 `korean`，重新装配 Worker。解析前后从 SQL 读取 `request_snapshot.resources.mineru.language` 和模板版本，并核对真实请求语言与批次身份。

| 克隆文种 | 当前默认配置 SQL 冻结值 / 实际请求 | 显式发布版本 SQL 冻结值 / 实际请求 |
| --- | --- | --- |
| `zh` | `ch` / `ch` | `ch` / `ch` |
| `en` | `en` / `en` | `en` / `en` |
| `ru` | `east_slavic` / `east_slavic` | `east_slavic` / `east_slavic` |

六条真实 MinerU v4 请求均返回 HTTP 200、业务码 0，批次均达到 `done`，原始解析结果包均已登记。Worker 在后续 IR 转换入口前停止，SQL 确认六个任务均停于 `running/parsed`，翻译启动调用和翻译批次均为 0。临时容器、数据库、凭据、Colima 环境及代码副本已清理。

```bash
PYTHONPATH=. CLONE_ACCEPTANCE_REPOSITORY_BASE=577726135d657bba909ea5fadd73e28e34a52bcb ../../../../.venv/bin/python -B ../run_docker.py
```

[六个组合的 SQL、真实请求与解析证据](../../../../../tests/tmp/direct-clone-mineru-pinned-explicit-lang-20261117/live-evidence.json)

主工作区在隔离副本创建后由并行提交移至 `29592706`。启动命令最初把该时点的 HEAD 记作副本基线。已根据归档时间和 reflog 将证据中的归档基线校正为 `57772613`，并保留启动时 HEAD。
