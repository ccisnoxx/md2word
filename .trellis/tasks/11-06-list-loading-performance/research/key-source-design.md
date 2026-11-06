# 设计

现有规范化 owner 保持：list_query.py 的完整语义投影及 list_query_facts.py 的 equality_key 不改变。新增存储投影 helper 从最终序列化 payload 构造完整事实，再拆出 keys，返回有序 SQL 值。

job 新列 list_descriptor_key/list_receipt_key/list_table_snapshot_key；file 新列 review_descriptor_key/review_receipt_key。SQLite TEXT NULL，MySQL LONGTEXT NULL；NULL 表示未回填，合法不适用值为非 NULL 空串。小 JSON 版本分别升为 3/2，保留 comparable 等小字段。helper 接口：document_job_list_storage_from_raw(payload) 返回 (json_text, descriptor, receipt, table_snapshot)；document_file_review_storage_from_raw(payload) 返回 (json_text, descriptor, receipt)。不新增哈希或索引。file 后端不持久化派生查询事实，继续从权威记录读取并纳入语义对照。

SQL shape 同步检查新版本及文本列非 NULL；key 比较直接读取列，MySQL CAST AS BINARY、SQLite COLLATE BINARY，其他 JSON 路径与 assert_ready 调用位置不变。缺列/NULL/旧版本均 DocumentJobListProjectionUnavailable（列表原 503 合同），不回退读取大 JSON，避免迁移未完成被误当无数据。旧版本读取新版投影也会拒绝，不支持混部。

所有 create/_write_job/_write_file/状态回填/正式复核导入、现有列表回填入口同行维护全部派生列。缺稳定时间沿原合同将整组派生事实设 NULL。现有迁移实现升级为当前布局，新独立 key 迁移入口复用它，避免旧受支持入口写回旧布局。回填只改变双表派生列，不改 payload/时间/事件；DDL 按现有 INFORMATION_SCHEMA/PRAGMA 逐列检查，DDL 可已提交，按实际列续跑；批次事务提交后才推进游标，verify 全量同一只读快照。

## 生产前置与执行（本轮禁止执行，必须单独授权）

1. 冻结代码及实例/库身份，检查 B08 是否已实施。当前无版本账本，使用现有显式 schema 维护；未来 B08 基线必须纳入新增列，不在本任务引入账本或 DROP。
2. 停止所有 API/Worker/回调/定时及脚本写者，排空事务；不使用混部兼容窗口。取得全库和对象配置必要备份，隔离恢复验证、记录恢复点和责任人。
3. 保持停写，用独立迁移脚本 dry-run 检查两表 payload/原时间稳定性，apply 逐列添加并按 files→jobs 分批回填，保留已提交游标；中断后从报告游标续跑或空游标幂等重跑。不得把 DDL 当可事务回滚。
4. 空游标 verify 全量两表；比较 payload/时间/其他表（特别 job_events）完整字节/行数、派生列版本、JSON 体积及固定 as_of 列表结果。差异或失败不得启动消费者。
5. 仅验证成功后启动统一新版 API/Worker；运行新写者后 JSON 和列同行更新。仅加列未回填时，新版列表/表格 guard 拒绝，Worker 的写入可重建所触及行，但不能代替全量迁移；详情原 payload 读取不变。已回填时新版正常，旧版不兼容。
6. 回退保持停写：新增列可保留，不 DROP；仅代码回退不足以恢复旧列表。使用冻结旧版回填工具从权威 payload 重建旧版本大 JSON、旧版全量 verify 后才启动旧进程；或者另行授权恢复同一备份点。旧 writer 一旦恢复，新列整体视为陈旧，再升级须空游标全量重建。数据覆盖恢复另行授权。

并行 list-ready-once 可能与 document_job_list_query.py 的 shape/assert_ready 邻近行冲突；合并须保留拆列 shape、新版本和原请求调用时机，本任务不实现缓存。

## 独立脚本命令与报告解读

仅在未来获批窗口使用下列命令形状；本轮未对生产执行。入口不读取 `.env`，MySQL 必须由操作人显式提供 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`（不在命令、日志或文档填真实凭据）。先独立核对实例/库身份与授权窗口，脚本不提供服务器 UUID 绑定，不代替操作人的目标核对。

```sh
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100
# 下一批：两个游标均使用上次已成功提交的 last_successful_*；未提交的 last_scanned_* 不可使用。
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100 --after-file-id '<已提交文件游标>' --after-job-id '<已提交任务游标>'
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --verify --batch-size 100
```

SQLite 使用 `--backend database --database-path <明确路径>`；只读前需停写并完成 WAL/journal checkpoint。dry-run/apply 每表至多一批，dry-run 的退出码0不表示全量就绪；files 未扫描完时 jobs 保持 pending。apply 的 mismatches 是本批修正前差异，committed_rows 是成功处理行数（包括已一致行），不等于UPDATE数量。只有空游标 verify 的 exit_code=0、all_ready=true 表示全量一致。DDL可能在失败前已经提交，schema_added 与实际列共同判断恢复，不执行 DROP。脚本无并发执行者协调机制，停写窗口仅允许一个迁移进程；旧写者或第二迁移进程进入时停止切换并重新核对。

rollback 的“旧版工具”必须来自冻结升级前版本，不可调用本候选的旧文件名入口（它已升级到新布局）。保留权威payload允许重建旧JSON，不意味着可以自动覆盖恢复全库；恢复动作另行授权。
