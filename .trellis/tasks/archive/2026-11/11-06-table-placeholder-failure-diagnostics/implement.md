# 实施与验证计划

## 前置条件

- [x] 创建任务已获用户同意。
- [x] PRD 已收敛，设计、事实研究与 implement/check 上下文清单已形成。
- [x] 用户在最终规划摘要之后明确批准实施（2026-11-06）。
- [x] 批准后激活任务并核对工作树；基线只有本任务规划目录未跟踪。

已获准修改本任务产品代码并进行定向验证；不启动生产服务或生产任务。

## 实施顺序与所有权

1. 由一个 Trellis implement 子代理完成耦合链路；独占下列产品文件和定向测试。必须告知存在其他工作者，不得回退不属于本任务的修改。
   - `app/services/failure_context.py`：现有上下文附加 helper 的共同 owner。
   - `app/services/document_ir/table_placeholder.py`：片段/文档范围上下文。
   - `app/services/renderer/word_renderer.py`、`app/domains/document_jobs/_failure_policy.py`：共同 helper 导入及必要接线；不修改既有分类和重试规则。
   - `app/services/renderer/evidence.py`：新增唯一受控操作类型。
   - `app/domains/document_jobs/failure_diagnostic.py`、`schemas.py`：报告无有效诊断时使用操作上下文；新增 source 枚举。
   - `frontend/src/api/types.ts`、`frontend/src/utils/failureDiagnostic.ts`：类型和技术定位格式化。
   - 相应测试及 `docs/api/openapi.json`。converter 只有证据确实要求时才做最小接线，不扩展转换算法。
2. 测试覆盖：新增 `tests/test_table_placeholder_failure_context.py`，复用现有合成 ZIP、测试 runtime 和 source span 夹具；在失败投影、Worker 安全证据、前端摘要与组件测试中增加本次合同用例。不得复制生产文件或下载客户内容作夹具。
3. 主会话更新 `.trellis/spec/backend/error-handling.md`，记录新来源、优先级和源片段定位；仅同步 Word 生成规则中直接受影响的诊断说明，不重写无关规范。
4. Trellis check 子代理复核候选差异与定向验证结果，重点检查原异常类型、私密内容过滤、跨页来源、旧代隔离、公开枚举兼容和降级影响。无具体风险时不重复扩大测试。
5. 检查最终 diff/工作树，记录验证与未验证边界；提交、推送、部署等待后续明确指令。

## 验证矩阵

| 验证 | 方法 | 覆盖 |
|---|---|---|
| 真实失败链路 | 合成 MinerU 表格输入在真实 prepare_placeholders 几何检查失败，经 eager Worker 写事件，再读取详情/异常 API | AC1、AC4、AC5 |
| 位置准确 | 页 0、跨页后续片段、未知页、全局预算/源身份错误 | AC2、AC3 |
| 安全与兼容 | 受控四类码、私密字段/非法值过滤、事件序列化往返、旧事件与旧代、既有渲染诊断 | AC3–AC5 |
| 成功/降级不变 | 正常表格占位、转换失败关闭、现有直接受影响降级用例 | AC6 |
| UI/API 合同 | formatter/真实组件 SSR、vue-tsc、OpenAPI 当前导出比对 | AC1、AC5、AC6 |

## 预期定向命令

实施后选择能够覆盖实际修改的测试类/方法，以下为已定位入口；不机械扩大到全仓或发布聚合门禁。

```bash
.venv/bin/python -m unittest tests.test_table_placeholder_failure_context tests.test_document_job_failure_diagnostic tests.test_render_failure_context tests.test_worker_failure_policy tests.test_worker_failure_message
.venv/bin/python -m unittest tests.test_image_normalization_pipeline tests.test_page_degradation tests.test_render_page_degradation
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python scripts/ops/export_openapi.py --check --no-diff
```

第二条可缩小为直接受影响的测试类/方法，并记录理由。若出现历史夹具不匹配或既有失败，先归因，禁止为全绿扩大本任务范围。

前端在 frontend 目录运行：

```bash
npx vitest run src/utils/failureDiagnostic.test.ts src/features/job-detail/JobOverviewPanel.test.ts
npx vue-tsc --noEmit
```

概览组件的既有 SSR 测试位于 `src/features/job-detail/JobOverviewPanel.test.ts`，补本来源用例并一起执行；诊断页签与异常抽屉核对对共享 formatter 的接线，由 formatter 的技术详情用例覆盖本次来源变化；不重复搭建浏览器 smoke，不运行全仓测试或 check_release 聚合脚本。若修改最终影响打包行为，再运行 npm run build。

## 交付与后续线上验收

本轮交付代码、必要文档和可复现定向结果，不声称已上线。后续经部署授权时核对 API/Worker/前端版本，并用经授权的新任务或重试确认新事件包含正确原因和源页；旧任务缺证据仍允许 null。重试会改变生产任务，不能作为本次只读研究或本地验证的隐含步骤。

## 回退点

本任务修改可作为一个兼容的诊断变更回退，无数据库迁移。共享 helper 移动及其导入必须一起回退；source 枚举、API 投影和前端类型必须作为合同整体核对。不会在实施前执行 git 回退或修改历史提交。

## 实施完成记录（2026-11-06）

- [x] 完成共同上下文 owner、真实片段定位、文档级错误、同事件诊断回退及 API/前端同步。
- [x] 更新后端错误合同及 Word 规则的诊断说明，新增/实质改动注释与 docstring 已核对为中文。
- [x] 完成 AC1–AC6 的本地定向验证；命令、结果、首轮失败归因及边界见 `validation-implementation.md`。
- [x] 完成独立 Trellis check；未发现产品阻塞缺陷，仅更正 Spec 的测试证据归属，见 `validation-review.md`。
- [x] 核对最终候选差异与工作树，未纳入无关修改。

诊断/安全覆盖 34 个不同测试，成功与直接降级回归 23 项，前端 27 项；vue-tsc 和 OpenAPI 当前快照比对通过。复核仅改文档，复用未受影响的成功结果，没有全仓回归、打包或线上验收。

本轮实施与复核已交付，代码尚未提交；任务保留 `in_progress` 等待后续提交与收尾，不执行可能产生记账提交的归档/日志命令。历史缺上下文事件不回填，生产环境没有变更。

## 后续发布授权与验收

用户随后明确授权提交、推送、部署及线上表格占位失败验证。上述未提交/未部署描述保留为实施阶段历史状态。发布采用现有分层 Compose override，仅更新 API/Worker；前端使用版本目录和 current 原子切换，保留旧镜像及静态目录供回滚。通过功能分支和 PR 遵守 main 保护规则。复用已有定向检查，发布新增构建制品、健康及实际失败事件/页面核对；不运行全仓或发布聚合测试，不回填历史事件。
