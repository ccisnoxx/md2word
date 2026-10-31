# 实施与最小验证计划

## 已批准边界

- [x] 从固定main建立独立worktree并记录原有七工作区基线
- [x] 用户确认审查方案并授权实施；另授权仅新增直接回归
- [x] PRD/design/implement按同一方案落地且可审阅

## 执行顺序

- [x] 首轮实现两个方法窄变更，更新触及的中文docstring及非显然边界说明
- [x] 首轮新增13个测试方法覆盖七组；静态复核后追加别名版本直接反例
- [x] 主会话补充必要Spec，另澄清整数索引与规范key优先
- [x] 首次新增模块13/13通过，退出码0；真实日志和SHA在外置evidence/regression-attempt-1.*
- [x] Trellis check首轮只读复核发现1项P2：别名key被整数去重遮蔽；未自行运行应用检查
- [x] 静态P2在同一列表方法内修复，补直接反例后仅重跑同一模块，最终14/14通过
- [x] 已核对精确9路径、索引为空、默认资源与原有七工作区/索引/未提交内容保持

## 七组直接回归

- R1：空库登记、重复调用和已有旧默认。seed只创建一次；重复调用记录/payload/hash不变；空库初始默认、已有默认保持各自现行语义
- R2：内置seed同号身份或payload完整性冲突。ValueError含template_id@version，冲突记录和默认指针不被覆盖
- R3：合法manifest元数据变化与已关闭seed。不比较新manifest整体hash；既有payload/snapshot不改；disabled/superseded不复活、不抢默认
- R4：自定义上传及默认模板替换draft。已有draft不误判为bundled冲突、不自动发布、不成为新默认
- R5：历史记录不在managed目录且不在当前manifest。仍列出旧版本；旧DOCX、YAML、render_policy、验证发布字段和默认标识保留自原payload，新旧版本降序且不移动默认
- R6：payload与目录/manifest候选不同或资产丢失。选择record指向的DOCX，而非目录首文件/新seed；原文件缺失时exists=false，不借用其他版本充数
- R7：版本去重、legacy无版本服务及非整数历史key。目录/manifest/record重复只一行；保留既有legacy视图，无法解析的历史key不导致整页失败；列表补回不写版本记录或DB默认

## 实施轮唯一应用检查（已执行，本提交轮不重跑）

以下为实施轮主会话执行的新增模块，准确argv/cwd/env见外置真实记录；当前提交轮不重跑：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_template_seed_history -v
```

仅运行这个模块。成功输入不变时复用；不因Spec、任务记录或收尾再跑。测试结果不扩展为真实MySQL、线上或Word外观验收。

## 停止与保留

不运行旧测试、全仓、lint/typecheck/build或CI，不启动后端/DB，不处理历史维护。超出已审查范围先报告，不自动扩围。

实施轮未授权提交；本提交轮已获用户授权，仅暂存本批9路径并创建一个本地提交。不推送、合并、删分支、运行task.py archive或add_session，不生成额外记账提交。任务保持in_progress、不自动归档。

## 已执行证据与必要重跑原因

首次 `tests.test_template_seed_history`：13/13通过、0.299秒、退出码0，仅一次应用检查。随后静态复核发现上述别名record问题，原成功结果不能证明该新反例；源码/回归将据此变化，因此修复后只重跑同一新增模块。未运行旧测试、lint、类型检查、构建或CI。

## 最终实现与验证

- 最终新增模块14/14通过，退出码0；共运行同一模块2次，测试失败次数0。第二次仅因静态P2修复及直接反例导致输入改变。
- 源码/新回归的成功字节SHA见外置 `evidence/successful-source-inputs.json`，完整执行记录与真实stdout/stderr保留为 `regression-attempt-1.*`、`regression-attempt-2.*`。
- 独立只读增量复核确认P2消除，无剩余确定缺陷；复核代理未执行应用检查。主会话执行记录为最终14/14证据。
- 注释、docstring及新增开发者错误按中文更新。未改生产解析器、默认DOCX/YAML/manifest、DB adapter/schema或前端。
- 实施轮全部改动保持未提交；后续本提交轮已获一笔本地提交授权。不推送、合并、删除分支或自动归档，不运行add_session。

## 实施结束时的保留核对

原有七个工作区、索引与全部已记录未提交文件逐项保持；新增本任务独立worktree，共八个。实施结束时本任务9条改动均未暂存，HEAD为基线df78de9c。默认DOCX、manifest及v1/v2 YAML字节与main基线完全相同。历史维护仍为11个测试与2份文档未提交。

远程仅main及五个归档标签保持原样；仓库配置不变。除本任务新增本地分支外，既有业务引用不变；Codex运行时快照引用单独记录、不人为还原。完整证据位于工作区外evidence/preservation-result.json。本次没有archive/add_session或其他记账提交。

## 本地提交（本轮新增授权）

- 范围：一份源码、一份独立直接回归、一份必要Spec及六份本任务记录，共9个路径；不包含历史测试维护或文档同步。
- 本轮开始时暂存区为空、HEAD为df78de9c，提交钩子无可执行脚本；原有其他七工作区、索引、未提交内容和远程引用已记录保留基线。
- 本轮不再运行测试或配置CI；源码、回归及依赖与最终14/14成功记录相同，Spec与已审阅版本一致。
- 本记录随唯一提交纳入；精确SHA以Git历史及工作区外 `evidence/local-commit-20261101/commit-result.json` 为准，避免回填自身SHA而增加提交。
- 提交后只核对精确路径、单一父提交、当前worktree状态及其他工作区保留情况；不推送、合并、删分支或自动归档。
