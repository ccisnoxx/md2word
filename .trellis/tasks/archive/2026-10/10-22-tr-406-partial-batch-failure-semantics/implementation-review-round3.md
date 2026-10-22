# TR-406 第三轮独立复审

日期：2026-10-22。只读 reviewer：`/root/storage_audit`。本轮检查固定候选，没有修改仓库或进行真实外调。

## 结论与修复入口

本轮确认 1 项 P1、2 项 P2，修复前候选不能停人工验收。已将三项交 `quality_check` 在 execution 和对应回归测试内最小修复；最终闭合结论另见最终复审报告。

1. **P1，execution.py:1596 / :1309**：预算预检失败后，未领取、未递增 attempt 的分支 `return failed`，上层将非空记录当作获得 lease。真实本地双 item fixture 的编码长度为49/26，先按每批一项安装，再收紧全局 max chars 为26，执行短根时复现 job.failed 但 Provider=1、attempt=0、lease=None。必须保留条件写及 finalizer 副作用后返回 None，并以该短根对照补测试。
2. **P2，execution.py:1437**：success CAS 的通用 ValueError 包装截获其子类 TranslationBatchTreeInvalidError，复现应为 translation_failed 的树错误变成 oss_failed。必须先透传专用树异常，保留原 generation 的错误 owner。
3. **P2，execution.py:1408**：Artifact 文件 metadata 注册的 SQLite/PyMySQL 驱动异常没有进入既有存储失败收口。真实 fixture 在 translation_batch_result metadata create 注入 sqlite3.OperationalError 后，异常直出且 job/batch 仍 running，Provider=1、audit=1，租约恢复可能再次调用。必须与 success CAS 使用一致的驱动异常识别，未知异常保持可见，并测试重放零额外调用。

## 已闭合部分与实际验证

- R1 MySQL 当前读/锁序、R2 shared reducer 停止闸门及删除原因字符串特例、R3 同快照 API、R4/R5 行分类与计数、R6 旧代树异常、R8/AC13 真实终态窗口、R9 执行侧同 job 快照均有闭合证据。
- 普通 claim 返回 None 已修复；第1项是新增预算分支的同类回归。Artifact OSError、success CAS OSError/SQLite 的 R10 回归通过；第3项是 metadata 写入残留边界。
- 独立执行三模块：workflow 11、repository 11、failure semantics 17，共39项，5.375秒，通过。另独立运行上述三个窄探针复现缺陷；没有重复前端、release 或数据库整模块。
- 关键源文件开始/结束哈希一致。execution SHA-256：`d240b1feab5d865f1e252e19a318a766f5c7e28c40bda5b12257a6205c0d49e2`；workflow、repository、三 adapter、service/router/schemas/result-state/record-lock/backend 均未在复审期间变更。

真实 MySQL/InnoDB、部署文件系统锁、真实 Provider/S3 和 Word 人工证据保持未验。本轮未提交、push 或改变生产状态。
