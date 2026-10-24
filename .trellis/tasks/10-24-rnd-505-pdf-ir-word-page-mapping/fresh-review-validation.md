# RND-505 全新复审后的最终验证

2026-10-24。仅在隔离工作树执行。本轮主源码修复 1 个文件，新增有意义回归涉及 3 个测试文件，并同步页映射合同与 Spec；批准的 v2 三件套 hash 全部保持。未再执行 task.py start，不提交、push、归档、合回或安装依赖。

## 最终源码验证

| 检查 | 结果 | 原始证据 |
|---|---|---|
| 修复前反例 | 代表字段 6 个预期失败；随后 disposition 3 个预期失败 | post-review-reproduction.log、post-review-disposition-reproduction.log |
| 补丁后定向 | 56 项通过，21.741s；实际渲染/持久认证/mapper、应用与恢复负例，合法混合列表对照 | post-review-targeted.log、post-review-fix.md |
| B1 三恢复入口 | 1 test / 30 subcase，8.068s，OK；file/SQLite × legacy/explicit/receipt × 五种 proof/trace 状态 | fresh-review-b1-three-entry-tests.log |
| B1 独立进程 | 实际加载 B1 execution/preview/block_anchors，核路径/hash；file/SQLite 均主件及预览 succeeded，无新 proof/mapping，旧 manifest reader 通过 | fresh-review-b1-application-probe.log、b1-application-results.json |
| B1 源码一致性 | 305 个 app 文件全部匹配指纹；相对候选仅 block_anchors.py、preview.py 两处停写差量，evidence.py 含最终认证修复 | b1-source-fingerprints.json、post-implementation-review.md |
| release | 203 项通过，7.367s；OpenAPI current、changed=false，frontend contract/mock 检查通过 | fresh-review-release.log |
| component | 1/1 成功 | fresh-review-component.log、tests/tmp/rnd505-fresh-review-component |
| direct phase2-core | 5/5、P0=0、automated_matrix_ok=true；phase3_entry_ready=false | fresh-review-direct.log、tests/tmp/rnd505-fresh-review-direct |
| 独立复验 | 全新 critical reviewer 核实两类篡改均拒绝；合法/空内容行为保留，未发现剩余可行动实质缺陷 | post-implementation-review.md |
| 静态与上下文 | 4 个修改 Python 文件 AST 通过，git diff --check 通过；task validate implement 9/check 10，无警告 | post-review-source-check.json、fresh-review-task-validate.log |

lint/type-check 为 N/A：现有环境未配置或安装 ruff/flake8/mypy/pyright；未安装依赖，AST 不冒充类型检查。以上结果不将重叠测试数量相加。

## 执行方式与证据连续性

所有候选检查使用已有 `.venv`，B1 独立进程的 cwd/PYTHONPATH 指向实际隔离 B1。`build_b1_snapshot.py` 从最终候选重建，停用生成策略及 manifest mapping 写入，保留全部 reader。三入口测试动态加载真实 B1 execution；相同依赖 reader 用全 app 指纹对账。独立进程另证明完整模块实际来自 B1，不用 mock 旗标代替真实源码。

本轮重建前的 B1 指纹/应用结果、candidate 指纹、原根保护结果及旧 evidence.py 副本保存在 `pre-fresh-review-evidence/`，原日志保留。最新 `candidate-files.json` 记录最终候选维护文件，`fresh-review-protection.json` 记录本轮原根保护与修改范围。

集中 339 项历史日志仍为 5 failure、0 error，已逐项与 G0/融合前基线核对；详 `implementation-validation.md`。本轮不重跑未变的完整集合；最终 56 项、独立反例、重建 B1 及项目回归覆盖新增修复，未将旧 339 项标为补丁后全部通过。此前 renderer B0/B1 的兼容测试结论保留，生成器与图片兼容代码本轮未变。

## 保护、权限与未验门

原根 `/Users/sc/PycharmProjects/md2word` 的 1118 个受保护路径、Git status 和暂存条目与本轮前快照相同；候选暂存条目也未变。Git stage 快照使用 `git ls-files --stage -z`，不把缓存更新误判为暂存内容变更。manifest 仍仅 RND-505 与原根不同，其余任务保持。task.json 修正历史 planning/start/G0 已完成的过时元数据，实际仍为 in_progress / review，不标 done。

新增注释、docstring、测试说明与文档使用中文；机器字段和错误码保持。修复未新增 API/DB/迁移、状态、权限、AI/外部调用或配置开关；坏可选 trace 只影响导航，原内容、存储、安全及发布校验不放宽。

真实 Word/WPS、Golden、生产沙箱/字体、真实 InnoDB/部署 FS-S3 与生产大文档容量仍未验；保持原生产 disabled。本轮未覆盖、未代签人工验收或部署门。最终停 review 等待用户验收。
