# RND-505 全新独立实际实现复审

2026-10-24。用户在已有实施 review 基础上明确要求全新 critical_reviewer 独立只读复审；本轮代理 `rnd505_fresh_actual_review`（Rawls）以空历史 `fork_turns=none` 启动，不参与实现或修复，不写工作树。主会话与独立 checker 核实修复后，由同一 reviewer 再次只读复验。当前候选仍停 review，等待人工验收。

工作树：`/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`，分支 `codex/rnd505-v2-implementation`，HEAD `8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf`。本结论针对 G0 之后未提交的 RND-505 实际差量；不代表部署或人工验收。

## 最终结论

本轮发现的 **1 项 P2 已关闭，包含代表字段错绑和 disposition 篡改两类变体；最终候选未发现新的可行动实质缺陷**。原有实施复核记录 `implementation-review.md` 保留，本记录是后续全新独立复审。

## 核实、修复与独立复验

最初仅把真实 renderer 的归并记录 `representative_block_id` 改为其他正文，持久 trace 仍通过认证，mapper 可跳到该正文书签及估计页。随后确认同一认证边界还允许把完全归并块伪装为 rendered，或把含独立正文的 mixed list 伪装为 coalesced，并同步 counts；两者分别导致归并定位丢失或独立正文定位被错误替代。

修复在共享认证 owner `app/services/renderer/evidence.py:377`、`:391`：记录代表须等于已认证策略按 item 顺序的最后归并代表；无归并策略须为空。非空 native_text 的 disposition 须与已对账的实际自有 target 一致。保留原 TOC target→policy→实际 owner 校验，空策略继续使用既有空列表规则。mapper 不增加第二套认证。

最终 evidence.py SHA-256：`9c4a9591d86be69744a1072cb564b884c3f37330d0ec310477d19d674ab09e24`。前红、补丁及新增测试见 `post-review-fix.md`、`post-review-reproduction.log`、`post-review-disposition-reproduction.log`、`post-review-source-check.json`。

reviewer 独立内存复验确认：代表被换为其他正文、空值、未知块，或给无归并正文添加代表，均拒绝；两种 disposition/counters 篡改均拒绝。坏持久可选 trace 只令导航不可用，原 aggregate 和内容认证保持；同次渲染的错误仍失败关闭。正常 TOC、mixed list、同块自归并、空 list、空段落、空标题及有效公式保持。真正空公式仍按原合同拒绝，不宣称其通过。

## 四个重点领域

| 领域 | 独立结论 |
|---|---|
| 书签与原报告共存 | 通用书签依赖同次独立创建证明；RND-501 strict v1 首名与 targets 保持。最终保存后冻结 locator，公式、图片 cell/run 原认证保留。 |
| 映射及降级 | typed spans/provenance、固定 IR 稳定 ID、主件和 generation/run/attempt/profile/PDF 绑定、确定性低置信推断、no_target 与预算降级已核查；本轮归并归属缺口关闭。 |
| 历史恢复与状态 | 沿用原 CAS、文件权限及当前引用规则；三恢复入口保留原 metadata、主件和内容认证，不重新渲染、不伪造 runtime ownership。坏导航不改变质量、复核、交付、下载或 available actions。 |
| B1 回滚 | 最终源码重建 B1 的 305 个 app 文件与指纹全部一致；相对候选仅停新 marker 与 mapping 两处 writer 差异。保留兼容 reader、原证明和历史 Artifact。B0 直接退回仍不允许。 |

## 验证证据与限制

reviewer 直接读取最终原始日志：定向 56 项通过；B1 三入口 1 个测试、30 个子场景通过；B1 独立进程 file/SQLite 主件与预览成功、无新证明和 mapping、旧 manifest 可读；release 203 项通过且 OpenAPI current / changed=false；component 1/1、direct 5/5、P0=0。这些套件由主会话/checker 执行，reviewer 核对；reviewer 另行执行反例，没有声称重跑全套。详见 `fresh-review-validation.md`。

此前集中 339 项中的 5 次已确认基线 failure 保留原归因，未改称全绿，本轮不机械重跑全 339 项。真实 Word/WPS 视觉、Golden、生产预览沙箱与字体、真实 InnoDB、部署 FS/S3、生产容量仍未验；direct 的 phase3_entry_ready 仍 false。保持生产预览 disabled；本结论不替代这些环境门、人工验收或部署验证。
