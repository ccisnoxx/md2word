# 窗口辅助脚本独立复核

范围：仅 `release_ops/window_helpers.py`、`test_window_helpers.py` 及case实际调用参数。初审源码SHA-256为 `e49d73435624c486f9261b6d706f203e6f5a84d69c0848d0ad76fdc305ac0eb3`，与派发身份一致；初版9项离线通过为主会话提供的执行证据。本复核只读，不修改已冻结6文件，不执行SSH、数据库、容器或产品测试。窗口真实恢复结果由主会话另行记录。

## Findings (fixed)

- **P1，目录分配大小导致恢复误报，已修复。** 初审 `window_helpers.py:66,117` 保存全部条目的 `st_size`，随后整条字典相等比较，导致目录也必须保持同一大小。目录大小属于文件系统目录项存储/分配布局，同一树恢复到新卷不保证相同；tar也不以该值重建目录。已立即通知主会话，由原实施者完成修复：原manifest及其摘要继续保留真实目录size，只在双方条目均为directory时从相等比较排除size；文件size、类型、目录mode/uid/gid/mtime、ACL/xattr、链接及全部子条目仍严格。已静态复核最终 `compare_filesystems` 和新增回归，没有修改输入manifest，也没有放松普通文件大小。
- 最终已复核源码SHA-256：`window_helpers.py` 为 `d16413a00d4f824adc53993060c964228cfa318f497e1791cc6c423812acee94`；`test_window_helpers.py` 为 `303068675c3b63ddd3ea72b239b99405a48cd0416b821bde58d89068ae2c2b01`。与实施者10项直接辅助测试通过时的身份一致。

## Findings (not fixed)

- **覆盖范围须如实记录。** 当前生成器未生成 `jobs.status_group` 或 `incidents.stage/failure_type/retryable/retry_count/stalled_minutes`。已通知主会话在正式cases审核时按可用真实维度补有限用例，或明确记录未覆盖；不能将当前生成器输出称为研究方案所有筛选维度覆盖。现有case没有发现非法router参数，这属于覆盖结论边界，不是已有case不可运行。

## 已确认的实际合同

- 文件条目使用 `lstat`，符号链接仅记录 `readlink` 与nofollow的xattr，不递归其目标；文件和目录打开使用 `O_NOFOLLOW`，目录遍历只对directory分支执行。文件完整分块读取hash，没有按size截断、最大文件大小阈值或只取前缀。目录身份和捕获前后状态会重核。这里依赖获批T0停写和可信根路径，不将路径递归宣称为可抵御恶意并发替换的通用沙箱。
- 相对路径、链接目标、ACL/xattr和账号ID只写受限JSON；输出父目录须由当前执行者拥有且0700，临时文件0600，fsync后通过独占link发布，不覆盖已有结果。stdout仅输出数量、维度计数和摘要；错误沿已审 `safe_main` 输出受控分类，不打印业务值或异常正文。manifest包含敏感路径/属性，不能公开粘贴。
- 文件mode/uid/gid/mtime_ns、内容hash、内部硬链接关系、symlink目标、ACL/xattr均入manifest；atime不比较，捕获前后ctime/nlink仅用于发现变更。真实恢复的时间精度、根目录属性及ACL/xattr支持仍须由运行结果证明，不因离线mock通过而声明Linux恢复通过。
- 矩阵从已绑定恢复UUID的只读会话读取真实active admin/operator；生产UUID在读取环境或建立连接前拒绝。用户/任务原列ID与payload ID核对，任务持久created_at缺失失败；不启动应用bootstrap，结束rollback并关闭连接。
- 逐用户默认可见集合使用与原service相同的tenant/company/owner以及deleted/archived条件。普通分页上界准确，异常集合是其子集，因此异常分页使用这个较大上界不会漏页。每个真实用户均生成两入口默认、全部上界分页、越界页和无匹配搜索；额外维度按role/tenant/company选真实代表，不伪造角色或提升权限。
- 已生成的status/QA/sort均来自真实模型或owner；日期为aware ISO且上下界有序，字段名匹配已审query_diff和实际router。用户ID及搜索词仅进入私有cases文件。`no_match`标签由普通搜索字段生成并防碰撞；异常另有建议/证据摘要搜索域，正式响应仍须核实total/items为空，标签本身不是空结果证明。

## Verification

- Tests：复用初版9项通过；目录size修复后复用实施者报告的10项直接辅助测试通过，已核对源码SHA与新增回归断言。本复核未重跑。
- Lint / TypeCheck：未新增执行；按只读派发只查实际代码及直接合同。
- 真实Linux文件系统恢复、ACL/xattr、目录根元数据、真实账号矩阵及完整router结果：由主会话正在进行的隔离恢复证据决定，不在此报告提前标记通过。
- 本复核只新增此报告；未修改Python、冻结载体、产品代码或生产资源。新增报告为中文。

结论：目录size阻断已关闭。未发现其他阻止现有辅助命令使用的具体缺陷；正式覆盖结论和真实恢复验收仍须保留上述边界。
