# 执行、最小验证与本地提交记录

## 实施轮结果（已执行，提交轮复用）

- [x] 用户确认创建最小任务，仅允许新增两组直接回归。
- [x] 固定 main `a942bbda`，建立新分支与干净 worktree；记录原有五个工作区保留基线。
- [x] 完成 PRD、设计、执行清单及真实 Spec 上下文；阻塞产品问题为空。
- [x] 已向用户呈现最终规划，并收到后续明确实施确认。
- [x] 已在本任务 worktree 运行 `task.py start`，状态为 in_progress；开始第一批。

## 第一批（AC1–AC3）

- [x] 只修改 `mineru_package.py::find_content_list` 的根唯一性与被选版本唯一性。
- [x] 新增 `tests/test_mineru_result_root_uniqueness.py`；独立夹具覆盖单根选择、跨版本多根、同版重复、缺失、坏 v2 不回退和错误分类。
- [x] 仅运行新增结果根模块一次：14/14 通过，退出码 0；原始输出与执行元数据已保存到 worktree 外 evidence。
- [x] 第一批无实际失败；未维护旧测试、未扩大 owner。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_mineru_result_root_uniqueness -v
```

执行目录为本任务 worktree。实际结果：14 个测试通过；日志为 `batch1-regression.log`，真实退出码与命令见 `batch1-regression.json`。

## 第二批（AC4–AC5）

- [x] 在 `text_semantics.py` 新增 `infer_source_heading_level`，旧三级推断函数保持原文，公式/字面文本处理未改。
- [x] 在 `mineru_converter.py` 的显式 heading 路径接线并复用已提取文字；原源层级解析与 1–6 级裁剪保持原文。
- [x] 新增 `tests/test_document_ir_numbered_heading_levels.py`，经过正式 converter 观察深度、无编号源层级、普通段落与原文顺序。
- [x] 仅运行新增标题模块一次：10/10 通过，退出码 0；复用第一批成功结果，未重跑第一批。
- [x] 第二批无实际失败；两批均无修复重跑，未运行旧测试或聚合检查。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_ir_numbered_heading_levels -v
```

## 必要文档与静态复核（AC6）

- [x] 只在本 worktree 更新 INPUT-001/TEXT-001 的实际合同与新直接回归入口；历史维护的文档同步改动未搬入。
- [x] 实施轮已检查产品、直接回归与必要 Spec 的最终差异；当时所有改动保留未暂存，未产生应用缓存或生成文件。
- [x] 产品函数及新增测试模块的 docstring 使用中文；未新增日志或修改既有异常文案，机器错误码保留英文，未改未触及的旧注释。
- [x] 主代理与独立 trellis-check 已静态复核，未发现需要修复的实际缺陷；复用14/14与10/10通过证据，未重跑测试，未运行 lint、构建、类型检查等应用检查。
- [x] 原有五个工作区的 HEAD、分支、索引、状态及文件指纹与 baseline 一致；11 个远程分支与仓库配置不变。本地业务引用仅增加本任务分支，Codex 差异快照命名空间的轮换单独记录。
- [x] 已记录实际检查结果与边界；实施轮按当时授权保留未提交。本提交轮仅创建两笔本地提交，仍不运行 archive/add_session 或产生额外 bookkeeping 提交。

## 禁止自动扩展

本提交轮仅授权将两批对应源码、直接回归、必要 Spec 和任务记录分别保存为两个本地提交，不再运行任何测试。不配置 Actions/CI/必需状态检查，不运行构建、lint、类型检查、发布脚本或线上验证；不推送、合并、关 PR 或删分支，不处理其他功能候选。

## 证据位置

`/Users/sc/.codex/worktrees/mineru-root-heading-20261031-xtefthlw/evidence/`。现有 `before.json` 为保留基线，`context.json` 为本次工作路径与授权范围；第一批新增回归 14/14、第二批新增回归 10/10 均通过，各执行一次；未运行其他测试。第二批日志和真实命令见 `batch2-regression.log`、`batch2-regression.json`。

## 实际执行结果

| 批次 | 唯一执行模块 | 执行次数 | 结果 |
| --- | --- | --- | --- |
| 结果根唯一性 | `tests.test_mineru_result_root_uniqueness` | 1 | 14/14 通过，退出码 0 |
| 编号标题层级 | `tests.test_document_ir_numbered_heading_levels` | 1 | 10/10 通过，退出码 0 |

没有实际失败或修复重跑。第一批的选择 owner 和回归夹具保持成功时的指纹；第二批只在显式 heading 接线，不影响第一批的选择/读取失败路径。只读复核后五个产品/直接回归文件指纹均与成功记录相同。

独立 trellis-check 严格只读，未发现阻塞或未修复的实际问题。复核结果见外部 `static-review-result.json`；两份原始日志和真实命令/退出码保存在同一 evidence 目录。

验证只覆盖本次两组直接回归与静态审阅，不代表全仓、构建、Word 输出、部署或逐页视觉验收。旧测试、lint、类型检查、CI 与聚合脚本均未运行。

代码、直接回归、必要 Spec 和任务记录按两批保存为本地提交。任务保留 in_progress、不自动归档；不运行 archive/add_session，避免产生授权两笔之外的提交。此状态不表示两批实现或直接回归尚未完成。

实施轮结束时保留核对通过：当时本 worktree 恰有三份产品源码、两份新增直接回归、一份必要 Spec 和六份本任务记录，共 12 条未暂存路径。原有五个工作区的文件、索引和 HEAD 完全一致，历史维护仍为 11 个测试与 2 份文档未提交。

实施轮引用核对的初次全命名空间比较包含 `refs/codex/turn-diffs/` 的会话快照轮换；确认其差异只指向 baseline 中已存在的对象，分支、标签和远程跟踪引用均符合预期。原始报告保留在 `final-preservation-initial-result.json`，分类后的结果见 `final-preservation-result.json`。当次核对未修改或恢复任何 Git 引用，也未重复采集已经成功的文件/索引检查。

## 本地提交（本轮新增授权）

- 第一批：`dd32568c21b87f364c9bcbbcb087b15963a339b9`，纳入结果根唯一性源码、独立直接回归、INPUT-001 与共享规划及第一批任务记录。
- 第二批：本段记录所在的提交，纳入源标题编号窄规则、converter 接线、独立直接回归、TEXT-001 与最终任务记录。第二批的精确 SHA 以 Git 历史及外部 `commits.json` 为准，避免为回填自身 SHA 产生第三笔提交。
- 两组直接回归均复用实施轮成功结果（14/14、10/10，各一次），本提交轮没有运行测试或其他应用检查；五份源码/回归文件内容与成功时相同。
- 共用 Spec 在第一笔仅纳入 INPUT-001，第二笔仅纳入 TEXT-001；其他工作区及历史测试、文档同步改动不纳入任何提交。
- 提交前已记录五个其他工作区的文件、索引、状态、HEAD、本地业务引用与远程分支基线。提交轮最终保留核对与提交精确路径记录位于 worktree 外 `evidence/local-commits-20261031/`，不作为额外仓库提交。
