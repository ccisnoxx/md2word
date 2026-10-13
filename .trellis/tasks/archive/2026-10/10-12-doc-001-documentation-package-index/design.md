# DOC-001 设计

## 当前实现与证据

- 调查 HEAD：c9b1e6a9642d23d932bcd98c107e8bc66fb3c361。文档包自身标注的 e51e6ccd 基线保留，不冒充当前代码审计结论。
- README 只有 P0/P1/P2 与运行、联调入口；docs/README 和 DOCUMENTATION-MANIFEST 已存在但未跟踪，缺少 manifest、prompt、bootstrap 导航。
- app/domains/translation/modes.py 已定义 direct 和四种跨语言模式，direct 没有 prompt/profile；models.py 已有单 result_file_id、translation QA 与批次 generation。未据此宣称统一质量/发布目标已完成。
- docs/api/document-jobs.md 描述后端 available_actions、权限、下载及 QA 事实；OpenAPI 快照已存在。MySQL/SQLite 使用 schema bootstrap；本任务不增加迁移。
- tests/test_openapi_export.py 与 scripts/ops/check_release.py 已存在；本次没有 API 或业务变更，不运行全套发布门禁。BAS-001 负责运行能力与测试基线核验。
- 旧模板部署、题注修复任务为 in_progress，其 PRD 范围与本次文档索引不冲突，保留其状态；没有其他 manifest in_progress 项。

## 目标边界与文档流

根 README → docs/README → 产品/架构/合同/设计/工程/实施/ADR。
DOCUMENTATION-MANIFEST 定义文档职责与权威；实施计划定义阶段，backlog 定义工作单元和依赖，manifest 记录执行状态与实际 task path；Trellis 保存任务方案及证据。
保留既有事实文档入口。目标与现状不同属于 gap，不以新文档覆盖当前 API 或执行 spec。
bootstrap 仅是父任务模板，task-map 仅为建议，不能取代 backlog 或制造平行任务清单。

## 数据、API、DB、前端与兼容

无业务模型、OpenAPI、DB、迁移、后端状态机、权限或前端路由/query key/URL/generated types 变更。
无事务、锁、幂等、并发、generation、错误映射改动；不重生成或覆盖历史 DOCX、发布件与审计。
不新增 quality flag、feature flag 或配置 snapshot；无需 backfill、兼容窗口或业务回滚。
文档新增导航保持旧 README 原文和旧相对路径；原有五类事实文档不改。

## 安全与可观测性

本地只读检查不请求网络，不运行代码块，不调用 MinerU、AI 或真实服务。检查输出只有路径、计数与状态，不复制客户文件、正文日志或凭据。
任务保留验证报告及可复现只读链接检查脚本；以文件哈希和工作树差异证明保全边界，不用未运行测试证明业务正常。

## 回滚

仅撤销本轮增加的 README 段落和文档索引增量；不得删除会话前已有未跟踪文档包。
manifest 可恢复到本轮前 blocked 记录；任务记录保留恢复说明，不更改他人任务。不自动运行 git restore/clean 或删除审计。
