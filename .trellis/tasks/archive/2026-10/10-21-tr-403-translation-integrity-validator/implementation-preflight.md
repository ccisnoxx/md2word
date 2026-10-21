# TR-403 实施准入与基线

日期：2026-10-21。用户已明确批准 revision 3 三件套及当前任务实现；本文件记录实施授权后的事实，不改写早期规划记录。

## 准入

- 工作目录 /Users/sc/PycharmProjects/md2word；从 HEAD c8fd2afc7dfea349b7fbc3e1f516d85adcb57536 新建并切换 md2word/TR-403，未 stash、提交或丢弃任何原有改动。
- TR-403 准入时 manifest/Trellis=planning；TR-402=done/implemented，归档 completed 且人工验收，实现提交 24ed6a717ca86cf5ed086f2eda58030e4af66810 是 HEAD 祖先。
- manifest 无冲突 in_progress；TAB-307 的 Trellis in_progress 是已实现待人工验收的隔离任务（manifest=review），SC1259 为另一隔离任务；不合入它们的业务改动。启动时 app/tests/scripts/实际 Spec 相对 HEAD 无 diff。
- 成功执行 task.py start .trellis/tasks/10-21-tr-403-translation-integrity-validator；session 指针准确，Trellis=in_progress。manifest 只把 TR-403 改 in_progress；本任务 task.json 记录 planning_revision_accepted=3、implementation_authorized=true、planning_review=accepted。
- revision 3 fresh architect 规划复审无确认新问题，audit_id=20261021T070653Z-tr-403-revision3-fresh-architect-review-57db9cc7；这只提供规划证据，不替代实现独立复核。
- 根原有 1466 个 tracked/untracked 文件已做临时哈希基线，完成时核对非本任务路径；不把未知 dirty 混入提交计划。

## 实际基线

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_protected_tokens
~~~

35 tests / OK，退出 0。本轮实施前重新执行，不借早期规划结果冒充当前运行。

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
~~~

退出 1，ok=False；manifest 检查通过（available=3、required=1、missing=[]），阻断为 p1_auth_missing、p1_runtime_unreachable。runtime 检查因缺 P1_TRANSLATION_PASSWORD/P1_TRANSLATION_BEARER_TOKEN 在构造认证 session 时停止；未请求外部模型、未创建任务或启动 API。属于现有环境/认证阻断，不是 Validator 测试失败；不尝试读取凭据或启动服务绕过。

translation-core 尚未注册：scripts/dev/run_local_mineru_quality_matrix.py 的 SAMPLE_SETS 只有 phase2-core、ru2zh-acceptance，既有 ALL_MODES 为 direct/en2zh/ru2zh。因此不执行不存在样本集命令或制造新样本体系，记录为未验；四方向正式样本/总门禁属 TR-407。本任务以公开 OPA228 fixture 和 fake 接线测试提供本地证据。

## 实施与验证边界

只执行当前批准的 AC1–AC12，保留有限 Codec 语法、不自动修复、整批失败和所有冻结不变量。无 HTTP DTO/DB/schema/前端变化，无新依赖或 feature flag。文件新 key 仅改变 opaque 物理身份，历史按记录读取。

项目 .codex/agents/trellis-implement.toml 与 trellis-check.toml 的模型/推理档位仅为注释，无法满足 multi-agent-orchestration 的固定 Profile 审计要求；不修改配置。固定 deep_engineer/implementer 承接相同 Trellis 实现流程，以 Active task 和 implement.jsonl 子侧加载为 fallback；主会话执行 Trellis check/Spec 同步，并取得 fresh critical_reviewer 的独立只读候选审查。

普通测试全部 fake/本地临时存储；不运行真实模型、线上操作、DB服务、浏览器或Word。候选稳定后只运行批准且直接相关门禁；业务测试与 release 的实际结果在 implementation-validation.md 收口。完成仅 manifest=review、Trellis=in_progress，不 done/archive，不提交/push。
