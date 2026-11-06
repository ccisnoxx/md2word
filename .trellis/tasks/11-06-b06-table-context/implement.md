# 实施与验证

用户已确认本计划并授权直接实施。

1. 在翻译准备 owner 附近实现 TableContextBuilder，复用现有 grid 和 Codec；在 models/Provider 添加输入专用上下文。
2. 共享请求准备和预算逻辑，保持现有 ID、公式保护、输出校验及 evidence；Settings 开关通过 app/main.py 必要构造参数注入。
3. 在对应定向测试覆盖 AC-1 至 AC-5：默认旧 payload 字节对比、开启上下文、合并表头、多级表头、eq、Token 回写、预算分批/超限、来源计数。
4. 使用 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_integrity tests.test_formula_translation_boundary 及新增定向模块；只用 fake，不执行 discover/聚合/在线验证。历史无关失败单列。
5. trellis-check 审查候选 diff 和最小必要补测；git diff --check。新合同记录于本任务设计（Spec 不在允许写入范围）。禁止 archive/add_session/commit/push。

完成指本地实现与定向结构验证，不代表人工语义或发布验收。报告 AC-6 的未验证质量与人工样本类型；中文维护触及的注释/docstring/开发输出。

## 已执行验证

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.tmp/b06-tests" /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_integrity tests.test_formula_translation_boundary tests.test_translation_table_context
git diff --check
```

第一条 59 个测试通过（新增上下文模块 12 项）；第二条通过。首轮新增测试预期未处理已有 strip 行为，修正该预期后通过；无已发现的无关历史测试失败，仅既有 Starlette 弃用警告。

AC-1 至 AC-5 的定向证据位于 tests/test_translation_table_context.py，含真实 Settings→runtime 注入、固定旧 prompt 字节对比、合并/多级表头与行标题区分、eq/caption 索引、正文 ledger/evidence 等值及预算负例。原 Codec、Validator、提取/回填 owner 均未修改。

AC-6：语义质量改善未验证；人工对照建议覆盖 Typical/Reserved/Output 等短词与缩写、合并表头、多级表头、正文和公式混合格，并记录改善/不变/退化。fake 仅证明结构与拒绝行为；真实 Provider、MinerU、在线门禁和聚合检查未运行。

独立检查发现并修复两项上下文边界问题：br/块级换行被拼接丢失，以及 scope 枚举未忽略大小写。新增两项回归后执行：

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.tmp/b06-tests" /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_translation_table_context
```

14 项通过；其余三个模块的 47 项结果复用，未重复执行，最终 git diff --check 通过。累计覆盖 61 个不同测试。独立检查已增量核对两项修复，未发现其他确切可行动的残留缺陷；另核对正式 Worker 的计划与请求都使用同一 Profile 字符限额。未发现已配置的后端 lint/typecheck 命令，未执行、不标为通过。以上是本地实现与检查报告，不代表 Claude 或用户人工验收。

新增及实质改动的注释、docstring 和错误消息均为中文。保持 Trellis in_progress 待人工验收，不 archive/add_session，不修改 manifest，不 commit/push。
