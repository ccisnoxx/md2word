---
doc_type: roadmap
slug: mineru-online-ingestion
status: active
created: 2026-05-18
last_reviewed: 2026-05-18
tags: [mineru, pdf, callback, backend, ingestion]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# PDF 在线解析接入路线图

## 1. 背景

当前 `md2word_file` 后端已经完成第一期产品化：它可以接收 MinerU 输出 zip，走后台转换链路，支持 `direct` / `en2zh`、任务事件、产物下载、模板只读和本地运维动作。这个阶段的边界是“后处理入口已经稳定，但不负责前置 OCR/解析”。

接下来真正的大需求不是“再加几个 API”，而是把 **原始 PDF 上传 -> 提交 MinerU -> 等待 callback -> 下载结果 zip -> 复用现有后处理链** 这整条在线解析链路接进当前后端。这个需求明显超出单条 feature：它会引入新的任务状态、新的安全边界、新的外部依赖检查和新的恢复流程，所以应单独拆成一份 roadmap。

参考项目 `/Users/sc/PycharmProjects/create_pdf` 已经验证了这条路线可行，但也证明了真正复杂的地方在于：

- callback 鉴权和 checksum 校验
- 结果 zip URL allowlist
- callback 丢失后的恢复
- public/internal 两种部署模式
- 任务状态和后处理的衔接

本 roadmap 的目标，是把这些复杂度拆成可以独立推进的子 feature，而不是把它们混进当前 `POST /api/v1/jobs` 的 zip 上传合同里。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 新增 PDF 上传入口和 `source_pdf` 产物
- 新增 MinerU 提交 stage、callback ingress、结果恢复和状态推进
- 把 callback 安全、结果 URL allowlist 和健康检查落成明确合同
- 让 PDF 直传主链在成功拿到 MinerU 结果后复用现有 DOCX 后处理链

### 明确不做

- 不替换当前 `POST /api/v1/jobs` 的 MinerU zip 上传合同；它继续保留为后处理入口
- 不在本 roadmap 内解决 MySQL / OSS / 多实例 / Redis/Celery 这些部署层扩展
- 不在本 roadmap 内引入模板 CRUD 或术语规则后台编辑
- 不做“前端页面怎么改”的设计，只定义后端 API 和运行合同

## 3. 模块拆分（概设）

```text
mineru-online-ingestion
├── 提交入口模块：接收原始 PDF、登记 source_pdf、调度 submit_to_mineru
├── MinerU 交互模块：上传 PDF、记录 batch/data/seed、查询批次结果
├── callback ingress 模块：接收 callback、鉴权、验签、匹配任务、调度后处理
├── 结果恢复模块：callback 缺失时主动查询并复用后处理主链
└── 运行护栏模块：health、public/internal 模式、allowlist、错误码和排障文档
```

### 提交入口模块

- **职责**：新增 `POST /api/v1/jobs/pdf`，接收原始 PDF，创建 job，登记 `source_pdf`，调度 `submit_to_mineru`
- **承载的子 feature**：`pdf-upload-and-mineru-submission`
- **触碰的现有代码 / 模块**：`app/api/v1/routers/jobs.py`、`app/services/jobs/command.py`、`app/services/jobs/artifacts.py`、`app/core/job_models.py`

### MinerU 交互模块

- **职责**：封装 MinerU 上传、批次结果查询、callback seed 生成和结果 URL 基础校验
- **承载的子 feature**：`pdf-upload-and-mineru-submission`、`mineru-result-recovery`
- **触碰的现有代码 / 模块**：新增 `app/clients/mineru_client.py`，扩展 `app/services/jobs/stage.py`

### callback ingress 模块

- **职责**：新增 callback router，处理 internal / public 两种部署模式、token/query 鉴权、checksum 校验、payload 归一化和任务匹配
- **承载的子 feature**：`mineru-callback-ingress-and-guards`
- **触碰的现有代码 / 模块**：新增 `app/api/v1/routers/mineru_callbacks.py`、扩展 `app/api/dependencies.py`

### 结果恢复模块

- **职责**：当 callback 丢失时，允许对单任务主动查询 MinerU 结果并复用当前后处理链
- **承载的子 feature**：`mineru-result-recovery`
- **触碰的现有代码 / 模块**：`app/services/jobs/lifecycle.py`、`app/services/jobs/stage.py`

### 运行护栏模块

- **职责**：把外部依赖 readiness、public/internal 模式护栏、callback 安全边界、排障说明和 API 文档沉淀下来
- **承载的子 feature**：`pdf-ingestion-observability`
- **触碰的现有代码 / 模块**：`app/services/health_service.py`、`docs/`、`app/core/config.py`

## 4. 模块间接口契约 / 共享协议

### 4.1 原始 PDF 上传入口

**方向**：Client → 提交入口模块  
**形式**：HTTP API

**契约**：

```text
POST /api/v1/jobs/pdf
Content-Type: multipart/form-data
Form:
  pdf: file
  template_id: str | null
  translation_mode: "direct" | "en2zh" = "direct"
  document_language: "auto" | "zh" | "en" = "auto"
  use_mineru_header_footer: bool = false

201 Response:
{
  job_id: str,
  trace_id: str,
  status: "uploaded",
  translation_mode: "direct" | "en2zh"
}
```

**约束**：

- `pdf` 必须校验扩展名、content-type（可选）、文件头 `%PDF-` 和最大字节数
- 不修改现有 `POST /api/v1/jobs` 的 zip 上传语义
- 上传成功后只代表 job 已创建，不代表 MinerU 已返回结果

### 4.2 提交 MinerU stage 协议

**方向**：提交入口模块 → MinerU 交互模块  
**形式**：后台 stage + 函数调用

**契约**：

```python
JobStage = Literal[
    "convert_package",
    "submit_to_mineru",
    "process_callback",
    "recover_mineru_result",
]

def submit_to_mineru(job_id: str) -> MinerUSubmissionResult

class MinerUSubmissionResult:
    batch_id: str
    data_id: str
    callback_seed: str | None
    mineru_status: str
```

**约束**：

- 只有 `uploaded` / 可重提失败态允许执行 `submit_to_mineru`
- 若未配置 `MINERU_API_TOKEN`，行为必须明确：要么拒绝创建 `POST /jobs/pdf`，要么任务进入可解释的失败态；不能静默卡住
- callback URL 存在时必须为当前 job 生成独立 `callback_seed`

### 4.3 callback ingress 协议

**方向**：MinerU → callback ingress 模块  
**形式**：HTTP API

**契约**：

```text
POST /api/v1/mineru-callbacks/result
Body:
{
  "uid": "...",
  "batch_id": "...",
  "checksum": "...",
  "content": "{...json string...}"
}
```

归一化后至少产出：

```python
NormalizedMinerUCallback = {
    "batch_id": str | None,
    "data_id": str | None,
    "state": str | None,
    "full_zip_url": str | None,
    "data": dict | None,
}
```

**约束**：

- `PUBLIC_DEPLOYMENT_MODE=internal`：不要求 callback token
- `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`：必须校验 `X-MinerU-Callback-Token` 或 query token
- 若 payload 带 `checksum`，必须按 `uid + job.mineru_callback_seed + content` 校验
- `full_zip_url` 必须通过 `https + host allowlist`
- callback 匹配规则必须先尝试 `data_id`，再回退 `batch_id`

### 4.4 结果恢复协议

**方向**：运维调用方 → 结果恢复模块  
**形式**：HTTP API + 后台 stage

**契约**：

```text
POST /api/v1/jobs/{job_id}/recover-mineru-result
Body: { reason: str }
Response:
{
  job_id: str,
  operation: "recover-mineru-result",
  accepted: true,
  status: str,
  message: str,
}
```

**约束**：

- 只有已有 `mineru_batch_id` 且尚无 `mineru_result_zip_url` 的任务允许恢复
- 若结果命中 `done + full_zip_url`，必须复用既有后处理主链，而不是再实现一套平行渲染逻辑
- 若结果未命中或未终态，只记录事件，不推进后处理

### 4.5 共享数据结构 / 状态

```python
JobStatus = Literal[
    "uploaded",
    "submitting",
    "parsing",
    "parsed",
    "converting",
    "completed",
    "failed",
    "canceled",
]

class JobRecord(BaseModel):
    id: str
    source_filename: str
    status: JobStatus
    source_kind: Literal["mineru_package", "source_pdf"]
    translation_mode: Literal["direct", "en2zh"]
    mineru_batch_id: str | None
    mineru_data_id: str | None
    mineru_callback_seed: str | None
    mineru_status: str | None
    mineru_result_zip_url: str | None

class JobFile(BaseModel):
    file_type: Literal[
        "source_package",
        "source_pdf",
        "mineru_result_zip",
        "translation_request",
        "result_docx",
    ]
```

## 5. 子 feature 清单

1. **pdf-upload-and-mineru-submission** — 新增 `POST /api/v1/jobs/pdf`，接收原始 PDF、登记 `source_pdf`，并完成 MinerU 提交与 `batch_id/data_id/seed` 持久化。
   - 所属模块：提交入口模块 / MinerU 交互模块
   - 依赖：无
   - 状态：done
   - 对应 feature：`2026-05-18-pdf-upload-and-mineru-submission`
   - 备注：已完成；当前系统已支持把 PDF 成功送进 MinerU 并稳定停在 `parsing`

2. **mineru-callback-ingress-and-guards** — 新增 callback router、payload 归一化、internal/public 两种部署模式、token/query 鉴权、checksum 校验和结果 URL allowlist。
   - 所属模块：callback ingress 模块 / 运行护栏模块
   - 依赖：pdf-upload-and-mineru-submission
   - 状态：done
   - 对应 feature：`2026-05-18-mineru-callback-ingress-and-guards`
   - 备注：已完成；当前 callback 可按 `data_id -> batch_id` 匹配任务，执行 internal/public 鉴权、checksum 与 allowlist 校验，并把 `done/failed` 收口到 `parsed/failed`

3. **mineru-callback-postprocess** — callback 命中 `done + full_zip_url` 后复用当前后处理主链，下载 zip、提取 markdown 和生成 DOCX。
   - 所属模块：callback ingress 模块 / Conversion Library
   - 依赖：mineru-callback-ingress-and-guards
   - 状态：planned
   - 对应 feature：未启动
   - 备注：不允许实现第二套平行渲染路径

4. **mineru-result-recovery** — 新增单任务 `recover-mineru-result`，支持 callback 丢失后的主动恢复。
   - 所属模块：结果恢复模块
   - 依赖：pdf-upload-and-mineru-submission, mineru-callback-postprocess
   - 状态：planned
   - 对应 feature：未启动
   - 备注：恢复成功时必须复用 callback 后处理主链

5. **pdf-ingestion-observability** — 更新 health 字段、任务事件、runbook、错误码和 API 文档，把在线解析相关排障口径落盘。
   - 所属模块：运行护栏模块
   - 依赖：mineru-callback-ingress-and-guards
   - 状态：planned
   - 对应 feature：未启动
   - 备注：这条要覆盖 internal/public 模式下的差异化 readiness

**最小闭环**：第 1 条 `pdf-upload-and-mineru-submission` 完成后，用户可以上传原始 PDF，并在任务详情里看到 `batch_id/data_id` 和 `parsing` 状态。

## 6. 排期思路

第一条只做到“送进 MinerU”，故意不掺 callback 和后处理，是为了把最容易验证的前半程单独跑通。第二条单独处理 callback 安全和归一化，因为这是最容易把整条链路做脏的部分。第三条再把 callback 成功结果接回当前后处理主链。第四条解决 callback 不可靠时的恢复能力。最后一条把 health、错误码、事件和文档补齐，防止“代码能跑、但运维看不懂”。

## 7. 观察项

- 当前 `fastapi-backend` 已稳定提供 MinerU zip 后处理入口；新增 PDF 入口时，前端和调用方必须明确区分 `/jobs` 与 `/jobs/pdf` 的语义。
- 若未来引入 MySQL 或 OSS，在线解析链路的 job 状态和 artifact 合同还会进一步扩展，这不在本 roadmap 当前范围内。
- `create_pdf` 里还包含更复杂的 `JOBS_ACCESS_MODE`、`PUBLIC_DEPLOYMENT_MODE`、回调 query token 兼容、allowlist 等运行口径；当前 roadmap 只选最必要的后端合同，不直接照搬全部外围能力。
