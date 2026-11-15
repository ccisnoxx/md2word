# 实施与验证计划

## 实施顺序

1. 用户评审通过规划后启动任务。先核对模板写入口、启动 seed、目录导入、任务提交与克隆、历史重试、正式发布证据以及现有快照错误映射。
2. 在模板包校验中实现 YAML 绑定要求和外部 Logo 检查，复用现有语言覆盖逻辑。接入首次创建、上传新版本、替换、样式草稿、发布以及两个默认入口。保留登记资源和默认指针 CAS。
3. 接入创建、克隆及管理员草稿验证的模板准入。针对默认快照构建失败、无快照历史克隆、已有绑定任务术语重绑分别沿对应意图处理。接入历史任务的读模型及新代拒绝原因。
4. 在任务物化与渲染证明中传播准入结果，关闭页眉覆盖时短路外部资产读取。补齐正式发布证据对旧结果的同规则核验。
5. 对齐模板 API、现有模板管理页面、`docs/api/templates.md` 与模板、任务模式相关 Spec。开发或历史兼容路径继续走已有载入合同。
6. 复核模板默认指针事务、恢复边界、发布证据及既有最终件。实现后做独立只读复核，重点检查准入绕行和发布兼容。

## 最小有效验证

| 验收 | 验证入口 | 要验证的行为 |
| --- | --- | --- |
| AC1、AC2、AC4 | `tests.test_template_package_validator`、`tests.test_template_package_contract`、`tests.test_template_seed_history` 中实际受影响的用例 | 各写入口 YAML 必绑、继承、语言覆盖、失败无写入、默认指针保留、原有 draft 验证和 seed 幂等。替换原有允许无 YAML 发布及创建任务的合同断言，并增加历史解析和恢复用例。 |
| AC2、AC3 | `tests.test_document_job_template_admission`、`tests.test_document_job_modes` 中实际受影响的用例 | 默认、显式与各 clone 策略，已绑定重试不重选，历史错误对外稳定，direct 不触发翻译资源加载。 |
| AC3、AC4、AC5 | `tests.test_job_render_resources` 与实际正式发布证据用例 | 任务消费同一 YAML 字节和哈希，内置页眉介质保留，外部资产改动不进入正式路径，历史实物可内部下载，旧 `complete` 证据被重核，合规模板有完整证明，已发布记录与下载可用。 |
| AC1、AC2 | 前端对应模板表单及版本操作的定向测试和 `cd frontend && npm run build` | multipart 必填、继承提示、历史版本标识、动作与后端响应一致。 |

优先使用 `.venv/bin/python -m unittest <目标类或用例>`。测试按变更选择实际入口。持久化层事务若沿用原实现，用服务层的指针和审计断言验证本次前置拒绝。若改动锁或事务行为，再选择 `tests.test_template_default_switch_mysql` 中直接覆盖该行为的用例。前端仅在实际改动后执行相应检查。

## 实施核对

- 各层都从相同版本与已认证 YAML 字节判定。显式无 YAML、历史缺字段、半绑定和文件损坏分别验证。
- 已发布内置 YAML 的字节与哈希保持一致。正式渲染封住外部路径读取，历史任务可按既有权限恢复。
- 最终检查改动和工作树。默认版本切换、历史修复、部署和在线业务验收另行授权。

## 定向验收记录

- 模板与 API 组 68 项通过。覆盖 YAML 必绑、旧版本读写分界、两级默认切换、旧指针迁移、新 seed 禁止外链、样式草稿、模板校验及 OpenAPI 发布检查中的模板子项。
- 任务、渲染与发布组 33 项通过。覆盖新建与克隆无副作用拒绝、旧任务重试及内部下载、file/SQLite YAML 消费校验、旧 `complete` 证明重核、发布重放及已发布最终件下载。
- 前端 Vitest 6 项、Chrome smoke 3 项以及生产构建（含 `vue-tsc`）通过。OpenAPI 快照检查、Trellis 上下文校验和 `git diff --check` 通过。
- 实际渲染两版内置配置，核对 DOCX 页眉关系指向的图片字节，并断言不解析外部路径。原始 YAML 与 `HEAD` 逐字节一致。SHA-256 分别为 `1a9ce13488a491367fbfde8d143d22b6cf7c0ce064c99c224ae09ef93f5b3818` 和 `132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d`。
- 两组旧下载可用性测试的失败和异常在干净 `HEAD` 的相同测试上复现。旧模式测试 `test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot` 的公开 `page_quality` 投影断言也在干净 `HEAD` 复现。保留这几组既有用例。
- 本地定向验收使用文件、SQLite、测试仓储及本地浏览器。真实 MySQL、生产环境和完整发布门禁未验证。
