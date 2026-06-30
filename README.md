# md2word

PDF 到 Word 转换与内部工作台项目。当前 P0 发布主链路是：

1. 上传 PDF：`POST /api/v1/files/upload-url` 后 `PUT /api/v1/files/{file_id}/content`
2. 创建任务：`POST /api/v1/document-jobs`，默认 `mode=direct_pdf_to_word`
3. 查询任务：`GET /api/v1/document-jobs/{job_id}` 和 `/events`
4. 下载结果：`GET /api/v1/document-jobs/{job_id}/download-url`

当前 P0 质量门槛聚焦技术 datasheet / 电子文档，不做泛 PDF。Golden Sample 阻塞验收套件是 `tests/fixtures/golden_samples/pdfs/` 下 4 个 OPA228 PDF：`OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf`、`OPA228_P7.pdf`。通过口径是接近原版排版并符合 Word 文档排版标准，最终由 admin 人工签字。

P1 beta 入口是 `mode=en2zh_pdf_to_word`，仍只面向技术 datasheet / 电子文档。P1 关注翻译 QA、术语治理、人工 review 和线上证据闭环，不重做 P0 Word 交付质量线。

P2 入口是内部单租户规模化与外部化：不扩展为 SaaS 或泛 PDF，而是补齐 hostdzire 部署追踪、线上门禁、运维可观测、任务治理和容量治理。P2 线上证据使用 `scripts/ops/run_p2_online_gate.py` 聚合 runtime readiness、metrics、ops alerts、release check、P0 preflight 和 P1 preflight。

## 发布与联调入口

- 后端运行手册：[docs/runbooks/backend.md](docs/runbooks/backend.md)
- 线上优先验证流程：[docs/deploy/online-first-validation-workflow.md](docs/deploy/online-first-validation-workflow.md)
- 正式内部门户说明：[docs/runbooks/internal-portal.md](docs/runbooks/internal-portal.md)
- P0 内部联调步骤：[docs/testing/pdf-to-word-p0-integration-guide.md](docs/testing/pdf-to-word-p0-integration-guide.md)
- Golden Sample 状态：[docs/testing/pdf-to-word-golden-sample-acceptance-report.md](docs/testing/pdf-to-word-golden-sample-acceptance-report.md)
- 本地 MinerU PyCharm 配置调试入口：[docs/dev/local-conversion-sandbox.md](docs/dev/local-conversion-sandbox.md)
- 本地电子元器件 direct/en2zh 调试计划：[docs/dev/local-component-pdf-debugging-implementation-plan.md](docs/dev/local-component-pdf-debugging-implementation-plan.md)
- 电子元器件样例回归治理：[docs/dev/component-pdf-regression-governance.md](docs/dev/component-pdf-regression-governance.md)
- API 清单：[docs/api/manifest.yaml](docs/api/manifest.yaml)
- OpenAPI 快照：[docs/api/openapi.json](docs/api/openapi.json)

本地变更阶段只做不依赖真实服务的检查，不在本机启动前端、后端、MySQL、Redis/Celery 或 Playwright smoke：

```bash
.venv/bin/python scripts/ops/check_release.py
```

准生产/生产发布按线上优先验证流程执行：先把本地变更同步到 hostdzire，再对运行中的 API 执行 `check_release.py --runtime-url <api-base-url> --golden-sample-preflight`，随后运行 Golden Sample 真实回归并由 admin 签字。

P1 翻译 beta 在线验证使用独立脚本，不混入 P0 Golden Sample：

```bash
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
```

P2 内部单租户线上门禁在 hostdzire 执行：

```bash
P2_ONLINE_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P2_ONLINE_PUBLIC_URL="https://md2word.962850.xyz" \
P2_ONLINE_ADMIN_TOKEN="${ADMIN_TOKEN}" \
.venv/bin/python scripts/ops/run_p2_online_gate.py --sync-acceptance
```

`--sync-acceptance` 会把本次 P2 gate 摘要写入 Acceptance Center 的
`acceptance_p2_online_gate_current`，只保存报告路径、blockers、warnings 和运行摘要。

前端工作台位于 `frontend/`。需要单独开发前端时可启动本地 dev server，但它不作为当前 P0 发布验收步骤：

```bash
cd frontend
npm run dev
```

如果是前端本地 UI 任务，需要运行 Playwright smoke 做页面回归，当前项目在 Codex/受限终端环境里应使用**非沙箱方式**启动本机默认浏览器，而不是依赖受限环境内的浏览器启动。推荐命令：

```bash
cd frontend
PW_CHROME_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
npm run test:smoke -- --grep "operations redesign renders verified desktop, tablet, and mobile screenshots"
```

补充约束：

- 多 viewport 截图 smoke 已按 `60s` 预算设计；不要再把该用例压回 `30s`，否则增加 `1024px` 等额外 viewport 后容易超时。
- 这类本地 smoke 只用于前端改动回归，不作为 P0 发布证据；P0 发布仍按线上优先验证流程在 hostdzire 收集正式证据。
