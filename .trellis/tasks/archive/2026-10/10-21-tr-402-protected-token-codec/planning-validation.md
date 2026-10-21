# TR-402 规划验证记录

日期：2026-10-21（Asia/Shanghai）。本记录只描述规划轮实际证据，不代表 Codec 实现验收。

## 任务和依赖

- 子任务：.trellis/tasks/10-21-tr-402-protected-token-codec。
- 父任务：.trellis/tasks/10-12-datasheet-docx-delivery-quality，仅新增该 child，其他字段相对于本轮启动快照不变。
- manifest：仅 TR-402 从 todo 改 planning 并记录路径/规划说明；其他 44 个任务对象和 TR-402 stanza 之外的文件字节不变。
- BAS-001：manifest done、归档 task completed、人工验收记录存在；工作提交 107624d7e87f8287c83020d9c751e9d54d23d855 为当前 HEAD 祖先，merge-base --is-ancestor 退出 0。
- 实际分支 main，HEAD 4c40e6c52bde072a7ad3afab67eb425f757bd33c；建议 md2word/TR-402 仅记作规划元数据。
- 子任务以 create --parent ... --no-start 创建；task.py current --source 返回 Current task: (none)、Source: none（无活动任务时退出 1 为 CLI 正常约定）。

## 已执行检查

| 检查 | 实际结果 |
|---|---|
| pwd、git status --short | 仓库路径正确；已有多项 dirty/untracked，不 stash、不删除或覆盖。 |
| 当前翻译基线 | PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_runtime_characterization：21 tests，OK，退出 0。 |
| 只读行为探针 | 复现 legacy 源文 PH 碰撞破坏 roundtrip、集合验证放过重复，以及正式 ID 校验接受 25°C→99°C；详 research/current-state.md。 |
| task.py validate | python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-402-protected-token-codec：implement.jsonl 3 entries、check.jsonl 3 entries，All validations passed，退出 0。此命令验证 JSONL/路径，不验证算法。 |
| git diff --check | 通过，退出 0。 |
| 规划文档和 context 自检 | 三份规划、任务 JSON、两份 JSONL 可读；无 TBD、行尾空白或失效的相对链接；context 无 seed-only 行，各 3 条有效 Spec/研究引用。 |
| 原工作区保护 | 创建前记录的 386 个 dirty/untracked 文件仍存在；384 个非任务文件 SHA-256 完全不变；另外两份共享文件仅有上述允许增量。 |
| 业务范围 | 未创建 protected_tokens.py 或 test_protected_tokens.py，未改业务/测试/API/数据库/配置/前端/Prompt；新增交付仅限当前任务目录及父/manifest 元数据增量。 |

## 规划收敛与覆盖边界

prd.md 已按目标、事实、范围、可观察 AC、权限失败、不变量和评审门完成收敛复读与修订；design.md 包含实际实现差距、分类顺序、批次碰撞规避、逐 item 次数和非递归恢复、跨层影响、兼容安全及回滚；implement.md 提供顺序、写边界、AC 测试映射、定向门和非适用检查理由。

额外收敛了源文残缺占位前缀的保护与解码扫描器一致性，避免源文自己被判为未知/篡改；完整 URL/公式优先于其内部字面量，避免破坏整体保护。不存在需要用户先裁定才能完成规划的冲突；三份文档仍是待人工批准方案。

没有运行未来 Codec 测试，因为没有实现；未运行 release/full suite、P1/runtime、真实 Provider、MySQL、浏览器或 Word 验收，因为当前只做规划且未接生产。当前 21 项基线不能证明未来 Codec 或生产技术完整性达标；需要实施期按 AC 补齐证据。

本轮未派发子代理，没有独立候选代码复核或相关审计摘要。候选实现的独立合同复核已列入 implement.md，不把本次自检称为独立审查。

## 最终交付边界

交付为当前任务内三份规划、调查证据、本记录、task.json 和两份 context（共 8 文件），外加父任务 child 链接与 TR-402 manifest stanza。Trellis/manifest 均 planning，planning_review=pending，implementation_authorized=false。

一次性保护快照保存在操作系统临时目录，核对完成后移除；没有创建后台服务、端口监听或长运行作业。原工作区其他 dirty/untracked 全部保留；不写 journal、不执行 archive/add_session、不提交、不 push。等待用户审核最新三份规划。
