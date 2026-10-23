# RND-504 修订 3 规划验证

日期：2026-10-23。结果：规划可评审；当前任务和 manifest 均 planning，尚未授权当前集成实施。

## 交付与身份

- 子任务准确路径：`.trellis/tasks/10-16-rnd-504-word-preview-provider`，父任务 `10-12-datasheet-docx-delivery-quality`。
- 复用本地 Git `48818e9` 已归档的同一 ID/slug；历史实现 `931d2f65738f7592a5b3e2dd4c528f9e1b2a0e19`。历史原件在 `research/history/`，未创建第二个 RND-504。
- 当前基线 HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`、分支 `md2word/RND-503` 保持。建议分支 `md2word/RND-504` 仅记入元数据，没有创建、切换、覆盖分支。
- prd/design/implement 为本次修订 3；包括权限/错误、当前合同适配、生产配置/协议/预算、Artifact、幂等/并发/质量恢复、兼容/回滚和有序验证计划。原 v2 完成状态不继承为本次实施授权。
- 依赖 CON-103 manifest=done，Git 归档 completed 与人工接受证据已核对。当前状态/复核/receipt 功能已集成，但原 bd828da 非当前 HEAD 祖先；实施前继续核实真实合同，不伪报提交已合入。

## 实际验证结果

| 检查 | 本轮结果与边界 |
|---|---|
| 当前目标：delivery_state / download_availability / generated_artifact_identity | 22 项，0.416s，OK；只证明已有相关基线。 |
| 源 931d2f6 独立临时快照：word_preview_provider / document_job_word_preview / document_job_preview_persistence | 40 项，23.636s，OK；cwd/PYTHONPATH 明确隔离。包含 tests-only 子进程和 fake，不是目标集成、真实生产引擎/沙箱或 Word 验收。 |
| `task.py validate .trellis/tasks/10-16-rnd-504-word-preview-provider` | 最终 exit 0，implement/check 各 10 条真实条目；无 warning。 |
| Context 截断检查 | 首次虽 exit 0，但完整 Word 规范 102309B 超 32768B；改为 8 条当前规则原文/hash/定位摘录（14957B），最终无截断。其他条目均在上限内，没有 seed/_example 或整仓目录。 |
| 规划文件 JSON/JSONL、manifest YAML、三件套尾行/尾空白 | 通过。系统 python3 不带 PyYAML，检查改用现有项目 venv 后通过；没有安装依赖。 |
| 本次已跟踪修改的 scoped `git diff --check` | 通过；新规划文件另作内容/尾空白检查，历史原件按源字节保留。 |
| 当前业务路径 diff | app/tests/scripts/frontend/docker/deploy/requirements 无暂存或未暂存增量。 |
| 工作区保护 | 全部原有文件逐 hash 复核；仅允许的 manifest、父 task 发生变化，unexpected=0；HEAD、分支、cached diff SHA-256 与起点一致。详 planning-protection.json。 |
| Manifest/父任务影响 | 仅 RND-504 条目有增量；其他任务与 manifest 顶层字段相同。父 task 仅 children 追加本子项，状态及其他字段不变。 |
| 活动任务 | `task.py current --source` 显示 none / Source:none；未执行 start，未写本次活动指针。 |

父关联恢复的工具限制：child 自带同一 parent，`add-subtask` 对任何已有 parent 均拒绝；检查 task_store.py 证实拒绝发生在写入前。未盲目重试或修改脚本，仅补父 children 的单侧缺失并比较原 JSON。

## 本次文件范围

1. 当前子任务：task.json、三件套、两个 JSONL、研究/源目标 blob 清单、当前规则摘录、历史原件和本验证/保护结果。
2. 父 task.json：仅新增当前 child，保留原 staged 删除及其他字段。
3. manifest：仅 RND-504 的 planning 记录/notes，task path 为当前实际复用路径；不更新其他任务状态。

没有修改业务源码、公共 API、数据库、部署配置、前端、backlog、其他任务规划或工作日志；没有 stash/提交/push、start、archive、add_session、切分支或生产启用。本轮 Markdown 文档为中文；未修改业务 Python 注释/docstring/日志。

## 当前差距与评审点

- 当前目标缺预览能力，历史已有已验收实现。采用“复用集成并验证收口”，当前不建议 skipped_existing；如果后续验收基线已经完整具备该能力，改为只验收，经人工接受后再建议 skipped_existing。
- 旧源不能整文件覆盖当前 CON-104、TR-406、RND-502/503 和全生成件独立 key；公式贡献与 preview blocker 的合成先后顺序是本修订新增明确的集成验收点。
- 尚无当前业务候选，本轮未做独立实际 diff 审查。历史独立复核只证明源当时验收；未来当前候选按 implement.md 取得独立只读复核。
- 真实引擎/validator/fonts/sandbox、真实 MySQL/InnoDB/部署 FS/S3、线上 Golden、Microsoft Word 视觉和生产回退均未验证；现有 publish 尚未实现，不宣称发布 E2E。保持 disabled，生产启用需另有批准及证据。
- 没有需要先作 SaaS/引擎选择或破坏性迁移的规划阻断；若未来必须新增未批准依赖且 port/fake 无法完成，或触及冻结产品规则/后续任务，则停止并回评审。

## 三件套冻结指纹

| 文件 | SHA-256 |
|---|---|
| prd.md | `557773773db7efd122237e26780c409e23d248bafbd1ec0bbec66273165e2cc6` |
| design.md | `05a5235052f1814c6e17758e168e0dc73d25a62d390e2d0a09b05e885a954570` |
| implement.md | `2aedba9e97ca29ffe477e7ac7aebab73e725719c08cf0e926edd741eb8740d93` |

停在规划评审门。下一次实施授权必须针对上述修订及当时真实基线；历史验收不构成本次 start、提交或生产启用许可。
