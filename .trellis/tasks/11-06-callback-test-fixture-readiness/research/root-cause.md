# 夹具失败根因

## 当前源码与运行证据

- `tests/test_fastapi_jobs_backend.py:330` 的 build_test_runtime 默认 app_env=dev、jobs_repository_backend=file、public_deployment_mode=internal。
- 四个方法位于同文件 9282、9370、9429、9537：均显式切为 single_tenant_public 并使用 eager。创建成功断言位于后面的 9338、9417、9474、9574，晚于首次 job_id 访问。
- `app/core/config.py:185` production_like 将公开模式视为生产类环境，与 app_env=dev 无关。
- `app/services/health_service.py:344` 使用 production_like；361–362 拒绝生产 eager；369–370 拒绝非 MySQL 元数据。
- `app/domains/document_jobs/router.py:141` 先执行创建就绪检查；175–187 将 blockers 转为 HTTP 503 / document_jobs_not_ready。
- 只观察 TestClient.post 的原始返回值运行四个未修改用例，各返回同样两个 blocker，均随后 KeyError: job_id；报告按 test_selectors 顺序记录 creation_responses。结果为 4 tests / 4 errors，而非四条回调行为已验证。

## 安全与原有职责

`app/domains/jobs/mineru_callbacks_router.py:29` 的入口依次执行 payload、URL、任务定位、checksum 校验后入队；`app/api/mineru_callback_guards.py:81` 的 checksum 路径没有 public_deployment_mode 分支。`docs/api/mineru-callbacks.md` 的部署模式表明确两种模式都使用 checksum。

两个成功处理用例使用 build_test_runtime 已配置的 DocumentIRWordRenderer（tests 文件 554 行），未找到这四个方法内替换 renderer 的逻辑。取消和 checksum 用例断言禁止继续处理。本计划不改变其内容或替换渲染合同。

专属生产 readiness 用例 `test_health_ready_blocks_p0_document_jobs_when_production_uses_non_mysql_metadata_store`（1833）及 `test_health_ready_blocks_p0_document_jobs_when_production_uses_eager_worker`（1858）保留；本轮只读取，不运行或修改。

## 基线归属与范围

B03 已留有原始 HEAD 79f20cef9ca0bb1a59af635e2408e130c4935e2d 的四例复现日志：`.trellis/tasks/11-06-mineru-download-boundary/validation/baseline-targeted-tests.log`。本轮复用该证据，不新建 worktree、不重复原始 HEAD 测试。

当前观察没有触及下载边界，故不能归因为 B03 下载实现。直接根因是测试部署配置与现行就绪合同冲突，晚置断言掩盖原始 HTTP 失败。无需生产逻辑变更；候选修复效果留待确认后的定向验收。
