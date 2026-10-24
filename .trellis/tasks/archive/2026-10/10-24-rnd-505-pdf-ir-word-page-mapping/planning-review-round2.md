# 全新 architect 独立审查：修订2

日期：2026-10-24。用户明确要求安排一位全新architect，核查G0、书签/报告共存、映射降级及兼容回滚。审查者：rnd505_fresh_architect_review（Ohm），fork_turns=none；与首轮审查者不同。主会话保留上一轮planning-review.md作为历史记录。

## 首轮发现及主会话核实

### P1：通用锚点与旧trace认证不能仅靠既有字段兼容

原v1 design第30/32/34行计划优先通用bookmark_name，并把冲突标为name_conflict。两个实际反例：图片marker在paragraph内，而drawing内容target的后代投影找不到它；模板预占expected名且恰在target内部时，仅命名空间或首名无法证明本次生成。

主会话独立读取69906a5e源码确认：

- app/services/renderer/block_evidence.py:19、50–63：封闭Reason和v1 record无冲突结果字段。
- 同文件240、344–353、368–369：仅投影target后代bookmark，并以去重首名赋值。
- app/services/renderer/evidence.py:184–219、282–284：严格内容targets数量/类型/role，及首名等式；追加伪caption/父paragraph/bookmark目标或重定义首名会改变已验收认证。
- 当前根app/domains/document_jobs/execution.py:3307：事件黑名单只剔除现有报告，新私有键不能假定自动脱敏。

修订2保留原v1全语义，新增独立可选block-anchor-evidence/v1：由同次collector成功创建事实与真实对象引用冻结，绑定IR/plan/最终DOCX，校验marker配对及原target关系；图片paragraph中包围真实drawing run，不扩大内容owner。模板同名不写成功entry。主件候选登记前随原metadata保存，receipt后不回填；preview只消费认证证明，缺证明统一anchor_missing，name_conflict仅当次diagnostic。

新证明缺失/坏/未知只令锚点不可用，原DOCX/hash/IR/plan/公式/图片认证仍失败关闭。实施文件清单新增block_anchors.py与execution.py精确接点；三恢复入口、公开出口脱敏、B1字段保留及篡改/误归属负例同步进入验收。B1必须在新写入前证明不会丢失、重算或泄露证明。

### P2：完整trace无正文候选时entries形状矛盾

原v1 design第79行同一分支既要求entries=[]又保留已认证entry；与PRD AC2保存无输出块来源/owner/disposition冲突。主会话对照该段确认。

修订2区分：成功preview+完整有界trace但没有正文候选时保留全部entries，unavailable/no_target，每项location不可用、fallback=null，total为已证明数量；无trace/无成功preview或超预算采用小型空entries。PRD AC2、design §4.1/§5.7和implement T1一致。

## 同一全新审查者复核

审查者只读重读实际v2三件套与同步研究材料，确认P1、P2在规划层均闭合，未发现修订引入新的实质风险。独立证明的登记/恢复/脱敏和B1新写入前门已形成明确计划。

G0仍为not_satisfied；规划审核通过不等于统一基线、真实书签/报告兼容、B1交叉恢复或部署证据通过。三件套v2等待人工审核，尚未授权实施。审查者未修改文件、未运行业务测试、未集成/start/提交/push。主会话本轮只改规划材料和RND-505登记。
