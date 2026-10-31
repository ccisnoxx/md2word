# TR-402 人工验收与收尾

日期：2026-10-21（Asia/Shanghai）；实际分支 md2word/TR-402。

## 人工验收和授权

用户已明确审查并接受实现、测试证据与残余风险，并确认当前 commit plan，授权只提交当前任务及 Trellis 收尾，不 push、不实施后续任务。

收尾入口确认 manifest=review、Trellis=in_progress、BAS-001=done。当前工作区存在已识别的其他任务/文档/记账 dirty，不能视为全树干净，也不得整体暂存共享文件。

本任务新增了 Codec 和测试，存在实际行为增量，最终结论为 done / implemented，不属于 skipped_existing。

## AC 与 Spec-sync 复核

| 验收 | 本轮核验 |
|---|---|
| AC1–2 | 分类/跨度/优先级和确定性向量对应当前候选；源文件与已接受版本完全一致。 |
| AC3–4 | 批次内 1007 次唯一、源文前缀碰撞、字面量/残缺/部分重叠回归以及字符串/UTF-8 往返证据保留。 |
| AC5 | ID、次数、归属、篡改、未知和整批失败负例已由最终候选测试覆盖。 |
| AC6–7 | fake 自然语言修改/同 item 语序移动及普通中英俄文反例证据保留。 |
| AC8 | 公开 OPA228 fixture 走正式 converter/extractor，只做 Codec roundtrip，Provider 禁止调用。 |
| AC9 | 冻结成员、敏感 repr/异常、交错调用和原有 translation/legacy/direct 32 项回归证据不变。 |
| AC10 | Codec Spec 和索引、翻译设计及两轮独立复核均已同步；首轮 P1 已修复并被 fresh 复核关闭。 |

Spec-sync 已重新阅读七节 Codec 合同：前缀碰撞、完整字面量先认领、部分重叠残留代理、非递归恢复和有限语法/隐私边界均已记录。本轮不改业务，不产生新的 Spec 语义或规则，无需再加无关规范。

## 轻量验证与证据复用

- git diff --check：通过。
- task.py validate 当前任务：implement 4 / check 4，All validations passed，退出 0。
- 审计 audit-verify：passed，Bundle closed，无异常；不重新生成历史 Digest。
- 业务候选 SHA-256 保持 fa3f254c1e453413c2ba6a8f0094b670b77a92c05df50351d4d1872ad2ee31c7；测试保持 a1a909bb504bc262af02346622b3bc842ae799dffb9940d0b2b8df401f92ad31。
- 复用人工已接受的 Codec 24 项、既有回归 32 项及独立合同复核，不重复运行输入未变的测试、release 或线上检查。
- P1 preflight 缺认证退出 1、translation-core 样本集不存在、生产未接线/四方向实译未验等限制仍保留，已经用户明确接受；不改写成已通过。

收尾还检查文档/JSON/JSONL、精确暂存 allowlist 和其他 44 项 manifest 对象；归档后复验实际路径、context、会话指针与工作区。

## 提交与归档纪律

按工作提交 → 当前任务归档提交 → 当前会话记账提交顺序。archive 和 add_session 默认会自动提交，已向用户说明本轮全部使用 --no-commit，再核对准确暂存集合手动提交。

- 工作提交包括业务/测试、对应 Spec/设计、TR-402 正式任务文件，以及 manifest 仅 TR-402 stanza、父任务仅 TR-402 child 链接。
- 归档只移动当前任务，保留父任务 child 计数关系；manifest/context 的当前任务导航改到实际归档位置，不改变其他任务状态或历史命令事实。
- journal 原有 CON-102 Session 29 未提交内容不属于本任务，必须保留且不得混入。add_session 将分配 Session 30；选择性提交仅本次 entry 和对应索引更新，编号沿用现有高水位，不提交 Session 29 内容。
- 不执行 stash/reset/清理他人文件，不 push，不开始其他任务。

实际工作提交哈希、归档位置和最终核验结果在提交/归档后补记；记账提交以 git log 为准，避免把归档提交冒充工作提交。

## 实际提交与归档

- 工作提交：24ed6a717ca86cf5ed086f2eda58030e4af66810，仅18个当前任务文件及共享文件的TR-402增量。
- 已执行 task.py archive --no-commit，退出0；准确归档位置为 .trellis/tasks/archive/2026-10/10-21-tr-402-protected-token-codec。
- Trellis status=completed、completedAt=2026-10-21；manifest=done，resolution=implemented。
- implement/check 的研究引用已迁移，PRD 当前任务导航同步；历史命令/基线事实保留。
- 归档后 task.py validate：implement 4/check 4，退出0；current --source 返回无活动任务（退出1为无任务约定）。
- 归档后当前任务文档/JSONL路径、其他44个manifest任务、原有dirty和业务候选哈希核对保持；不扩大业务验证范围。
