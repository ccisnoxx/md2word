# TR-402 独立合同复核与修复

日期：2026-10-21。范围仅限新增 Codec、定向测试和对应文档；其他任务的 dirty 不作为本任务候选。

## 首轮确认问题

独立只读 critical_reviewer 检查旧候选模块 SHA-256 98ed4f77dc60d111e6faec9e4a5ca85edd7bd29eb938da5ab808b08be02082d4，确认一个 P1：

~~~text
{{PH_ https://example.test/a
{{MD2W_PT_v1_0_ TA = 25°C
~~~

残缺保留语法匹配会包含后续 https/TA，与高优先级 URL/公式部分重叠；旧选取逻辑将整个低优先级候选丢弃，裸前缀遗留在编码结果中，decode 因 malformed 拒绝自身输出。这违反 AC3/AC4，而不是生产接线问题。

主代理在实现代理完成后接管这两个文件的范围内修复：

- 先加入 test_partial_reserved_prefix_is_not_left_bare_by_higher_priority_structures；单独运行 1 个测试，4 个子例按预期报 protected_token_malformed，复现缺口。
- 保留 URL/公式整体优先，只有 literal_placeholder 候选发生部分重叠时，继续代理其中未被覆盖的连续片段；不提升全局优先级，不让其他低优先级类别抢占。
- 新测试交叉覆盖两种残缺前缀与 URL、赋值公式、定界公式；原有 URL 内部字面量、普通外括号、非递归恢复测试保留。
- 修复后运行完整 tests.test_protected_tokens：24 tests / OK。

首次复核还追踪了命名空间、逐次编号、所属 item/次数、整批验证、非递归恢复和隐私合同，未确认第二项问题。只执行针对性内联探针，不落盘、不联网；复核前后工作区文件集合和内容 SHA-256 一致，未观察到仓库写入。

## 最终 fresh 复核

采用另一个 fresh、隔离上下文的 critical_reviewer，对父代理修复后的完整候选复核：

- 模块 SHA-256：fa3f254c1e453413c2ba6a8f0094b670b77a92c05df50351d4d1872ad2ee31c7。
- 测试 SHA-256：a1a909bb504bc262af02346622b3bc842ae799dffb9940d0b2b8df401f92ad31。
- 结论：上述部分重叠阻断已关闭，未确认新的 P1/P2 合同缺陷，没有需要继续阻断当前候选的具体反例。
- 复核确认：高优先级结构不被拆开；普通外括号/URL 平衡括号保持；全输入前缀扫描和出现编号确定性；全部验证后才构造结果；一次原文切片恢复；不扩宽自然语言或保留语法识别规则。
- 复用主代理 24 项通过证据，没有重复运行测试、执行探针或联网；复核前后工作区内容哈希和文件集合一致，未观察到仓库写入。

复核范围限于已定义的有限静态语法和纯内存合同，不证明真实模型、四方向正式实译或生产集成。P1 preflight 的认证阻断和 translation-core 缺失仍如实保留。

## 审计

Bundle：20261021T041920Z-tr-402-protectedtokencodec-implementation-de863c8c。

实施与两轮独立复核的 WorkPlan、实际派发、执行、summary 和 SUBAGENT_EXECUTION_DIGEST 已生成；audit-finalize / audit-verify 均 passed，Bundle closed，无异常或活跃 Worker。审计中的任务责任验收不代表用户已人工验收 TR-402。
