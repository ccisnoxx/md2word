# Worker 实际环境、灰度启用与回滚

- 核对 Worker 启动、Poppler 取证来源、开关粒度和回滚时的同包意图。
- 依据当前工作树的应用、编排、规范与第四阶段归档。运行时探针和验收步骤供后续执行。
- 调查日期为 2026-11-15。

## 调查结果

### Worker 镜像与 Poppler

| 文件 | 证据 |
| --- | --- |
| `docker/prod/docker-compose.yml:4–64,66–104` | 标准生产编排使用 Uvicorn 和独立 Celery Worker，两者引用同一 `MD2WORD_IMAGE`，读根目录 `.env` 并共享 `/app/var`。标准编排共用 MySQL 与 Redis。 |
| `docker/prod/Dockerfile:2,10–13,21–32` | Debian 基础镜像固定 digest，`poppler-utils` 由 apt 安装且未锁包版本，运行用户是 `md2word`。重建与已运行的镜像都需要核对实际版本。 |
| `scripts/dev/run_document_worker.py:34–74`、`docs/runbooks/backend.md:82–94` | 正式 Worker 启动及 API readiness 的裁图检查核对 `pdfinfo` 和 `pdftoppm`。该检查覆盖裁图依赖。 |
| `app/services/document_ir/pdf_value_column_observer.py:75–103,579–621` | 参数列取证在 Worker 的 PATH 查 `pdfinfo`、`pdftotext`、`pdftocairo`、`pdftohtml`，以 `LC_ALL=C` 读取 `-v` 的 stderr。四工具须分别解析出同一版本并成功输出页面框、文字 bbox、渲染文字 XML 和 SVG。观测记录的版本形如 `poppler-value-geometry/v1:<版本>`。 |
| `app/domains/document_jobs/execution.py:346–378`、`.trellis/spec/backend/word-generation-rules.md:404–408` | 可选取证按单任务最多 60 秒和剩余时限的一半取较小值。超时或证据不足保留未决和原质量 blocker。 |
| `.trellis/tasks/archive/2026-11/11-15-table-value-pdf-binding-online/validation.md:3–31` | 第四阶段实物用本地 Poppler `26.06.0`。完整 `gs-008` 认证 9/23，14 项仍阻断。独立 LOW/HIGH 划线表验证了 Word 落位、未决阻断和同包人工核定后的放行。真实 MinerU 外部传输、实际部署 Worker 和真实 MySQL 仍待验收。 |

后续预检先确定目标环境的编排项目、release 和实际运行实例。读取每个 API 副本和每个能执行 `document_jobs.run` 的 Worker，记录 image ID、已知发布制品的 digest、启动时间、应用版本和配置结果。每个目标 Worker 的四项 Poppler CLI 都应能在服务用户 PATH 上执行，版本在单个运行实例内一致。同一灰度批次用统一已验收 image ID，方便把几何差异归因到同一个构建。目标 Worker 的版本可以与本地 `26.06.0` 不同，由目标镜像下的两种表格版式和实际 Word 证据判定兼容性。生产编排指纹和候选镜像指纹分别记录。获准预检时对照 `docs/deploy/p0-docker-deployment.md:44–71,128–150` 和 `docs/runbooks/backend.md:98–106`，避免根据标签、主机安装版本或本地 Dockerfile 推断容器内容。

以下命令是后续只读窗口的探针示例。在已确认项目、Compose 文件和服务名的上下文运行，按实际环境调整服务名。容器 ID 逐一探测，保留白名单列及探针时间。

```bash
docker compose --env-file "$rollout_env_file" -f "$rollout_compose_file" ps -q api worker
docker inspect --format 'image_id={{.Image}} state={{.State.Status}} started_at={{.State.StartedAt}}' "$rollout_container_id"
docker exec -i "$rollout_container_id" python - <<'SETTINGS_PY'
try:
    from app.core.config import Settings
    settings = Settings()
    enabled = settings.document_table_value_pdf_binding_enabled
except Exception:
    print("settings_status=unverified")
    raise SystemExit(1) from None
print("binding_enabled=" + str(enabled).lower())
print("worker_backend=" + settings.document_jobs_worker_backend)
SETTINGS_PY
```

读取有效配置时遇到配置解析失败，仅记录失败状态和后续在授权环境内核查。应用版本和部署标识可使用现有 API Ready 的 `deployment.version`、`deployment.deployment_id`、`deployment.started_at`，同时核对每个服务实例实际加载的制品。Exec 建出的 `Settings` 只能观测该容器同环境下的新实例。API 工作路径仍需通过来源为授权测试任务的正式请求或已批准的预生产验收证明运行策略已生效。

```bash
docker exec -i "$rollout_worker_id" python - <<'PY'
import os
import re
import shutil
import subprocess

versions = []
for name in ("pdfinfo", "pdftotext", "pdftocairo", "pdftohtml"):
    path = shutil.which(name)
    if path is None:
        print(f"tool={name} status=missing")
        continue
    try:
        result = subprocess.run([path, "-v"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, env={**os.environ, "LC_ALL": "C"},
                                timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        print(f"tool={name} path={path} status=unavailable")
        continue
    match = re.match(rb"[\w]+\s+version\s+([\d.]+)(?:\r?\n| )", result.stderr)
    if result.returncode or match is None:
        print(f"tool={name} path={path} status=unverified")
        continue
    version = match[1].decode("ascii")
    versions.append(version)
    print(f"tool={name} path={path} poppler_version={version}")
verified = len(versions) == 4 and len(set(versions)) == 1
print(f"poppler_versions_verified={str(verified).lower()}")
raise SystemExit(0 if verified else 1)
PY
```

探针输出限于制品标识、角色、开关布尔量、Worker 模式和工具名/路径/版本。Celery broker URL、容器全量环境、`.env`、MinerU 配置和客户文件信息均无需进入证据。四工具版本一致后，再用候选 Worker 重读同源的完整 `gs-008` 和独立 LOW/HIGH，分别保留观测版本、最终 Word 主件摘要、列归属及认证和未决计数。

### 开关读取与覆盖路径

| 路径 | 当前行为 |
| --- | --- |
| `app/core/config.py:24–31,74–76`、`app/main.py:37–50,109–122,151–166` | `DOCUMENT_TABLE_VALUE_PDF_BINDING_ENABLED` 是 `Settings` 的环境布尔量，默认 `false`。API 初始化时构造运行时与发布用例。 |
| `app/workers/document_tasks.py:19–30,45–54`、`scripts/dev/run_document_worker.py:34–74` | Worker 启动时确定队列，每次 Celery 任务调用重新构造运行时和 `Settings`，轮询续投及 Worker 就绪恢复也在相应运行环境里重新解析。标准生产 Compose 将宿主 `.env` 注入容器。改宿主文件或只重启原容器不重建其注入环境。 |
| `app/domains/document_jobs/execution.py:151–195,305–335,346–378` | 同一执行骨架在原排版进入 IR 时选择自动绑定。未传同包意图时以本次执行设置为准。已有本代 IR 直接续渲染。翻译路径遵循自己的阶段合同。 |
| `app/domains/document_jobs/use_cases/publication.py:148–199,210–231` | 管理员同包请求先按原 UUID 和提交摘要对账，再检查开关及原排版资格，最后冻结来源和核定记录。关开关后原 UUID 同内容仍返回既有接纳，新的核定意图会得到 `409 table_value_column_review_disabled`。 |
| `app/composition/document_pipeline.py:58–68,142–176`、`app/domains/document_jobs/execution.py:750–795`、`app/workers/celery_app.py:24–36` | `celery` 使用单个配置的 document-job 队列，`eager` 在当前 API 进程执行同一骨架。`DOCUMENT_JOBS_WORKER_BACKEND` 决定这里的执行接入，健康响应中的 `jobs_worker_mode` 不能单独证明 Celery 实际被消费。 |
| `app/domains/jobs/mineru_callbacks_router.py:35–55`、`app/domains/document_jobs/recovery.py:245–307`、`app/domains/ops/router.py:102–135` | 回调先保存后按配置续投，传 `run_inline=False`。API 启动恢复及管理员恢复沿共享队列端口，API 启动恢复在 eager 配置设 `run_inline=True`。Worker 侧无 callback URL 时也会在就绪后扫描可轮询任务。 |

Worker 消费按收到的 `job_id` 查持久化任务。当前两个开关调用点没有租户或公司筛选。默认队列送入同一批消费者，同一任务的首次投递、轮询以及恢复都可能被不同实例处理。把开启和关闭的 Worker 接到同一队列，分配取决于取件时序，无法稳定限定到试点公司。API 入口的限流或流量切分也不能约束已在库中的恢复任务。

### 预生产与真实生产灰度

1. 用生产候选的固定镜像身份建立隔离的预生产 API 与 Worker。通过正式 HTTP 上传、真实 MinerU 回包、正式 Celery 和预生产的审批发布运行验收。使用隔离 MySQL schema 和账号、独立 Redis/队列、独立对象存储根或前缀和 callback 目的地。API/Worker 共享各自测试环境的一套配置，禁止交叉读写。关闭开关验证原路径，开启开关验证同源、Word 实物、未决门禁和同包放行。生产准入另外需要真实 MySQL 并发和审批重核窗口的审计结果。
2. 生产首轮如果要求固定试点公司，需要明确选择隔离整套生产试点入口及数据，或在共享生产栈增加一个最小的、服务端控制的 `(tenant_id, company_id)` 白名单。共享栈优先后一方案。API 的新同包接纳和任何 Worker/eager 的普通绑定使用同一策略，归属来自已鉴权且持久化的 job。全局开关保留总闸作用。建议灰度模式下空表默认无人启用，稳定窗口内各 API/Worker 的策略版本一致，试点外控制样本按关闭路径处理，已接纳意图继续按冻结来源执行。仓库当前没有这项白名单。
3. 经另行授权后，所有 API、Worker 和恢复执行者先使用通过兼容性验收的候选镜像并保持开关关闭。待实例、队列和配置收敛再用单个内部试点归属验证自动绑定、管理员人工同包、无资格普通对照、回调/轮询续投和恢复。扩围仍用同一不可变候选镜像，按试点名单滚动安排，保留每次切换的生效时间。启用前保留一组关闭状态的输入、报表和耗时作对照。
4. 灰度升档前核对每个认证项与当前 Word 格位一致，未决项仍出现在表格质量接口，错配原件没有自动解除，试点外没有新增认证与重生成接纳。观察来源待核和预算耗尽的计数、转换耗时、Worker 任务超时、队列积压以及 MySQL 锁超时/死锁。以关闭窗口的同版对照判断性能偏差；出现任何错误解除、越出试点或审批发布绕过即停止扩围并进入回滚对账。

### 回滚和恢复确认

1. 首选保留同一兼容镜像、冻结试点扩围及新同包接纳，随后把总开关恢复为 `false` 并让 API 与所有执行者使用已核对的运行配置。在切换边界先记录各试点在途代次、已接纳 UUID 及状态。用候选保持默认关闭的 read/approve/publish 合同作回滚基线。
2. 已进入 `_convert_and_save_document_ir()` 的执行按既定分支完成。已有同代 IR 的渲染恢复使用已持久化 IR。已接纳的人工核定即使尚未投递，也保留 UUID、执行摘要和冻结的 PDF/raw 指针，按原代次对账。一般停用可让已接纳的处理在兼容 Worker 继续。若因证据错误或审批绕过回滚，先暂停可能受影响的消费、内联和恢复，隔离相关代次的审批发布，待逐件对账后决定何时恢复。关开关本身不撤回既有认证或批准，也不变更已经登记的不可变发布件。
3. 版本回退前验证目标 API 和 Worker 能重读、保留并对账新代账本、核定意图、结果 receipt、质量实物引用及在途阶段。`app/domains/document_jobs/new_generation.py:117–185,304–366` 的私有账本使用 `extra="forbid"` 并复核 job 归属和执行摘要。较早版本能读普通任务并不足以证明能读这些记录。按 `.trellis/spec/backend/document-job-mode-contract.md:110–116,134–138` 与 `.trellis/spec/backend/database-guidelines.md:140–149`，只允许兼容版本继续消费。若仅有已验证读兼容的旧镜像，停止全部 DocumentJob 消费和内联执行，保留依赖、字节、状态和审计，待兼容执行者恢复。不得通过删字段、清队列、换新 UUID 或覆盖历史 Word 来解除卡点。
4. 最小回滚确认是逐实例重读开关/镜像及启动时间，并对切换前登记的同一 UUID、现有主件和质量记录作只读对账。在隔离环境用关开关后首次进入 IR 的原排版代确认无新自动认证，原 blocker 保留；用关开关前的已接纳 UUID 验证回执可重读、同包复用和后续审计可追踪。分开记录尚未处理的意图、已完成在途和关开关后新进入的普通代。

## 待实测证据

- 标准生产 Compose、部署手册与第四阶段归档提供配置和本地证据。实际运行镜像、Poppler 四工具版本、真实上游原件配对及线上配置在本轮待实测。
- 当前仓库只提供全局开关。隔离预生产可以用已有入口完成。固定公司灰度需要独立环境边界或已验收的白名单，混跑相同队列无法替代这项隔离。
- 回滚涉及审批重核窗口、真实 MySQL 和发布时点的结果，以本任务对应研究和后续实际验收为准。
