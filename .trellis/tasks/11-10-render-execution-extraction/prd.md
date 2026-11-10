# 渲染段提取

## 目标

`app/domains/document_jobs/execution.py` 在翻译批次提取后仍有 2164 行。`DocumentJobExecutionService` 里的 Word 渲染、质量检查、上传收尾和表格占位符读取共 17 个方法、580 行，只经 `execute_job` 和 IR 转换的一个 lambda 进入，适合沿用翻译批次提取（PR #39）的做法提取为独立协作者。

本任务只建立宿主与渲染段之间的边界，不改任何行为。度量见 [research/current-state.md](research/current-state.md)。

## 范围

- 新建 `app/domains/document_jobs/render_execution.py`，迁入渲染核心 10 个方法和表格占位符读取组 7 个方法（清单见 research §2）。
- 宿主构造并持有协作者 `self.rendering`。`word_renderer`、`template_read_service`、`word_preview_service`、`job_resource_snapshot_service` 不再由宿主持有。
- 宿主内 2 处调用、相关测试改为经 `rendering` 访问。
- 测试按模块路径打的 4 处补丁改为指向新模块。
- 更新 Spec 中的 owner 表述。

## 非目标

- 不改方法名、签名、方法体逻辑、错误码、事件、阶段流转、持久化格式和 DOCX 产物。
- `_record_event`、`_mark_failed`、`_mark_succeeded`、`_mark_timed_out_if_needed`、`_get_uploaded_file`、`_document_ir_layout_metadata` 留在宿主。
- 不拆分 `_render_and_save_word`（229 行）内部结构，不合并渲染与翻译两个协作者的共用依赖。
- 不缩减宿主构造签名，不把协作者提到 `main.py` 装配。
- 不修复与本次无关的既有测试失败（例如 `_build_image_loader` 旧签名调用）。
- 不处理 MinerU 回调段的提取。

## 约束

- 与翻译批次提取一致：先 Mixin 纯搬移，再改为协作者；每阶段用 AST 等价脚本核对。
- 协作者在调用时经 `self._host` 查找宿主方法，不捕获绑定方法。
- `render_execution.py` 不在运行时导入 `execution.py`。
- 宿主模块不得为兼容旧补丁而保留只被渲染段使用的导入。
- `.trellis/spec/backend/word-generation-rules.md` 当前有另一会话的未提交改动，提交时只纳入本任务的行。

## 验收标准

- [ ] AC-1 阶段一：17 个方法与基线 AST 逐一等价，宿主其余方法逐一等价；测试只改 4 处模块路径补丁。
- [ ] AC-2 阶段二：协作者方法去掉 `_host` 一跳后与基线等价；协作者只访问 6 个宿主方法；宿主只经 `_render_and_save_word`、`_load_placeholder_source` 两个入口访问协作者。
- [ ] AC-3 4 个渲染依赖只由协作者持有（`job_resource_snapshot_service` 同时由翻译协作者持有），宿主无同名属性、无转发方法；宿主构造签名不变。
- [ ] AC-4 外部合同不变：API 响应、事件、错误码、阶段流转、质量摘要、发布 provenance、DOCX 产物与持久化格式。
- [ ] AC-5 定向测试的结果清单（用例、状态、最终异常行）阶段一、阶段二均与基线逐行一致；测试只改访问路径、`patch.object` 目标和模块路径补丁目标。
- [ ] AC-6 全仓检索：经执行服务访问迁出方法和 4 个渲染依赖的旧写法为 0；`app.domains.document_jobs.execution.<名字>` 形式的补丁目标都在宿主模块中真实存在。
- [ ] AC-7 `directory-structure.md`、`word-generation-rules.md` 的 owner 表述更新。

## 评审决策（2026-11-10 用户确认）

1. **占位符读取组归属**：随渲染迁出（7 个方法中 6 个只被渲染使用，IR 只经 lambda 用 1 个入口）。
2. **命名**：模块 `render_execution.py`、类 `WordRenderExecution`、宿主属性 `rendering`。
3. **阶段二**：做。阶段一完成后直接进入阶段二，`implement.md` 评审点 A 视为已确认。
