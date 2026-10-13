# BAS-001 执行验证

日期：2026-10-12（America/Los_Angeles）。HEAD `fcea60ff8c131edff7fd5ba360e1bf4e37ec4227`，分支 `md2word/BAS-001`。

## 本地基线与验收

完整命令/退出码/耗时/日志哈希、六项事实及 AC1–AC7 见 `docs/implementation/baseline-verification-2026-10-12.md`。

- release：202 项通过，OpenAPI 164 paths/322 schemas current；frontend contract/mock 通过。
- IR/translation/converter：30 项通过；fake MySQL 缺列维护：1 项通过；三项 API direct QA/失败审计/retry 旧文件过滤通过。
- component：1/1 succeeded、DOCX openable；不代表 Word 视觉签字。
- P1 preflight：退出 1；manifest 3 available/required 1，缺认证而未发 readiness 请求。精确 blocker 为 p1_auth_missing、p1_runtime_unreachable；未复跑/未修业务。
- frontend unit：31 files/127 tests 通过；build 的 vue-tsc/Vite 通过；因原 dist 存在而输出到任务临时目录。
- 合成探针：三项退出 0，现有 converter + fake translator/正式 renderer 证实 annotation、paragraph、reference 缺口，见 research/reproduction-evidence.md。
- Golden/P1 完整在线、Playwright、Word 人工、真实 MySQL 均未运行，原因与历史版本边界见报告。

## 轻量门禁

- `python3 .trellis/scripts/task.py validate .trellis/tasks/10-12-bas-001-current-capability-baseline`：通过；implement.jsonl 3、check.jsonl 5。
- `git diff --check`：通过；另检未跟踪本任务 Markdown 的行尾空白及相对链接。
- 比较启动快照与当前 manifest：除 BAS-001 外任务对象完全不变；父任务仅有本次子关系，未变状态。
- `git diff -- app frontend tests scripts docs/api docs/dev resources`：空；没有业务/测试/配置/样本修改。
- `.gitignore` SHA-256 保持 `b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`。
- 一次性文档核对最初用系统 `python3` 导入 yaml 失败（ModuleNotFoundError）；切换项目 `.venv/bin/python` 后执行成功。该失败属核对工具环境，不是业务测试失败，未安装依赖。

## 交付状态

manifest：planning → in_progress → review，resolution=null。准确子任务经 start 为 in_progress；规划批准记录已写 task.json，实施尚未人工验收。未提交、未 push、未 archive。

执行流程由主代理完成，专用 Trellis profile 未声明审计要求的固定模型字段，未修改代理配置。只读 reviewer 的复核结果和清理确认在下方补记。

## 独立复核与处置

fresh reviewer 只读核对任务、报告、源码、测试及 diff，确认一项 P2 文档问题：component 的 `Settings()` 会自动加载 `.env`，报告原先“无凭据内容读取”过于绝对。主代理对照 `formal_mineru_conversion.py:141` 与 `config.py:18` 确认后，改为未人工查看/输出凭据，并明确自动配置加载及跨环境复现限制；没有改代码或重复测试。其余六项结论、合成探针、状态与范围未发现可确认问题。复核未独立重跑测试，不补造线上/Word/真实 MySQL 证据。

补查 component IR 为 4 blocks、quality_flags=["middle_json_missing"]，因为最小 fixture 只有 content list、没有 layout/middle 页尺寸文件；该既有 flag 已在报告解释，不新增/压制 flag。

review 前后工作区 dirty/未跟踪集合及内容哈希一致，未观察到 reviewer 仓库写入。主代理随后只修上述文档措辞、补 flag、整理 Spec 段落及验收记录。

## 清理与最终交付

本次新增的 `tests/tmp/component_pdf_regression/20261013T041428Z` 和临时 frontend-dist 已删除；原有两个 component run、frontend/dist、依赖缓存保留。临时脚本/日志在最终摘要固化后清理，仅保留正式报告和 Markdown 中可复制的复现代码。准确 Trellis 会话指针保留，用于人工验收前维持 in_progress，不属于应删除的运行资源。

审计 Bundle `20261013T042110Z-bas-001-7e900ee3` 管理独立只读复核；digest 的 reviewer 验收仅指复核责任完成，不代表用户接受 BAS-001 实施。无活跃测试/构建进程、无本任务后台服务。

审计工具已成功生成并校验 SUBAGENT_EXECUTION_DIGEST：1 次 reviewer 尝试、1 次复核责任验收、1 次独立复核，未观察到写入，无残留活跃 worker、无异常；audit-finalize / audit-verify 均 passed。

## Commit plan（未执行）

建议单个提交：`docs(baseline): verify BAS-001 current capabilities and test baseline`。
显式选择正式 baseline 报告、database-guidelines 的事实补充、BAS-001 manifest 增量、父 task.json 的子关系，以及当前子任务内 10 份规划/证据/context/元数据文件。总计 14 个文件；排除 `.gitignore`、其他任务、临时产物与用户配置。不执行 git add/commit/push，等待人工验收与授权。

## 2026-10-12 人工验收收尾复核

用户已接受实现、测试证据及残余风险，明确确认 commit plan 并授权当前任务提交及归档；不 push、不启动后续任务。开始时 BAS-001=review、DOC-001=done，分支 md2word/BAS-001；暂存区为空，非任务 dirty 仅 .gitignore（哈希保持）。

| 验收 | 收尾核对 |
|---|---|
| AC1 | 报告身份、依赖、环境、命令及六项实现路径齐全；基线版本仍为 fcea60ff8c131edff7fd5ba360e1bf4e37ec4227。 |
| AC2 | 工具/任务预览、资源/成品发布、分页/合并、maintenance/版本迁移区分明确。 |
| AC3 | 已报告 A–H 结果逐项复核；release 202、IR 30、fake MySQL 1、API 3、component 1/1、frontend 127 与 build 通过；P1 preflight rc1 为缺认证，不改写为通过。 |
| AC4 | 三项探针的完整输入/代码/输出保留；结论指向真实实现和既有测试，线上/Word/真实 DB 未验证的边界保留。 |
| AC5 | backlog 建议有明确 ID、缺口和依赖理由，未修改其他任务。BAS-001 报告本轮新交付，状态应为 done。 |
| AC6 | 业务、测试、API、DB、配置、资源、样本未变；.gitignore 保留；其他 44 个 manifest task 及父任务状态不变。 |
| AC7 | 三份规划/context/证据完整，原 review 门已获人工接受；本轮按新授权提交归档，不违背之前等待验收要求。 |

Spec-sync 已复核：database-guidelines 中已有本任务的 maintenance 事实补充与 fake 证据边界；本轮没有新的知识或合同变更，无需另加 Spec。当前是 Phase 3 收尾，由主代理处理，无新增代码检查或代理派发。

轻量门禁：git diff --check、未跟踪 Markdown 空白/相对链接、JSON/JSONL 及 context 路径、task.py validate、manifest 其他任务对象对比、业务路径 diff、精确暂存 allowlist。归档后还须复验新路径和会话指针。业务代码与测试输入未变，沿用已获人工接受的测试结果，不重复全量测试/构建。

archive / add_session 默认会自动提交；已向用户说明本轮使用 --no-commit，在核对路径和精确文件后分别提交归档与日志，以保持工作提交→归档提交→journal 提交顺序。无未知 dirty 纳入提交。

归档前轻量复验已通过：task.py validate（implement 3/check 5）、git diff --check、文档链接/空白/JSONL 路径、manifest 44 项不变、父任务不变、业务 diff 为空和 gitignore 哈希一致。
