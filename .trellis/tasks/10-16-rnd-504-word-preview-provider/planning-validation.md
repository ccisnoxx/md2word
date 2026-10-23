# RND-504 修订 4 规划与独立审查验证

日期：2026-10-23。结果：修订 4 的两项规划问题经同一 architect 定向复核闭合，等待人工审核；task/manifest 仍 planning，未授权实施。

## 本轮交付

- 复用任务 `.trellis/tasks/10-16-rnd-504-word-preview-provider`；当前基线 HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`、分支 `md2word/RND-503` 不变。
- 一位全新 architect、fork_turns=none，独立只读审查修订 3，确认 2 项 P2；主会话分别核实源原函数反例并修订三件套为 4。同一审查者定向复核确认 R1/R2 规划层闭合，未确认修订引入新矛盾。详 planning-review.md。
- 原修订 3 三件套及验证记录保存在 research/review-v3/；历史修订 2 实现/验收原件仍在 research/history/，均未覆盖。
- R1 补登记前阶段 CAS、本 attempt 可信终态确认、耗尽分类与未知存储失败关闭；R2 补成功证据有效性、新 key 的失效预览有界恢复、旧 key 历史重放及锁外观测/锁内 CAS。PRD、设计、实施步骤和组合验收同步。

## 证据及限制

| 检查 | 结果与边界 |
|---|---|
| 修订 3 初次独立审查只读保护 | 986 个受控文件变化 0、新文件 0，HEAD/分支/cached diff 相同。 |
| 修订 4 定向复核只读保护 | 991 个受控文件变化 0、新文件 0，三件套字节与送审时一致。详 research/architect-review-protection.json。 |
| 主会话 R1 最小反例 | 内存加载 931d2f6 原模型/claim/ensure_initial；最后 attempt lease 过期后 manifest=null、preview_finished=true、quality=blocked，恢复 Provider 调用0。只证明源控制流；登记中断由审查者的内存文件服务/BaseException probe 与原 I/O 顺序支持，未称真实磁盘崩溃实验。 |
| 主会话 R2 最小反例 | 源 claim/finish 与到期 guard：主件90天、manifest1天，第2天授权false，新key仍reused/succeeded、同过期manifest且keys=2。无引擎/对象I/O；与审查者的内存应用链观察一致。 |
| 源集成清单 | 审查者逐项核对37个 source/source-parent/target blob，mismatch=0；不是补丁已应用或业务集成验收。 |
| `task.py validate` | 修订4 exit 0，implement/check 各11条真实context，无warning/截断；新增1条审查反例与修订追踪。 |
| JSON/JSONL/YAML与Markdown格式 | 使用现有venv核验；三件套/context/审查记录在单文件注入上限内，未新增依赖。最终格式和工作区结果见 planning-review-protection.json。 |
| 当前目标原22项、历史源40项 | 复用上一轮规划的成功证据，详 research/review-v3/planning-validation.md；业务代码未变，本轮未重复整套测试，不称修订4已经实现。 |

## 工作区与授权边界

本轮允许增量仅为当前子任务内规划/审查/context/元数据，以及 manifest 的 RND-504 notes；父任务、其他任务、backlog、日志和原 dirty 不变。最终对初始986受控文件逐hash比较并核对新增路径、分支/HEAD及cached diff，详 planning-review-protection.json。

没有业务源码/API/数据库/部署/前端改动，没有 task.py start、提交、push、archive、add_session、stash、切分支或服务启用。Trellis当前指针保持none。新增及修订规划文字为中文，未改业务Python注释/docstring/日志。

CON-103依赖仍done，原人工验收证据不变；当前目标缺preview能力，仍采用历史实现的最小复用集成，不建议当前skipped_existing。真实引擎/validator/fonts/sandbox、MySQL/InnoDB/部署FS/S3、线上Golden、Microsoft Word视觉与生产回退未验证，production_ready=false、backend=disabled。没有业务候选，独立规划审查不能替代后续实际diff复核或人工验收。

## 修订 4 三件套指纹

| 文件 | SHA-256 |
|---|---|
| prd.md | `b8e6756a61aacb863c96af9694ada504c9cc4f596cbdcda6bcff223a6187b62e` |
| design.md | `7b5c184a725f0861594450c4ab3682e4ab275be18bb68eea353929b524cf9d40` |
| implement.md | `a718d7b828e3904c936e9c17da91ff235cdad6c04455742105135009278b41c0` |

停在规划评审门；后续实施必须另获对修订4及当时真实基线的明确批准。
