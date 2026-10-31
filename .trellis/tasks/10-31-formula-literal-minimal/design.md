# 技术设计

## 职责与数据流

保持数学扫描/源视图 → render_formula → 共享有限 parser → FormulaRenderResult → renderer 写入前冻结预期投影 → 最终 DOCX/报告核验的既有链路。main 的 render_to_result 和报告结构不改。

## Parser 的局部扩展

仅在 `_OmmlParser._parse_command` 加入 `\,`/`\_` 和 ln/log/exp/sin/cos/tan 的有限处理，复用 `_math_run` 的 p 样式。标点在字母命令扫描前识别；其他未知转义、命令和结构沿用既有错误路径。

不把函数加入 GREEK_AND_TEXT_COMMANDS 或 STRUCTURAL_TEX_COMMANDS，不改变普通路径/翻译前扫描，也不对所有反斜杠做替换。text wrapper 空格、脚本原子及显式 b/i 不重建或压缩。

## 已认证 OMML 的残留处理

先执行既有 validate_formula_report 与 _formula_ranges。后者校验锚点、范围、mode、输出 hash 与数学对象覆盖；未通过时不能享受任何新例外。

复用该验证结果确定 mode=omml 的 m:t 所有权。质量分析保留实际文字与原 LATEX_RESIDUE_RE，仅对这些节点中合法的字面下划线匹配做窄处理；text_fallback 的现有精确排除保持。

优先采用原残留字符串中的位置/范围信息识别已认证的下划线，必要时扩展现有私有残留 helper 的可选参数。偏移必须与包含段落分隔符、排除 fallback 后的同一字符串一致。相同文字出现在普通 w:t 时不得因值相同而获得豁免；不能通过全局 replace、删字、占位符改写诊断文本或跳过全部 m:t 清零。

原正则允许下划线后带反斜杠，单看匹配起点不足以保证整条匹配都是字面量；例如认证下划线紧邻普通命令时，必须保留整条原始诊断。因此只有不含反斜杠的纯字面下划线匹配才获例外。既有反斜杠命令、美元定界及 caret 残留继续检查。原始反斜杠后仍带 `\_` 的残留不能被当作已转换字面量。允许用同等窄、可读的局部机制落实上述合同，不增加公共 schema、配置或通用框架。

## 兼容与历史

保持 formula-render/v1 与 formula-output/v1、source hash/位置和 anchors、四种 reason 与逐式 expected_output_sha256。实际字节验证仍对字符、节点和数学样式生效。无报告路径保持原逻辑；缺失/损坏报告不回退。

旧产物若原来按 text_fallback 保存，继续按原报告及字节核验，不能因当前 parser 支持扩展而重新渲染或升级 mode。历史请求 owner、receipt、持久化和发布路径均不修改。

## 验证与职责

独立回归自建最小 IR/DOCX/报告夹具，不导入旧测试辅助类。新语法正向路径必须使用真实共享 parser 和正式 renderer。历史兼容夹具须清楚表达旧降级产物，不能用 mock 遮蔽新语法实际路径。

实现代理仅写三份产品/回归文件；主代理维护本任务与必要 Spec。独立只读复核复用已有新增回归结果，不再运行其他检查。

基线 worktree：`/Users/sc/.codex/worktrees/formula-literal-minimal-20261031-g0l1d94p/md2word`；分支 `codex/formula-literal-minimal-20261031`。本轮按用户新增授权将本批保存为一个本地提交；源码和独立回归内容保持已验证版本，不再运行应用检查，不推送、合并或删除分支。
