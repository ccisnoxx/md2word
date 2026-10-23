# RND-502 本轮独立实际实现复审

日期：2026-10-23。用户要求全新 architect 对照批准 v2 只读审查实际实现与 diff，主会话核实后修复并定向验证，仍停 review；不提交、不 push、不归档。

## 基线和分派

- 实际子任务未重新 start，仍准确指向当前子任务；manifest=review，Trellis=in_progress；BAS-001仍done。
- HEAD=c56e12832ff30212cc067d0909430cf5f091f79b，branch=md2word/RND-502；13业务文件与上轮最终源快照4af77e68e8d0d358a237f42f6c76c4508cababec6ac83a2294641ad06d5f42ec完全一致。
- 本轮dirty/暂存树/文件哈希快照：`/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd502-post-implementation-review-mzrwimtc`。全部原改动保留。
- 按用户要求新建 `/root/rnd502_new_architect_actual_review`，role=architect、fork_turns=none；其仅做角色适配判断，返回ROLE_MISMATCH，声明未读仓库/执行探针，不能算作有效实现审查。
- 该role只允许未来架构决策，要求实际高风险diff交critical_reviewer。主会话已向用户明确说明调整，重新新建 `/root/rnd502_new_independent_actual_review`，role=critical_reviewer、fork_turns=none，独立只读，范围/授权保持，避免用空审查结果宣告通过。

## 发现、主会话核实与验证

有效实际实现审查已收敛。共确认 1P1/2P2，均已由主会话独立复现、修复并通过 reviewer 再次复验；当前无剩余确认可行动缺陷。

### R1：left/right 空数学 run 的保存前后投影不一致

- Reviewer 实证：`formula.py` 的 `m:t` 投影直接用 node.text，而 left/right 生成空 math run。DOM 前为空字符串，DOCX 保存后 ElementTree 读为 None，导致合法支持公式被新报告校验拒绝。
- 主会话独立纯内存复现：`\frac{1}{2}` render_to_result→evidence 通过；`\left(\frac{1}{2}\right)` 在同链路稳定 ValueError（DOCX公式实际输出与预期绑定不匹配）。正式线上映射 quality_checking/render_failed，本地不写最终件。
- 现有 trellis-check 已修复，写权仅 formula.py 与 test_formula_rendering.py：只把空 m:t 的空字符串规范为 None，不合并/忽略节点，非空文字和语义属性仍严格绑定。旧成功公式 v1 哈希及无报告 legacy 路径保持。
- 34 项 formula tests 通过（0.484s），包含保存后 block/inline/table 正例，以及空化数字、改数字、追加空 run 拒绝；日志 tests/tmp/rnd502/post-review-empty-math-tests.log。独立 reviewer 已再次纯内存保存后复验三入口 build/ensure 通过。

### R2：上下标参数压缩丢失显式数学样式

- Reviewer 和主会话分别完成真实 render_to_result→build_renderer_evidence→ensure：独立 \mathit{out}/\mathbf{n} 的 m:sty 为 i/b，但进入 x_{\mathit{out}}、x^{\mathbf{n}}、x_{\boldsymbol{n}} 后变 p，报告仍认定 OMML 成功。
- 根因是 _compact_plain_script_argument 仅检查 m:r 与字母值，重新 _math_run(combined) 丢弃显式 rPr；违反批准 v2 的数学样式保真，属于已有支持命令组合。
- 已交同一 checker 在原节点语义 owner 最小修复，保留未显式样式的 datasheet 压缩及 text wrapper 空白。要求保存后上下标 i/b 精确断言；不修改 Codec、翻译、receipt/generation 或公共接口。

### R3：不可见 delimiter 句点被错误输出为可见符号

- 在 R1 修复后的候选上，reviewer 与主会话独立验证 \left.\frac{1}{2}\right|_{0}^{1}：最终 m:t 含真实句点，mode=omml，带正常正文时 quality_flags=[] 且 ensure 通过。
- 语义依据：[Microsoft 官方 LaTeX delimiter 文档](https://learn.microsoft.com/en-us/office/math/latex) 将 \left. 的句点定义为 invisible。当前 left/right 丢命令却保留句点，改变公式可见内容。
- 最小范围为 left/right 后 dot（含允许空白）整体 unsupported_structure literal 降级，原式逐字保留、可见提示/flag；既有可见括号保留支持。已交 checker 补 left./right. 与三入口保存后测试，不引入 delimiter 引擎。

### 未确认为问题的观察

双重 script、空参数等未获得足够合同缺陷证据，不作为发布阻断或扩围实现依据。reviewer 已核验翻译 eq 子树/索引、跨 DOM/semantic 数学及裸命令调用前保护、三恢复入口、选中摘要与最终锚点属性，本轮暂未发现其它确认失效路径；最终冻结候选的 R2/R3 已修复并完成独立复验。

## 冻结候选与独立复验结论

- R1 原始严重度 P1；R2/R3 为 P2。最终位置 formula.py:374（空数学文本）、:648（脚本样式）、:575（不可见 delimiter）。修复仅涉及 formula.py 和 test_formula_rendering.py；另外更新当前任务证据及 Word Spec/必要摘录。
- Checker 修复后三项共 36 个 formula unittest 全过，0.726s；见 tests/tmp/rnd502/post-review-style-delimiter-tests.log。
- 独立 reviewer 对最终 formula.py SHA-256=4c66b22418a2f0205242db5fb5141f9aad618aca9b99127f39db051d24ba523c 复验：圆/方括号 × 三入口 6 例；三种显式脚本样式 × 三入口 9 例；默认压缩 2 例；四种 dot delimiter × 三入口 12 例；数字删除/改值/额外空run/style篡改/漏提示/截断literal 6负例全部拒绝。原成功 frac 的 v1 哈希 d21e8504c07b4c5aad1233156f3b558832f06b330204217bd4806ad8daa5a038 保持。
- 另有 7 个纯内存主动改值 fake 翻译场景与 4 组结果 owner 场景独立通过。eq 原值/索引保持；未覆盖数学调用前拒绝；first-valid winner、四质量状态、清空新代摘要及 receipt 保持。未将纯 owner 测试冒称真实锁竞争。
- 主会话独立修后探针见 tests/tmp/rnd502/post-review-main-probes.json；真实保存后括号 OMML/脚本 i,b/整式 literal+warning 均确认。
- Reviewer 最终结论：当前冻结候选没有剩余确认可行动缺陷，三项代码审查阻断解除。architect 未执行审查的角色调整事实保留，不能将本轮称为 architect 完成的有效代码审查。

## 主会话最终验证

业务源快照：15eeffed1bfcc1fdbe1dcd771dcfb1acc27fb8c0d13fe200e5c953f9e7932a7f；13 文件哈希和 HEAD 见 tests/tmp/rnd502/post-review-code-snapshot.json（与原快照沿用紧凑、排序 JSON 哈希）。测试期间及最终保护检查均核对源文件未漂移。

| 门禁 | 实际结果 | 证据 |
|---|---|---|
| 15 模块定向 | 311 项，32.304s，exit 0 | tests/tmp/rnd502/post-review-final-targeted.log |
| release | 202 项，5.625s，exit 0；OpenAPI current | tests/tmp/rnd502/post-review-final-release.log |
| 组件 | 1/1 | tests/tmp/rnd502/post-review-component/report.json |
| direct phase2-core | 5/5、0 P0 issue；原 P1/P2 backlog 仍使 phase3 未 ready | tests/tmp/rnd502/post-review-matrix/report.json |
| RS2G04 正式报告审计 | 143 次=141 OMML+2 invalid_syntax 保真降级；未登记残留 0 | tests/tmp/rnd502/post-review-local-report-audit.json |
| context | implement/check 各 8 条，全部通过 | task.py validate 当前准确子任务 |
| diff | git diff --check 通过 | 主会话最终执行 |

311 与 202 有重叠，不相加为唯一测试数。原 306 项等日志按前一版本证据保留，本表替代其当前版本结论。旧矩阵不带报告重扫仍显示两次受控 LaTeX 降级，未修改扫描器来消告警；正式报告审计保留原文和 warning。RS2G04 产物与私有报告保留在 tests/tmp/rnd502/post-review-report-audit/。

没有新增 API、DB、迁移、权限、翻译 Token、receipt/generation、外部调用或发布规则变化。仍不宣告真 Word 视觉、线上 Golden（缺认证/API）、真实 InnoDB/S3/部署文件系统通过。回滚按既有任务约定保留不可变件、报告与审计，兼容执行器/排空在途规则不变。

manifest 维持 review，Trellis 维持 in_progress，当前 session 子任务指针不变；未执行 start、commit、push、archive 或 add_session。新增/修改代码注释、测试说明和开发者可见文本已按触及范围使用中文。
