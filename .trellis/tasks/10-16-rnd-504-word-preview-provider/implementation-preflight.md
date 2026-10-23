# RND-504 实施预检

2026-10-23。用户接受修订4并授权实施；原三件套字节冻结，当前授权见 implementation-authorization.md。

- 依赖：根权威manifest CON-103=done，归档completed与人工接受证据一致；不启动其他任务。
- 目标：独立managed worktree `/Users/sc/.codex/worktrees/rnd504-current-integration/md2word`，分支 `codex/rnd504-current-integration`，基线 `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`；历史同名分支不改写。
- 原工作区：`/Users/sc/PycharmProjects/md2word`、分支 `md2word/RND-503`，未识别dirty/暂存删除保留。完整路径哈希、cached diff和批准文档哈希保存在授权文件指向的保护快照，结束时比较；不stash/reset/clean/stage/commit/push。
- 已仅对本子任务在新工作树执行task.py start，状态in_progress；根任务同步元数据，未对根/父/其他任务start。批准文档哈希核对无漂移。
- 当前最小基线：实施代理在新工作树运行delivery_state/download_availability/generated_artifact_identity，22项通过（0.371s），不是预览集成验收。
- 角色：原生trellis-implement独占app/tests，主会话拥有Spec/文档和本任务证据。后续trellis-check及独立critical_reviewer复核实际diff；二者不同于已完成的规划architect审查。
- context：implement/check各12项，当前word-preview-contract替换历史参考，task.py validate通过；不注入整个仓库，冻结三件套未改。
- Python：复用原工作区venv绝对解释器，新工作树cwd及PYTHONPATH显式指定；不复制.env/密钥，不安装依赖，不启动服务。
- direct预检：新工作树直接CLI dry-run退出1，5项均sample_input_missing；原工作区既有对应5个MinerU包已定位，后续通过原脚本模块ROOT仅调整样本查找根（当前模块只在查找使用该全局），保持代码/默认模板/输出为新工作树；输入hash快照见research/implementation-sample-inputs-before.json。dry-run不计内容通过，不执行视觉命令或生产引擎。
- 边界：生产默认disabled，production_ready=false；真实MySQL/部署FS/S3/引擎/Word/线上Golden另门，离线protocol测试不冒充生产证据。当前完成出口review，禁止提交/push/归档/add_session/后续任务。
