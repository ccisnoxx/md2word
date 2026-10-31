# 执行与提交记录：第一批快照

本文件记录当前提交的交付范围。任务总规划仍包含两批；本提交只纳入结果根唯一性，编号标题层级的实现与完成记录由后一提交纳入。

## 授权与隔离

- [x] 用户批准最小任务、最终规划及两批实施。
- [x] 已从 main `a942bbda` 建立独立 worktree，实施时记录原有五个工作区保留基线。
- [x] 用户后续授权仅创建两个本地提交，不再运行测试，不配置 CI，不推送、合并或删除分支。
- [x] 当前 worktree 提交前暂存区为空；五份源码/直接回归文件与此前成功时的内容指纹一致。其他工作区及历史维护不纳入提交。

## 第一批：结果根唯一性（AC1–AC3）

- [x] 只修改 `mineru_package.py::find_content_list`，先检查结果根唯一，再检查 v2 优先后的被选版本唯一。
- [x] 新增独立 `tests/test_mineru_result_root_uniqueness.py`，覆盖单根选择、多根、重复、缺失、正式转换报告与坏 v2 不回退。
- [x] 实施轮只运行该新增模块一次，14/14 通过，退出码 0；没有失败或重跑。
- [x] 当前提交仅纳入 INPUT-001 的必要合同更新，TEXT-001 留给后一提交。
- [x] 已静态复核本批实际改动及既有通过日志；提交轮直接复用，不运行测试、lint、类型检查、构建或聚合脚本。

## 第二批：后继提交范围（AC4–AC5）

- [ ] 将 `text_semantics.py` 的源标题窄规则、`mineru_converter.py` 接线与独立标题回归纳入后一提交。
- [ ] 将 TEXT-001 的必要合同和第二批实际完成记录随后一提交保存。

此处勾选状态描述提交包含关系，不表示当前完整 worktree 的第二批实现尚未完成；该批源码和直接回归在本提交中均未暂存。

## 当前提交路径

- `app/services/document_ir/mineru_package.py`
- `tests/test_mineru_result_root_uniqueness.py`
- `.trellis/spec/backend/word-generation-rules.md`：只含 INPUT-001 更新。
- 本任务的 `prd.md`、`design.md`、`implement.md`、`task.json`、`implement.jsonl`、`check.jsonl`：两批共享规划与第一批完成记录。

## 证据与边界

既有第一批命令、退出码和原始输出位于 worktree 外 `evidence/batch1-regression.json`、`batch1-regression.log`；新增/更新 docstring 为中文。验证仅覆盖输入选择及直接受影响的转换失败合同，不代表全仓或线上验收。

提交轮保留基线和最终核对保存在 `evidence/local-commits-20261031/`。不执行 archive/add_session，避免产生授权两笔之外的 bookkeeping 提交。
