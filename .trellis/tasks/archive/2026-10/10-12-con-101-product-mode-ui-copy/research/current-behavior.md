# CON-101 当前行为与规划依据

调查日期：2026-10-12（America/Los_Angeles）。HEAD：`e03232e`；分支 `md2word/CON-101`。证据是当前源码、配置声明、测试定义和两项只读探针，未运行真实 API/Worker/DB，也未把 BAS-001 的测试结果记为本轮通过。

## 工作区与依赖

`pwd` 为 `/Users/sc/PycharmProjects/md2word`；初始 `git status --short` 仅 ` M .gitignore`。其 SHA-256 为 `b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`，不属于本任务，不修改、不暂存。

Manifest CON-101 起始为 `todo`；唯一直接依赖 BAS-001 为 `done`。`archive/2026-10/10-12-bas-001-current-capability-baseline/task.json` 为 `completed`，`meta.human_acceptance` 记载已接受 implementation/validation/residual_risks。DOC-001 也为 done，但没有为本任务增加依赖边。父任务已存在且 planning；未发现重复 CON-101。

按明确授权使用 `TZ=America/Los_Angeles task.py create ... --parent ...` 创建本子任务。create 自动设置会话规划指针，不等同 `task.py start`；任务状态始终 planning。父任务只增加 children 关系。

## 权威文档与历史边界

已调查用户指定的产品 PRD、scope-and-decisions、implementation-plan、完整 backlog、execution-guide、manifest、architecture-decisions、domain-model、workflows-and-state-machines、rollout-and-migration、quality-review-release-design，以及根 AGENTS、Trellis workflow 和 backend/frontend/guides 索引。

- 冻结五种模式、direct 无 AI、单主输出：PRD §4/FR-002/005/007、PD-001..005、ADR-001/002/003/007/014。
- 统一 review、quality/delivery、PublicationRecord 是目标能力。BAS-001 报告及当前 models/schemas/available actions 显示其尚未齐备；由 CON-102..104、QA-601/605 承担，不扩大 CON-101。
- 2026-07-23 `add-zh-translation-modes` 历史任务已完成五模式、四方向资源和 Prompt 工作区。历史 PRD 中旧称谓是当时事实，不回写归档。
- BAS-001 已验收 baseline 报告证明当时 release 202、前端 127 单测与构建通过；P1 preflight 缺认证、真实 MySQL/Word/线上未验证。这里只复用环境和入口信息，不声称 CON-101 已通过实现验证。

## 事实矩阵

| 证据位置（当前 HEAD） | 当前行为 | CON-101 处理 |
|---|---|---|
| `app/domains/translation/modes.py:11,45,130` | 五种 Literal；direct spec 的 language_pair/profile/prompt 都是 None；两种历史 alias 归一到 direct。 | 复用唯一模式 owner，保留所有已有 alias。 |
| `app/domains/document_jobs/schemas.py:17`；`router.py:102` | 创建字段为 canonical Literal；router 直接转发到 service，alias 在 schema 前置失败。 | 窄的请求归一化，不把类型放宽为任意 str。 |
| `service.py:2299` | 只传 translation_mode 使用公共 normalizer；同传两个字段按原始值比较。 | 内部一致性判断也消费规范值。 |
| `service.py:184,2374`；`translation/term_version_service.py:57` | direct 创建也调用 resolve_for_job；空值返回 None，显式 `en2zh@v1` 会 load_version。 | direct 提前拒绝新翻译资源选择并跳过术语服务。 |
| `jobs/resource_snapshots.py:69,260,296` | versioned direct 已拒绝 Profile/Term Set；legacy 无版本服务走其可用性检查。 | 在 DocumentJob 应用边界统一 direct 写入意图，避免存储路径差异。 |
| `service.py:2386,2399` | direct 不允许全文调试；Operator 不能启用；显式失败。 | 保持权限优先级，不静默忽略。 |
| `execution.py:770,836,2163` | direct 不进入翻译批次分支；执行术语加载按 language_pair 提前返回。 | 验证已有分流，不重构执行阶段。 |
| `service.py:622,694,1990,2109` | retry/clone 已有权限、策略与快照；keep_source_snapshot 不重新解析旧资源。 | 新显式 direct 选择同样拒绝，历史被动字段惰性保留。 |
| `frontend/src/utils/format.ts:49` | 共享五模式配置，direct label/shortLabel 为旧文案；能力布尔已区分资源和 QA。 | 更新名称，复用 shared helper。 |
| `PdfUploadPanel.vue:126,145,157,257,379,413` | 翻译选项、调试和默认卡已条件隐藏；切回 direct 清空；提交有模式守卫。 | 保留并补行为覆盖，不重建表单。 |
| `PdfUploadPanel.vue:208,239` | warnings 全量显示；direct 也提示首个未就绪方向的翻译配置。 | 仅过滤已知翻译配置 warning，保留未知/P0 blocker。 |
| `JobDetailPage.vue:128,219,904` | 翻译资源行、Provider 区、原始 request_snapshot 无模式投影。 | 条件展示和只读快照投影。 |
| `JobDetailPage.vue:613,703,719,1475,1525` | retry/clone 翻译选项和批次请求已有守卫。 | 复用并回归，隐藏空 Provider 区。 |
| `JobEventTimeline.vue:1` | 展示 message、stage、trace，不展示 payload JSON。 | 不改事件组件或删除审计。 |
| `frontend/src/api/types.ts:1359,1381`；`docs/api/openapi.json` | 规范枚举准确；创建字段缺 mode-specific 说明。 | 保持集合，补说明；由源生成 OpenAPI。 |
| `docs/api/document-jobs.md:74,111` | 五模式已列出；direct 说明和翻译字段适用范围未收口。 | 补名称、direct 示例、错误及资源适用范围。 |

搜索 `app frontend/src frontend/tests tests docs/api docs/dev README.md resources scripts`：无把“中译中”当产品入口的当前命中；alias 命中 modes.py、`scripts/dev/run_local_mineru_conversion.py:96`、`tests/runtime_direct_loaders.py:677`。后两者保留兼容，不删除。不能把文本扫描等同全部验收满足。

## 只读复现

以下命令 cwd 均为仓库根，退出码均 0。使用项目已安装 Pydantic，`-B` 不写 pycache；没有构造 Settings/runtime，没有网络、持久化或外部样本。

```bash
.venv/bin/python -B - <<'PY'
from app.domains.document_jobs.schemas import DocumentJobCreateRequest
from app.domains.translation.modes import normalize_translation_mode
from pydantic import ValidationError
for value in ('direct', 'zh2zh', 'zh_to_zh'):
    try:
        req = DocumentJobCreateRequest.model_validate({'source_file_id': 'file_probe', 'translation_mode': value})
        schema = req.translation_mode
    except ValidationError as exc:
        schema = exc.errors()[0]['type']
    print(f'{value}: normalizer={normalize_translation_mode(value)}, create_schema={schema}')
PY
```

输出：direct 为 `direct/direct`；两个 alias 为 `direct/literal_error`。结合 router/schema/错误处理判定 HTTP 将返回 422；本轮没有实发 HTTP。

```bash
.venv/bin/python -B - <<'PY'
from types import SimpleNamespace
from app.domains.document_jobs.service import DocumentJobService
calls = []
class ProbeTerms:
    def resolve_for_job(self, value, *, language_pair):
        calls.append((value, language_pair))
        return None
probe = SimpleNamespace(term_version_service=ProbeTerms())
for value in (None, 'en2zh@v1'):
    DocumentJobService._resolve_term_version_id(probe, 'direct_pdf_to_word', value)
print(calls)
PY
```

输出 `[(None, None), ('en2zh@v1', None)]`。证明 direct helper 仍委托翻译术语服务；真实加载路径由 TermVersionService 源码确认，探针没有读取术语数据。

## 配置、数据库、脚本和测试

- `app/core/config.py:98,115`：默认模式 direct、调试归档 false，是文件声明而非线上有效配置。未读取 `.env`、私有运行数据或凭据。
- `config_summary.py:28,187,214,264` 聚合各语言方向只读资源元数据，不调用 Provider；保留公共响应，UI 按当前模式显示。此配置查询与任务创建/执行零翻译服务调用区分。
- `models.py:87` 单 result_file_id；MySQL `document_jobs.py:31,53` 保存/读取模型 JSON payload；无需新列、迁移、回填或真实 DB 访问。数据库 Spec 明确当前是 bootstrap/maintenance，不是版本化 up/down migration。
- `scripts/ops/export_openapi.py` 支持隔离临时目录导出/`--check`；`check_release.py` 已含 OpenAPI、前端类型/mock 和 P0 测试，不建立新门禁工具。
- `tests/test_fastapi_jobs_backend.py` 有 direct 创建、四方向资源、模式冲突、权限、clone/retry、direct QA、Worker/AI 审计测试。缺 HTTP alias 和 direct 创建零术语调用断言。
- `frontend/src/utils/format.test.ts:186` 覆盖五模式能力，`documentJobConfig.test.ts` 覆盖默认资源/readiness；缺 direct 全页面隐藏和切换状态证据。
- `frontend/tests/smoke/core-flow.spec.ts:1963,1992` 有 mock API 上传测试，后者期待 direct 显示翻译配置缺失提示，须随新合同调整。
- `frontend/package.json` 使用 Vitest/vue-tsc/Vite/Playwright，没有 Vue Test Utils/jsdom。复用纯函数单测与 mock API Chrome smoke，不新增测试依赖，也不以源码正则冒充交互验证。
- `frontend/playwright.config.ts` 默认启动 3010 mock 前端。实现阶段必须区分无真实后端/Provider 的 UI 测试与禁止本地替代的 P0 线上证据；本轮未启动服务。

## 结论

不建议 `skipped_existing`：HTTP alias、direct 创建调用、名称、提示和详情展示均有差距。未发现需要改冻结决策、DB 或外部选择的阻塞。验证和风险约束以 [implement.md](../implement.md) 为准。
