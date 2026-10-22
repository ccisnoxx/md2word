# TR-406 独立实现复核：第一轮

日期：2026-10-22。由独立 `critical_reviewer` 只读复核现有 workflow/仓储候选，主会话依据代理最终报告落盘。本轮确认 2 项 P1、3 项 P2；以下锚点属于审查时版本，修订后需独立复审，不能把修复自报当成通过。

## 发现与交错证据

| ID | 级别与位置 | 触发、影响及解除条件 |
|---|---|---|
| R1 | P1，MySQL adapter 原约599/615/792行 | 同事务先普通读 batch，再等待 job 锁，最后普通读全代列表。B 的旧 RR 视图看不到 A 等待期间消耗的最后预算或落库终态，可能超领/晋升。需将 job 定位读移出写事务，事务内 job→batch 当前读，并核对所有入口。 |
| R2 | P1，file/sqlite/MySQL 原约483/637/622行及同类结果入口 | 原子闸门只判断 failed&&!retryable。真实 file 方法的窄内存探针：A running、attempt1/max1、lease已过期，B pending、预算4；共享 reducer 已判 failed/attempts_exhausted，claim(B) 仍成功。需在同 job 边界复用唯一 reducer，补跨 lease 截止时间的领取/结果提交测试；保留合法最后预算在途和合法自身回收。 |
| R3 | P2，service.py 原约425，router.py 原约357 | 鉴权读旧代0后用户 retry 到1，再按0请求 snapshot，可得到 job1+batches0并将响应标1。需按同一锁快照的 job 过滤当前代，补真实换代窗口回归，执行侧旧消息不得误伤新代。 |
| R4 | P2，workflow.py 原约643 | A终败、B仍有资源的retryable failed时，outcome=failed而B行仍retrying。终态停止须优先于retrying，成功叶和split父保持自身身份；终态job无显式terminal记录也须停兄弟。 |
| R5 | P2，workflow.py 原约500/503 | 最终attempt租约到期时行已terminal，但按raw status计算terminal计数仍0；retryable failed后预算耗尽也被误数为retryable。计数须从同一次归约分类得出。 |

R1 的事务机制已核对 [MySQL 8.4 一致性读取说明](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html) 与 [锁定读取说明](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)：RR 的普通读取延续首次一致性读视图，锁定读取使用当前版本。未连接真实 MySQL，不能将文档和 fake SQL 证据写为 InnoDB 并发实测。

## 范围和证据边界

- 已读三件套、授权、窄合同、相关 Spec、CON102/103 摘要及五个目标源文件，并检查主记录锁/backend事务和必要调用者。
- 静态确认 file 主记录和批次共享稳定 job.lock，SQLite 写方法 BEGIN IMMEDIATE，数据库根安装/split使用同连接事务；完整根现态保留、file残缺树失败关闭及旧attempt/lease条件未发现额外确认缺陷。
- 实际执行仅为上述窄内存探针，不运行变化中的大测试、真实 DB 或 Provider。代理未修改任何文件。
- 主会话已把 R1/R2 交给 storage owner，R3 交给 execution owner，R4/R5 交给 workflow owner；修复和新增验收另见各 validation 文件，最终还须复审。

## 被审版本

| 文件 | 开始 SHA-256 | 结束情况 |
|---|---|---|
| repository.py | e6009f147fb72bea8a0ce87715d28af94b4381327fab83e8d937815bd7c7756c | 一致 |
| workflow.py | 67ff5a7147e748613dddfdb4ab51f50c6583208b62194ac844487231a64935bf | 一致 |
| file/document_jobs.py | 2f099b5db5fb94cdc4f1479a3bcb21313e04533005b26bbdb1507e06b5b90602 | 一致 |
| sqlite/document_jobs.py | 3bc1ee3997ea726fd233d2d840b0f9398df5cfd57c86dad675ff1354c861cabc | 一致 |
| mysql/document_jobs.py | d82fb5b2f175fa1b7624ca63826d85fdcae4cdd05951c9dcf5301779fbadf13f | 审查中变为66bca955e775eedba6cebeddbcb2c8dbbc43fed5acf9e661a84727bfe82d8f39，未视为复审通过 |
| file/record_lock.py | 83deadb86b672eabc4f0e7e10f9943aa7dd775f468cef26b39fa227e7ba0c51e | 一致 |
