# 合并设计

从当时的 origin/main 在隔离工作区创建合并提交，原始分支作为第二父提交。按顺序使用原分支名称推送，由 GitHub merge commit 合入 main，保留原始提交可达性。若主分支在合并前改变，更新候选并核对受影响区域。

## 冷启动

API 装配、持久化、认证、Worker、Compose 和语言映射均以 main 为准。保留 app.main:create_app --factory、service_healthy、单进程 Runtime 复用和按需配置读取。补入隔离 Compose 验收脚本、说明和历史证据，确认失败注入与 factory 入口兼容。Trellis 重复的 MinerU 档案沿用主分支版本，独有冷启动记录和日志纳入合并。

## 参数表

- app/services/tables 负责源 Grid 数值列发现和有效风险。保留主分支的隐式表头、续片、单位和值口径。将候选与认证后的有效集合衔接到现有报告，维持旧报告读入与未认证项阻断。
- DocumentIR、renderer 和 execution 负责源 PDF/ZIP 身份、逐页取证、同包核定和 Word 实物认证。合入分支的证据链，同时核对主分支内容证据和输出契约。降级页和过期执行沿既有代次合同。
- document_jobs 继续使用任务与产物的当前权限、报告摘要及代次。保留主分支现有确认、发布重验与只读投影，合入同包新代权限、锁内重核和试点名单。开关默认关闭，名单为空，读者兼容旧证据。
- 以实际 FastAPI 模型重新导出 OpenAPI。文档只更新被整合影响的合同。

## 分支清理

远端主分支包含原始 HEAD 和候选 HEAD 后，核对 GitHub 自动删除结果。需要手动清理时使用已核对的 SHA。保留 Claude 的现有工作区并使其在原提交上分离 HEAD。
