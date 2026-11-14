# 生产动态模板目录实施计划

## 顺序

1. 核对 seed 历史修复和 B08 在选定基线的接入状态。核对并行任务 `11-13-template-default-switch-integrity` 的实际差异。该任务如先交付默认版本切换的校验或事务能力，目录切换直接接入该能力，并补齐全局默认模板与目录状态联动的验收。
2. 接入 MySQL 目录、全局默认和事务方法，实现首版登记、后续版本及发布/默认一致性。明确候选文件归属、故障补偿和冲突映射。
3. 将 API 读写、新建与克隆的模板准入切到数据库，整理 seed 初始化顺序。快照渲染绕开 manifest，检查同任务重试、无快照任务和本地兼容入口。
4. 实现旧目录预检、导入、复核，更新模板 Spec、API 和部署迁移说明。对事务、准入和迁移做独立只读复核。
5. 运行定向回归、隔离 MySQL 与 Compose 验收，最后核对 diff 和证据。

## 验证矩阵

| 合同 | 最小证据 |
| --- | --- |
| AC1、AC4 | `tests.test_template_seed_history` 的空库、旧默认、关闭 seed、路径和历史快照用例。新增迁移用例覆盖重复导入、异常默认、孤立草稿、缺失资产、只读预检与冲突。 |
| AC2、AC3 | `tests.test_fastapi_jobs_backend` 的模板 CRUD、发布禁用和 admin 草稿用例，覆盖停用/删除后拒绝新建及克隆。将 `tests.test_job_render_resources` 的旧清单停用断言改为已绑定任务可生成，并覆盖目录删除、保留快照重试、数据库版本禁用、草稿授权、无快照历史任务和哈希失效。 |
| AC5 | 注入明确回滚与提交结果未知。真实 MySQL 验证并发创建、上传和默认/停用竞态，核对已登记文件与哈希。 |
| AC6 | 隔离 Linux amd64 工程基于生产 Dockerfile 与 Compose，API/Worker 使用相同镜像身份与非 root 用户，运行独立 Worker、真实 MySQL 和 Redis。复用 PDF/MinerU 结果夹具，仅在隔离测试接线替换外部 MinerU I/O，队列、资源物化和 DOCX 渲染走正式入口。 |

## Compose 步骤

1. 使用独立项目名、端口、合成凭据和临时卷。确认服务就绪，记录实际镜像 ID、UID、卷和 seed 哈希。
2. Worker 已运行时，通过正式 HTTP 创建自定义模板和显式绑定该 draft 的验证任务，等待 Celery 生成 DOCX。通过现有接口发布并设为全局默认。以普通用户通过默认选择创建 direct 任务，验证实际绑定的 published 版本与 DOCX 实物。
3. 上传新版本，确认已有任务和默认版本未漂移。分别重启 API 与 Worker，每次重新列表、提交新任务并下载产物。记录任务 ID、版本及至少一项可辨识的 DOCX 内容或样式。
4. 先将全局默认切回内置模板。用夹具在 Worker 渲染前暂停绑定非默认自定义模板的任务。分别验证停用与删除后旧任务仍可生成、通过模板 ID 或显式版本新建与继承源快照的克隆均被拒绝。用非默认版本验证显式版本禁用后已绑定的任务以 `resource_snapshot_invalid_status` 失败。核对目录、历史记录、实物与 seed 哈希，清理该工程的临时资源。

专项入口为 `tests/integration/template_catalog_compose.py`，按 `tests/integration/README.md` 准备隔离 context 与锁定 wheelhouse。真实 MySQL adapter 用例为 `tests.test_mysql_template_catalog`，在明确指定隔离回环端口后执行。

隔离 Compose 专项覆盖双容器、真实存储、队列和渲染链。真实 MinerU、正式环境数据迁移及上线各自保留验收状态。
