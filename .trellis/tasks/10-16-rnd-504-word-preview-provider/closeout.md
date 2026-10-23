# RND-504 人工验收与收口

用户已明确接受本任务实现、独立复核结论、验证证据、列明基线失败与未验证边界，并确认仅本任务三次本地提交及Trellis归档计划，授权在独立工作树执行。禁止push、合回原分支、删除/归档工作树、生产启用或启动其他任务。本记录只更新实施报告中的阶段性“待人工验收/停review”说明，不修改历史验证结论或冻结三件套。

## 执行边界

- 实际工作树：`/Users/sc/.codex/worktrees/rnd504-current-integration/md2word`；分支`codex/rnd504-current-integration`；初始HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`。
- 原根`/Users/sc/PycharmProjects/md2word`的业务、分支、HEAD、原302暂存删除、其余index条目、无关dirty、原日志和72份样本输入保持。仅最后同步本任务归档镜像与manifest局部。
- 38个已验收业务/测试/Spec/docs SHA仍与research/candidate-files.json匹配，清单SHA `04ac039011f8cda8dab591bb660ed2c03f38189bbb1d9e3a620eba6f50782d08`。不修改业务，不重跑未变代码的重门禁。
- 依赖CON-103按原根权威manifest为done；独立树中其他任务条目保持HEAD原样，不为本次收口同步其历史状态。
- 生产backend=disabled、production_ready=false，required默认false；不改.env/部署，不安装实际引擎。

## 已确认的三次提交

1. `feat(preview): 接入 Word 预览 Provider 与 Artifact（RND-504）`：38个验收文件、本任务三件套/研究/验证/复核/收口证据、manifest仅RND-504说明、父任务仅child关联。
2. `chore(task): 归档 RND-504 WordPreviewProvider`：工作提交成功后记录真实SHA，`task.py archive ... --no-commit`；仅本任务移动/完成元数据与manifest RND-504=done、implemented、实际归档路径。
3. `chore: 记录 RND-504 收口日志`：`add_session.py ... --no-commit`后，仅独立树本次实际journal/index变更；引用工作提交SHA，不复制覆盖根dirty日志。

归档和日志脚本默认可能自动暂存/提交，用户已知悉；本轮均显式no-commit，逐次精确暂存白名单并检查完整暂存差异。无git add .、无广泛archive目录暂存、无自动提交副作用。

## 验收证据与保留限制

最终应用35项通过，未变Provider/持久化成功证据复用，总63项覆盖；post-review release203项通过，OpenAPI/前端合同通过。既有113项仍有5 selectors/6 failures，均在未改HEAD复现并获用户接受，没有隐藏或计通过。component1/1、direct5/5且P0=0；P1/P2提示和Word视觉未签字。三项实现P2独立复审closed。

真实引擎/validator/字体/批准隔离、真实MySQL/部署FS/S3、线上Golden、Microsoft Word视觉及部署回滚未验，接受本项交付不表示这些门禁通过。生产继续disabled，不清blocker、不恢复批准、不改发布资格/不可变/Token/内容完整性/路径边界。

## 本轮预检

候选哈希无漂移、工作树index空、目标归档当前不存在、任务hooks和Git hooks均无启用。初始保护摘要见closeout-protection-before.json，完整快照保存在该摘要所列临时证据目录。后续归档提交记录工作提交SHA，最终日志提交前生成closeout-protection-after.json；最终三SHA由Git历史与答复给出，避免提交自身SHA递归。
