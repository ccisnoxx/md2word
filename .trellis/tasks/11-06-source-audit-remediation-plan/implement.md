# 规划交付与后续执行入口

## 授权与状态

本任务是规划交付。用户已授权“核实审查并制定分阶段计划”，明确暂不改业务代码、不引入 CI/全量测试。总计划保持 `status=planning`，不运行 `task.py start`。后续获批的 B03 已完成本地定向验收，回调夹具专项证据已回填；其余 B 批次仍是待独立授权候选。本轮用户只授权证据和状态整理，不再运行测试。

## 本轮检查清单

- [x] 核对 main commit、初始工作区及审查基线。
- [x] 建立 A01–A29 证据矩阵，标注源码事实、推论和运行未知。
- [x] 检查既有任务/Spec/当前调用，识别 TR-404 等重叠和状态滞后。
- [x] 制定 B01–B11 的优先级、范围、依赖、可观察验收、最小验证及回退边界。
- [x] 收敛 PRD，使本轮验收与未来实施验收分开。
- [x] 编写真实 implement/check context，不放示例条目。
- [x] 运行文档路径/行号、ID 覆盖、JSON/JSONL、空白与范围检查，记录结果。
- [x] 形成最终规划摘要供用户审阅，停留在 planning，不申请自动沿路线图实施。

## 文档验证命令（本轮允许）

```bash
python3 .trellis/scripts/task.py validate .trellis/tasks/11-06-source-audit-remediation-plan
git diff --check -- .trellis/tasks/11-06-source-audit-remediation-plan
git status --short --untracked-files=all
git diff --name-only
git diff --cached --name-only
```

任务新文件尚未跟踪时，`git diff --check` 不覆盖其内容，因此另以只读 Python 检查：

1. task.json/JSONL 可解析，context 引用实际存在；status=planning。
2. 三件套及研究文件的 `文件:行号` 均存在且行号有效。
3. A01–A29、B01–B11 定义完整且交叉引用有效。
4. 新文件无尾空白和默认 TBD 占位；检查文件清单仅属于本任务目录。
5. 业务/配置/依赖/测试/Spec/其他任务相对 HEAD 未改变，index 未暂存。

Word 规则文件超过单文件上下文注入上限；manifest 通过 backend/index.md 保留权威入口，后续只读相关 PIPE-001/002、INPUT-002 等段落，不以被截断的整文件注入代替合同阅读。

以上是文档校验，不是运行时安全、翻译或渲染验证。任务 validate 主要校验 context，不认证 PRD 质量或业务验收；三件套仍须人工可审阅。

## 后续获批批次的最小验证选择

下表保留各批次最小验证入口。B03 的批准子计划已经执行并有成功证据，见 progress.md；其余条目只定位未来候选，不表示执行或授权。本轮不因收尾重新测试。

| 批次 | 已有入口/候选检查 | 扩展条件 |
|---|---|---|
| B01 | 文本/链接/精确 diff | 仅改文案时无应用测试。 |
| B02 | `tests.test_document_ir_word_renderer_layout`、`tests.test_render_table_from_html_characterization` 的所影响类/方法；隔离安装/依赖一致性 | 选定平台/锁方案后固定命令，不能把当前 venv 当作验证完成。 |
| B03 | `tests/test_fastapi_jobs_backend.py` 的 callback checksum 与队列行为用例；新增最小轮询/URL/跳转传输案例 | 用新定向测试文件保护实际统一边界；不跑整个大型 backend 模块。 |
| B04 | `tests.test_document_job_execution_stages.DocumentJobExecutionStageTests.test_direct_quality_checks_precede_main_word_registration`；`test_provider_return_after_cancel_or_generation_change_cannot_finalize`；失败策略对照 | 仅触及相应状态路径才加入批次/receipt 用例；不修无关旧夹具。 |
| B05 | `tests.test_openapi_export.OpenAPIExportTests.test_export_openapi_writes_snapshot_and_check_passes`；选定入口 characterization | OpenAPI 单方法不等于运行 release 聚合脚本；不自动启动 Worker。 |
| B06 | `tests.test_document_ir_translation`、`tests.test_translation_integrity`、`tests.test_formula_translation_boundary` 的受影响案例 | 真实 Provider 语义对照另行授权；fake 不证明质量改善。 |
| B07 | `frontend/src/stores/auth.test.ts` 与实际改动页面/导航用例；必要的 `npm run build` | 只构建/测试所改合同需要的范围；无全量 Vitest/Playwright。 |
| B08 | schema maintenance 对应定向用例，隔离 MySQL 目标升级路径 | 新持久化合同才触发；fake 不代表真实 DDL。 |
| B09 | admin 配置/API 掩码/所改会话合同的定向正反例 | 不读取实际秘密；具体工具选型后才确定版本验证。 |
| B10 | 文件保护集合对照和已授权数据规模的单查询基准 | 不扩大为全站性能工程或全量压测。 |
| B11 | 分发与许可证文件清单 | 无业务测试。 |

最终命令须在被选批次的 implement.md 中落到具体模块/类/方法。B03 结果以专项验收记录为准；其余候选入口不代表已通过。

## 停止条件与恢复

- 若 HEAD 改变或出现并行修改，只刷新受影响证据，不覆盖他人内容。
- 若实现所需产品/兼容取舍未明确，停在该批次规划，不把合理推断当作用户授权。
- 不新增/启用 CI，不调用 unittest discover、完整前端 test:unit/test:smoke、check_release 或在线门禁聚合脚本。
- 不提交、不推送、不归档、不执行 add_session；避免顺带产生 bookkeeping commit。
- 规划文件可局部修订；未来回退按 design 中每批次处理，不使用破坏性 Git 操作。
