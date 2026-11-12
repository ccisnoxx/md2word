# B3 用途与静态入口准备

日期：2026-11-10。HEAD：`d45e46e1233c3f173fa1d738cf75b3ef7a393eb9`。B2 整批独立复核通过后，主会话已正式授权 B3 写入。本记录先于维护文档变更形成；51 份全文已读。

本批仅核对文档用途、原字段、入口挂载/参数声明及明确的旧说明差异。没有导入运行应用、执行文中命令、调用 API/Provider/数据库或访问生产。代码入口的归属指文件/模块，不表示确认了人类 owner。全部文档 owner 与 last_verified_commit 保持 null；局部静态证据不足以认证全篇，且存在已知未提交依赖。

## 51 份文档逐份分类

分类：{'active': 39, 'superseded': 7, 'draft': 2, 'historical': 3}。分类依据内容用途，原 status/日期等字段完整保留。

| 相对路径 | doc_status | 原 doc_type / status / 复核日期 | 用途与边界 | 实施前 SHA-256 |
|---|---|---|---|---|
| `docs/api/acceptance.md` | active | lib-api-ref / current / 2026-06-21 | 验收摘要索引 API；starter 仅历史引导，不是新的发布通过证据 | `7108b1d94222cc70816b9bdacd924f60262d8d3ca37706fdda726efe96896c33` |
| `docs/api/auth.md` | active | lib-api-ref / current / 2026-06-21 | 内部登录、当前用户与自助密码 API 参考 | `bae2a610ff791ed8f2f16b3fcfb21e9e95bda2e327e3906c830da2216e34703b` |
| `docs/api/config-workbench.md` | active | lib-api-ref / current / 2026-06-10 | 只读配置中心聚合 API 参考 | `85a21b204a0b7361cea9a536ee2f262b23a66d073d8ae0ab590849146cbb7317` |
| `docs/api/document-jobs.md` | active | lib-api-ref / current / 2026-10-22 | 正式任务 API 与质量/复核/交付状态参考；原末尾 Golden blocked 不是本次验收结论 | `ef5bfbb5f81c29e4dba48b35b213ed3332367fbe1ab1f19eaab32b5c8fc23da0` |
| `docs/api/files.md` | active | lib-api-ref / current / 2026-06-07 | 上传、文件元数据、quota 与受控 retention API 参考 | `dcfc5a4b27d921be9011d90101fd487ea6bde3e62257d4f7ea510c953128888a` |
| `docs/api/health.md` | active | lib-api-ref / current / 2026-06-06 | live/ready/metrics 与只读告警 API 参考；示例部署数据不是当前观测 | `1fb1248d7cda91ee47bfea9f81f7403fdba4822307cbee51046579474f7a9128` |
| `docs/api/jobs.md` | superseded | lib-api-ref / removed / 2026-06-11 | 旧 Jobs API 移除入口；明确替代为 docs/api/files.md 与 docs/api/document-jobs.md | `4e6cf9fe84764048984588b7b0e62081d63f447ed97f681b330059c75b939015` |
| `docs/api/manifest.yaml` | active | api-manifest / current / 2026-07-10 | API/开发资料索引；原 entries/guides/OpenAPI 状态保留，不能覆盖被引用文档的用途 | `d593caf8f33bf42e0be774065edf79f8aef3a4ce775cb24d0cd564b8bb9b929d` |
| `docs/api/mineru-callbacks.md` | active | lib-api-ref / current / 2026-11-06 | 正式 MinerU callback 入口、checksum 与结果 URL 边界参考 | `bde29f985a87f7fc19be3a3bf8d715654b9fdc80a2cb2a7eea29b403a8315bc3` |
| `docs/api/mineru-config.md` | active | lib-api-ref / current / 2026-07-10 | MinerU 账号与密钥绑定配置 API 参考 | `7710e3f68d7e561e76e37c8462c6869c21f62c4b8844e76810f8494e9d23231f` |
| `docs/api/ops.md` | active | — / — / — | 运维 registry/preview/fake/pilot API 参考；历史 pilot 不代表当前真实发送启用 | `4d7f12dce6faf29cb3b721f4534e78abcbf2734cd86f129ae1fd80cad3a8fdf9` |
| `docs/api/templates.md` | active | lib-api-ref / current / 2026-07-11 | 模板文档/样式草稿/资源版本治理 API 参考 | `c8239460b086e64cf2627f1bd87da24998076e65d429b23e98c2dbbc483e40b1` |
| `docs/api/term-rule-categories.md` | active | lib-api-ref / current / 2026-05-31 | 术语分类 API 参考；旧写保护说明未在本批逐字段重验 | `28c0890488ee0ce068c02609f162c8b6fd0086478fdeb1a450db5ced5cfa1109` |
| `docs/api/term-rule-sets.md` | active | lib-api-ref / current / 2026-06-21 | Term Rule Set 草稿与发布流程 API 参考 | `67fcf9d836d2f601d1558d30b56d9d8308983eca46b9488015888896a8047a09` |
| `docs/api/term-rules.md` | active | lib-api-ref / current / 2026-06-04 | 术语规则与 proposal API 参考 | `1a9c1c03bcb6a27be0fc36599971b247f35f06b0365613432e8a510d98d4c3d7` |
| `docs/api/translation-profiles.md` | active | lib-api-ref / current / 2026-07-23 | 翻译配置和命名 Prompt 版本 API 参考 | `9eeb69cc405f224768217a2e8cf1adaebd1883260334c7d9357f5050ef5707e7` |
| `docs/api/translation-term-proposals.md` | active | lib-api-ref / current / 2026-06-02 | 翻译术语建议与审核 API 参考 | `d27e3986b3f5edb536295c12924e271e8084c0dd051cf17509f890e161b64395` |
| `docs/api/translation-term-sets.md` | active | lib-api-ref / current / 2026-06-04 | 翻译术语集/草稿/导入导出 API 参考 | `4b244f6b4bdbf4ff2c32c135dc89a424e349a40062d58fe042d84d20f7d714e6` |
| `docs/api/users.md` | active | lib-api-ref / current / 2026-06-21 | 托管内部用户管理 API 参考 | `2df56ba0f1e53bbffeb14109e580806fdc074c567665e5c8c794d7ad0b19c985` |
| `docs/dev/backend-architecture-baseline-and-issues.md` | draft | dev-guide / draft / 2026-05-28 | 2026-05-28 legacy Jobs 架构草稿；未冻结方案不作为现行主线事实 | `0d64d2ea70ee3d34487b28b2ad6bd71dbb7fd4a994a3e05cecbeccc33651dff4` |
| `docs/dev/backend-design-implementation-plan.md` | draft | dev-guide / draft / 2026-05-28 | 2026-05-28 后端阶段草稿；原 checklist 是原记录，不重判当前完成 | `8059462f15d202614dc38448ceeadcfe1f96bc06e40221bfc7a28a2bad213ccf` |
| `docs/dev/backend-dev-docs-index.md` | active | dev-guide / current / 2026-06-30 | 后端开发导航；链接目标的 doc_status/适用范围优先于旧推荐次序 | `c4162eab9a7e3ccc2d8ed1b7c90a379888ff4afeaa8bbedcd12ad5636e5dfb8c` |
| `docs/dev/backend-local-minimal-env-and-commands.md` | active | dev-guide / current / 2026-05-29 | 本地配置速查；夹杂旧启动/StageWorker/token 示例，入口改看 runbook 的适用说明 | `6d47bd04803c40e7320ee40fa0cbaeb42060986507a8ce7ec0e0b5bae84ed91e` |
| `docs/dev/backend-local-setup-and-architecture.md` | active | dev-guide / current / 2026-05-31 | 正式后端本地结构与 Files + Document Jobs 接手说明 | `fdcd99b94502353a080a473f81aefbb1cd4443a450e6af3fb1832d817ce8aa42` |
| `docs/dev/backend-pdf-online-completion-change-summary.md` | superseded | dev-note / deferred / 2026-06-30 | 已明确不维护的变更总结占位；替代为 backend 架构/计划及 docs/runbooks/backend.md | `c7b67c736a56b29cbb5168f6355191e64a85e749ee3c517ceaac7c78b5c11c10` |
| `docs/dev/component-pdf-regression-governance.md` | active | dev-guide / current / 2026-06-26 | 电子元器件本地样例治理与回归程序；不构成执行证据 | `a82166ec204cc278f532f2685a1cf9e7611197d888601b30302695e2572de61f` |
| `docs/dev/document-ir-v1.md` | superseded | dev-note / deferred / 2026-06-30 | 空的旧 v1 主题入口；明确替代为 docs/dev/document-ir-v2.md | `42e9d9a05e4a0f4e9b8db1141755e7ee4d351cc0b9e95d00a9ddba9798364d99` |
| `docs/dev/document-ir-v2.md` | active | dev-guide / current / 2026-06-03 | v2 布局事实开发参考；与 docs/contracts/document-ir-contract.md 配合使用 | `433f9e67daa9c28f3e556301d2a99789668c1e7d8ba05344c9b51fbfe3f4f1cc` |
| `docs/dev/local-component-pdf-debugging-implementation-plan.md` | active | dev-guide / current / 2026-06-26 | 本地 PDF 调试阶段目标与流程；准入条件不表示已经满足 | `02bd6f1ea6698dd636a3e8560b06519226e18c8b977e6009849f3f7c295696b1` |
| `docs/dev/local-conversion-sandbox.md` | active | dev-guide / current / 2026-10-21 | 正式本地 MinerU 调试适配器、矩阵及视觉证据流程 | `7f0f68b3efb960e8d0ae9531249c573d4145255786bcba3079dea07f48d87544` |
| `docs/dev/repository-hygiene.md` | active | — / — / — | 已有卫生工具说明；仅追加元数据，保留正文与原扫描结论 | `ee255a925be7fde0e0589bdd767958a42e384cfa8bedbdea9311e3dcfd8fe8d4` |
| `docs/dev/runtime-observability-and-health.md` | active | dev-guide / current / 2026-05-28 | 正式任务日志/健康观察参考；旧 callback token 排障不能代替 checksum 合同 | `40fa134f7a37b3d40f53e491ec40b89d6dc4b169bfa7245c4b2c45b348549e34` |
| `docs/dev/template-config-package-v1.md` | superseded | dev-note / deferred / 2026-06-30 | 不维护的配置包占位；替代为 docs/api/templates.md 与 docs/runbooks/backend.md | `c9f9b4384b11e0bc32782cf0df88f01a18533795c017c4a80b5b19fb2a2d3fee` |
| `docs/dev/term-assets-sql-versioning-tasks.md` | historical | dev-note / deferred / 2026-06-30 | 原 deferred 任务主题占位，无现行任务 AC；未来须在相应 Trellis 任务重新规划 | `19f233615a5b04cef7e6503450c751a97b3b4f7b5f37fce9e9e46fb6a10f65b4` |
| `docs/dev/term-assets-sql-versioning.md` | superseded | dev-note / deferred / 2026-06-30 | 旧 SQL 主题占位；替代为 term-rule-set-versioning-guide.md 与 translation-profile-and-segment-trace-guide.md | `98cf1d99e5fe715b73336e1f85600388f7a3a539318934ed3c222c41df6b7ade` |
| `docs/dev/term-rule-set-versioning-guide.md` | active | dev-guide / current / 2026-05-29 | 术语规则集版本管理程序；示例鉴权/版本不是现环境执行事实 | `483a61c00fb6950b034cf1b33bcf45c7f014e77632ff3da474e8c4e9b8891ee5` |
| `docs/dev/translation-ai-audit-debug.md` | superseded | dev-note / deferred / 2026-06-30 | 旧审计调试占位；替代为 translation-profile-and-segment-trace-guide.md 与 docs/runbooks/backend.md | `d3b7492703a7632c7b80d44d4b822ea5a367532ffad455a6645e19612aea1e83` |
| `docs/dev/translation-profile-and-segment-trace-guide.md` | active | dev-guide / current / 2026-07-23 | 翻译配置与片段 trace 集成指南 | `3992281297d31d0d93e52846eed88c775fd6e5578a3e9d5d5082d08549edbc4c` |
| `docs/dev/translation-terms-v1.md` | superseded | dev-note / deferred / 2026-06-30 | 旧 v1 主题占位；替代为 docs/api/translation-term-sets.md 与现行翻译配置指南 | `ecb40500b83419432e7815c9b8dbe3c79b7e9c5c5d4b4ef30c33ef257864e308` |
| `docs/runbooks/backend.md` | active | dev-guide / current / 2026-06-17 | 后端专项开发/部署/迁移程序；命令不自动授予运行授权 | `bc65f45eb2df3bb0f78ce587f72eb01b1f998922283ba488aaeb7f2e4196bd7a` |
| `docs/runbooks/internal-portal.md` | active | runbook / current / 2026-06-21 | 内部角色、页面/API 地图及账号运营程序；部署示例适用范围由维护部署说明限定 | `ab76f68f96c51d4a41fc88a670567f7bb0033b45db2716f76c2fa01ad61ed788` |
| `docs/testing/md2word-fe-be-integration-acceptance.md` | active | integration-acceptance / current / 2026-06-17 | 联调计划与验收模板；第 9 节仅保留 2026-06-10 原执行声明 | `05d4fb41be89757e26e9f8a510ca3ab3a97683e4405d5d73d8577d0b40ec1f81` |
| `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md` | historical | test-report / current / 2026-06-03 | 20260603T070724Z 四样本人工 triage 记录；原未通过 P0 结论限定该批次 | `cd4c1966f68c83860673649164856552fd3a82b879c5d843beb5fee208e22be2` |
| `docs/testing/pdf-to-word-gs-003-quality-triage.md` | historical | test-report / current / 2026-06-02 | 20260602T071017Z gs-003 与旧 sandbox 基线；历史命令不恢复为现行入口 | `7a2159fbe11f452ca7f078bd7f16e2ef6b78daabd4a48c19b50675feb3349e48` |
| `docs/testing/pdf-to-word-p0-integration-guide.md` | active | integration-guide / current / 2026-06-17 | P0 人工联调程序与 Golden 签字流程；不是新运行报告 | `00ab95424f81e8a90e2326adb220bd33f6569addb2ea9889520d252f09307e35` |
| `tests/fixtures/component_pdf_samples/README.md` | active | — / — / — | 本地组件 PDF 样例目录说明；转换职责以现行组件治理页为准 | `7b124b858f5647181ec772a07599d44a1178055439e6df1db05a3c710b53e5a8` |
| `tests/fixtures/component_pdf_samples/acceptance-record-template.md` | active | — / — / — | 本地样例人工验收空白模板；所有勾选/结论须由实际运行证据填写 | `146ad00d17205cb016cedc44f59ac0509ef193a4011f92b5c1b345ac2724dc40` |
| `tests/fixtures/golden_samples/README.md` | active | — / — / — | P0 canonical suite 与脚本程序说明；available 标签不是运行通过 | `b9cf20ff8e98b9ef454433b93d819f94faf886925cda9d0634f1f7866f6ff243` |
| `tests/fixtures/golden_samples/acceptance-record-template.md` | active | test-template / current / 2026-05-29 | Golden 人工验收/签字模板；空白栏和示例不能视为真实签字 | `56475224829c7149f412f696235492c8a977257257c0d7b32e1a8b3642ba57dc` |
| `tests/fixtures/p1_translation_samples/README.md` | active | — / — / — | P1 英译中样例与 formal beta 程序说明 | `a5c2efe15fb45d900456cffe6ad7c5f19350ef55b7ee1efe42f0c012683a93d4` |
| `tests/fixtures/p1_translation_samples/acceptance-record-template.md` | active | test-template / current / 2026-05-30 | P1 翻译验收空白模板；不是历史或当前执行报告 | `a5377ab92c1cdff195fd67c4813c9f39f778eefba3a5e0398f982a26072c1626` |

## 当前 API 静态入口

已读取 `app/api/v1/router.py` 的导入与 include_router：本批 17 个现行 API family 的 router 仍在 `/api/v1` 下挂载；旧 `/jobs` 未挂载。下表给本文件各 router 的直接装饰器数量与一个入口；Document Jobs 合计包含同文件主 router 24、quality 子 router 9、new_generation 子 router 2、publication 子 router 4，共 39。此计数不声称覆盖其他文件动态注册端点、API schema 一致性或运行鉴权通过。

| API family | 实际 owner 文件 | prefix | 直接装饰器数 | 示例入口 |
|---|---|---|---|---|
| `acceptance` | `app/domains/acceptance/router.py` | `/acceptance` | 5 | `GET /api/v1/acceptance/runs`（定义行 30） |
| `auth` | `app/api/v1/routers/auth.py` | `/auth` | 3 | `POST /api/v1/auth/login`（定义行 34） |
| `config-workbench` | `app/domains/config_workbench/router.py` | `/config-workbench` | 2 | `GET /api/v1/config-workbench/summary`（定义行 28） |
| `document-jobs` | `app/domains/document_jobs/router.py` | `/document-jobs` | 39（含同文件子 router） | `POST /api/v1/document-jobs`（定义行 135） |
| `files` | `app/domains/files/router.py` | `/files` | 24 | `POST /api/v1/files/upload-url`（定义行 102） |
| `health` | `app/api/v1/routers/health.py` | `/health` | 5 | `GET /api/v1/health/live`（定义行 22） |
| `mineru-callbacks` | `app/domains/jobs/mineru_callbacks_router.py` | `/mineru-callbacks` | 1 | `POST /api/v1/mineru-callbacks/result`（定义行 29） |
| `mineru-config` | `app/domains/mineru/router.py` | `/mineru-config` | 2 | `GET /api/v1/mineru-config`（定义行 23） |
| `ops` | `app/domains/ops/router.py` | `/ops` | 14 | `GET /api/v1/ops/integration-capabilities`（定义行 77） |
| `templates` | `app/domains/templates/router.py` | `/templates` | 15 | `GET /api/v1/templates`（定义行 87） |
| `term-rule-categories` | `app/domains/term_rules/categories_router.py` | `/term-rule-categories` | 4 | `GET /api/v1/term-rule-categories`（定义行 70） |
| `term-rule-sets` | `app/domains/term_rules/sets_router.py` | `/term-rule-sets` | 16 | `GET /api/v1/term-rule-sets`（定义行 157） |
| `term-rules` | `app/domains/term_rules/router.py` | `/term-rules` | 10 | `GET /api/v1/term-rules`（定义行 79） |
| `translation-profiles` | `app/domains/translation/router.py` | `/translation-profiles` | 11 | `GET /api/v1/translation-profiles`（定义行 62） |
| `translation-term-proposals` | `app/domains/translation/proposals_router.py` | `/translation-term-proposals` | 8 | `POST /api/v1/translation-term-proposals`（定义行 148） |
| `translation-term-sets` | `app/domains/translation/sets_router.py` | `/translation-term-sets` | 12 | `GET /api/v1/translation-term-sets`（定义行 104） |
| `users` | `app/domains/users/router.py` | `/users` | 4 | `GET /api/v1/users`（定义行 30） |

## 仍维护的命令入口

只用标准库 AST 读取 argparse 声明/入口，并对正式启动、回填薄入口、预检与签字分支读取必要正文；没有调用 `--help`、main 或任何脚本命令。下表仅表示声明存在，未核验依赖环境、样本可用性、输出结果或所有业务分支。

| 实际脚本 | 入口/参数声明 |
|---|---|
| `scripts/dev/run_api.py` | __main__ 直接调用 uvicorn.run("app.main:app", host="127.0.0.1", port=8000) |
| `scripts/dev/run_document_worker.py` | main:70 |
| `scripts/dev/formal_mineru_conversion.py` | run_conversion:135 |
| `scripts/dev/run_local_mineru_debug_config.py` | parse_args:55, main:138；；--config |
| `scripts/dev/run_local_mineru_conversion.py` | parse_args:28, main:151；；input_path, --output, --template, --layout-config, --subscript-config, --no-template, --use-mineru-header-footer, --document-language, --translation-mode, --translation-request-output, --translation-response, --translation-trace-output, --translation-model, --translation-api-key, --translation-base-url, --translation-max-pages, --translation-max-chars, --log-level |
| `scripts/dev/run_local_mineru_quality_matrix.py` | parse_args:214, main:769；；--sample-set, --sample-id, --mode, --output-dir, --no-timestamp, --template-path, --layout-config-path, --subscript-config-path, --translation-response-dir, --translation-model, --translation-api-key, --translation-base-url, --translation-max-pages, --translation-max-chars, --dry-run, --allow-blockers, --json |
| `scripts/dev/manage_component_pdf_samples.py` | parse_args:59, main:343；子命令 validate, add-mineru-sample；--manifest, --json, --sample-id, --brand, --category, --product, --title, --source-pdf, --mineru-package, --tag, --acceptance-focus, --document-language, --translation-mode, --apply |
| `scripts/dev/run_component_pdf_regression.py` | parse_args:60, main:265；；--manifest, --output-dir, --sample-id, --no-timestamp, --json |
| `scripts/dev/audit_conversion_sandbox.py` | parse_args:75, main:333；子命令 drift, samples, thin；--sandbox-root, --official-root, --path, --json, --allow-drift |
| `scripts/ops/run_golden_sample_regression.py` | main:86；；--preflight, --preflight-output, --apply-manual-signoff, --manual-signoff |
| `scripts/ops/run_p1_translation_regression.py` | main:103；；--preflight, --preflight-output, --apply-manual-signoff, --manual-signoff |
| `scripts/ops/run_p2_online_gate.py` | main:56；；--base-url, --public-url, --output-dir, --skip-release-check, --skip-p0-preflight, --skip-p1-preflight, --no-release-check-unittests, --sync-acceptance, --acceptance-run-id, --acceptance-environment, --acceptance-review-decision, --acceptance-review-note |
| `scripts/ops/export_openapi.py` | main:181；；--output, --check, --no-diff, --format |
| `scripts/ops/check_release.py` | main:595；；--runtime-url, --golden-sample-preflight, --golden-sample-preflight-output |
| `scripts/ops/migrate_document_job_state.py` | main:298；；--dry-run, --apply, --verify, --phase, --batch-size, --after-job-id, --backend, --data-dir, --database-path |
| `scripts/ops/migrate_document_job_list_keys.py` | __main__ 调用从 migrate_document_job_list_query 导入的 main；参数与后者共用 |
| `scripts/ops/migrate_document_job_list_query.py` | main:245；；--dry-run, --apply, --verify, --batch-size, --after-job-id, --after-file-id, --backend, --database-path |
| `scripts/ops/check_repository_hygiene.py` | main:148；；--staged, --tracked, --files |

## 精确观察及处理边界

| 文档/位置 | 本次静态观察 | B3 处理 |
|---|---|---|
| docs/api/manifest.yaml：guides | backend-pdf-online-completion-change-summary 仍 current、两个 term-assets 主题仍 approved，但被索引正文实际为 deferred 占位 | 仅顶层范围字段说明索引不覆盖文档用途；原 guides/entries/OpenAPI 全保留 |
| docs/api/manifest.yaml：mineru-callbacks.source_files | `app/domains/jobs/mineru_callback.py` 当前不存在；维护中的 callbacks.md 已列正式入口 | 精确登记，不改原 source_files 或业务对象 |
| docs/dev/backend-local-minimal-env-and-commands.md：启动节 | 根 `run_api.py`、`run_worker.py` 不存在；`scripts/dev/run_api.py` 与 `scripts/dev/run_document_worker.py` 存在；旧 StageWorker 的 `scripts/dev/run_stage_worker.py` 不存在 | 原命令原样保留；导语明确旧根启动/StageWorker 不适用，链接现行 runbook |
| docs/dev/backend-local-minimal-env-and-commands.md 与 runtime-observability-and-health.md：callback token 段 | guard 的 verify_mineru_callback_identity 不校验额外 token；verify_mineru_callback_checksum_for_job 校验 uid/seed/content；callbacks.md 已说明 checksum | 导语明确 token 提示是旧口径，实际回调按 callbacks.md；不修改命令语义或扩成安全审计 |
| docs/api/document-jobs.md：当前边界 | 原末尾 Golden blocked 是旧验收声明；本批未读取新环境或重跑样本 | 导语隔离该声明，链接 P0 程序与历史报告，既不重判 blocked 也不改成 passed |
| docs/testing/pdf-to-word-p0-integration-guide.md：上传 | 原文保留外部 S3 presigned URL 条件；当前 Files 文档及 router 的 upload_file_content 回落路径描述代理上传 | 导语链接 Files 当前合同，不把该条件视为当前已启用路径；不重写示例 |
| tests/fixtures/component_pdf_samples/README.md：修复路径 | 原文只指 app/conversion；现行组件治理页明确 DocumentIR/renderer 与共享规则 | 导语链接治理页并限定旧职责提示，保留原步骤与命令 |
| docs/runbooks/internal-portal.md：部署节 | 旧 compose up --build 示例未体现 B02 版本化镜像/离线输入流程；维护部署页已限定新流程 | 导语链接 P0 Docker 的依赖锁/构建输入范围，原示例不作为新镜像构建认证 |
| 两份质量报告与 FE/BE 计划第 9 节 | 分别记录 20260602T071017Z、20260603T070724Z，以及 2026-06-10 原执行声明 | 保留原结果/样本/job/路径/命令，只增加时间范围和当前程序入口；未核看/再生原二进制或重新验收 |
| API Manifest 消费方 | 在 app/scripts/tests 按 manifest 路径与 api-manifest 检索未找到读取此 YAML 的程序；无从认证仓库外消费者 | 保留原所有业务键与值，不以搜索无结果证明任意消费者兼容 |
| 样本 Manifest | Golden 四个 canonical ID 与 P1 三个 formal ID 及 target_sample_count=3 仍有版本化声明 | 只读对照身份与样本用途，不改样本 YAML，不把 available 解释为新运行通过 |

## 本批读取的静态输入身份

文件哈希是工作区内容身份，整文件哈希不表示已审计全部正文。历史报告原始输入/输出制品未在本批重开或再生；B1/B2 已核验且字节不变的事实仅按原范围复用。

| 相对路径 | SHA-256 | 与 HEAD 关系 |
|---|---|---|
| `app/api/v1/router.py` | `623d4b3eaea1195a1990147ee7c047ce6a62af787f8dff5e9663e310138a69c1` | 相同 |
| `app/domains/acceptance/router.py` | `f0944770488d8f124598bd23a7fa9f76df296d64e669c0a044a840adda437ca7` | 相同 |
| `app/api/v1/routers/auth.py` | `cc8ea15506487f4c4761bcbff181ed534c6901a58bc6525bfbe2d674e64b4cfc` | 相同 |
| `app/domains/config_workbench/router.py` | `9f0454edce1204298a9b53527a5c643c0b52173600c8e8760e520a845e494aa7` | 相同 |
| `app/domains/document_jobs/router.py` | `b018bbfb6d71c7ee89ef0fceac7e8bf9dce780a6eb52b9b763727c4e5c02b6c6` | 已有未提交差异 |
| `app/domains/files/router.py` | `4e8b57b3699ed8d1d75f11cab880b186e94bdc33b44fc430cdd09d3e49a8c731` | 相同 |
| `app/api/v1/routers/health.py` | `d90d96db24f322af032042f77994f10806ccfec387d5cd07f4d7c1c8fae5038c` | 相同 |
| `app/domains/jobs/mineru_callbacks_router.py` | `ffa3f0c90ea732316c980f437026b3a58f01c4ff970dc16dec81d262c7d5585c` | 相同 |
| `app/domains/mineru/router.py` | `5b4d8132b68a14b81fe3939d205bbcef64cf25f4303af59148c5067f475eaecb` | 相同 |
| `app/domains/ops/router.py` | `4c5a87e8872eb2f155f3f2c71268e050346e95493ee505a26035a40d48d799f2` | 相同 |
| `app/domains/templates/router.py` | `a545f753ee0cea39dd68cef8b876d86fe428676084fca9db6234d2e0f8f0ca9f` | 相同 |
| `app/domains/term_rules/categories_router.py` | `61a7aee60ba11feeefe30c0b6eb7994ebef8143c5e68bad1b48a8534ea592b2f` | 相同 |
| `app/domains/term_rules/sets_router.py` | `7780bd3a2b04a7542c34a18c9f9218f56c7fae53c68a07d97c3065aee830e9c7` | 相同 |
| `app/domains/term_rules/router.py` | `098a66486e1bffe513973d364dcfdc32860de43a4e5634e69ac82248169493ee` | 相同 |
| `app/domains/translation/router.py` | `dcd88b416d4bd91a433eb24ed0fc8f72245b0d7f024454321d7d473522742cfd` | 相同 |
| `app/domains/translation/proposals_router.py` | `99058ea7533ad933044d68f490cde8b51eff0490cd0a225350d2cf418158c451` | 相同 |
| `app/domains/translation/sets_router.py` | `0ec7093e5c5bf31371dc9f61c3951a680942daaf021a14aba5577e3fa6f626e8` | 相同 |
| `app/domains/users/router.py` | `e431ffece9398a03aa2a6cd2a75f7394f58e4a3a6dea7a9178511506e0d65194` | 相同 |
| `scripts/dev/run_api.py` | `b4e6a960886cd44c35ea264bf350a08a88e4931d26d33b90623f69bc7703f0bd` | 相同 |
| `scripts/dev/run_document_worker.py` | `3879dd504bef52eb3c6a9eac09f196317b24655f6a487873a2a51ba4f8780b2b` | 相同 |
| `scripts/dev/formal_mineru_conversion.py` | `c1593cbce9979712cfd3ff3ed559d872133c70c3eb1629b0fb28ec3b6a77ff20` | 相同 |
| `scripts/dev/run_local_mineru_debug_config.py` | `1a75fa334fa3065d44826a3e8785ad4bae9a613c740e62495bb8fd93b694a4a6` | 相同 |
| `scripts/dev/run_local_mineru_conversion.py` | `643de74627afacefac1a78fdb1626fd864c665b7616d662fc468737465b4888a` | 相同 |
| `scripts/dev/run_local_mineru_quality_matrix.py` | `b97d3f1e96cfec3acda16373cd63733471ba603d80aa1a3ab573000224936f3d` | 相同 |
| `scripts/dev/manage_component_pdf_samples.py` | `4914a14e5653a436db11ac989d364835340a8ddb2319ab31ccdfe87e02da0625` | 相同 |
| `scripts/dev/run_component_pdf_regression.py` | `8db40cb895bd4da5c724eea496e7a670852964c267132d9292c066cf2baf9c19` | 相同 |
| `scripts/dev/audit_conversion_sandbox.py` | `c92e792edb60fd85f1a2aa750729f861b431397dd9270feda7381f5a839ad7d6` | 已有未提交差异 |
| `scripts/ops/run_golden_sample_regression.py` | `e7f40687fc80d04153883cdbadc24b8ecd0de3437bae228a412c335091d41621` | 相同 |
| `scripts/ops/run_p1_translation_regression.py` | `b90f1bd0eaa4f8a1b1892b24d4133136b01a42cbaae8e6ea8441ef3c0d39b7c8` | 相同 |
| `scripts/ops/run_p2_online_gate.py` | `eb3f6d030f6d10c6ebd52c5dc1397cfe0b31aa0dc0943a74738a28dd2f845ba8` | 相同 |
| `scripts/ops/export_openapi.py` | `534c7d7b32e3356e6155e90d05728fd2407e78f7ceb08078cc96ac54eedd96fd` | 相同 |
| `scripts/ops/check_release.py` | `31c96e03808c7542a526430188e546de0e7836e90329fb4e1dbb84c2419273f0` | 相同 |
| `scripts/ops/migrate_document_job_state.py` | `5183d01556f221e8be203764a004574981c546abbca7ab63c47fd20e457d35ee` | 相同 |
| `scripts/ops/migrate_document_job_list_keys.py` | `917b29d0b251583d5542af7952b42e7a8e18dc80698367636e878ca639ee9412` | 相同 |
| `scripts/ops/migrate_document_job_list_query.py` | `f3cbea460cff8237971a1418155a9822b5f88d843c1478c1c1858bd050341409` | 相同 |
| `scripts/ops/check_repository_hygiene.py` | `a1f516a01b68dffca06f76f6ad539dd5b81be5c23459e57efdd2ed2a742bf744` | 未跟踪 |
| `app/api/mineru_callback_guards.py` | `220fc23d68fddaee987b6f5f31646308b52a5cf9ee2cc547d1654bdbdfd10a20` | 相同 |
| `app/domains/files/service.py` | `542ed3099e1c91e5211c2cf13f3fa48a380556d763b265a5d76aba702f242c8a` | 相同 |
| `frontend/src/router/index.ts` | `d30e0424f4f0271a6e8cee1ee3aea7203f99dbf137513082ba67560c160e7109` | 相同 |
| `tests/fixtures/golden_samples/manifest.yaml` | `5b1ee01dc8b4da8a1af4791df8e6b2d070f7e01e22597386a1a800fd629eacd7` | 相同 |
| `tests/fixtures/p1_translation_samples/manifest.yaml` | `308698a9f0656d76fa951f6c3de59e5fea428277bc317441853b6132b0feea4d` | 相同 |

尚未确认任何文档的人类责任 owner。本记录与后续元数据不改变 Manifest 执行状态、原 AC/依赖或既有验收结论；不提供执行生产/迁移/发布/测试命令的授权。
