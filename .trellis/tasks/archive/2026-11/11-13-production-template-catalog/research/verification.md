# 动态模板目录验证记录

实现分支 `codex/production-template-catalog`，基线 `b6264d91`。实现保存在独立 worktree。主工作区原有改动保留。

## 定向与 MySQL

- 77 项定向用例通过，覆盖模板 CRUD、发布、默认选择、草稿快照授权、Worker、克隆和重试、旧任务及迁移。
- 生产 Compose 所锁定 MySQL 镜像 `sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`，实际版本 8.4.9 Linux x86_64。使用独立 loopback MySQL、每用例随机 schema，`tests.test_mysql_template_catalog` 4 项通过。覆盖同 ID 并发创建、首版冲突回滚、COMMIT 应答丢失、版本序列、默认与停用并发、旧库结构增量与幂等导入。隔离容器与卷已清理。
- 一条扩展模式用例 `test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot` 在 GET detail 的 `word_preview` 字段断言失败。未改动基线 `b6264d91` 可同样复现。
- 独立质量复核通过 73 项定向检查及 6 项兼容/导出检查。OpenAPI 对照仓库快照为零差异（180 路径、393 schema）。Python 编译、Trellis 上下文校验和 `git diff --check` 通过。当前后端未配置独立的 linter 或类型检查器。

## 复核范围

- 独立复核后，Celery 消费入口跳过模板 seed 初始化，发布要求同一草稿快照，迁移预检与启动共用 seed 身份校验，旧删除的内置模板保留墓碑，上传和迁移统一排除 `.` 与 `..` 模板 ID。
- 模板管理成功审计沿用独立写入。若审计失败，目录或版本事务可能已经提交。默认版本切换的审计一致性仍由并行的 `11-13-template-default-switch-integrity` 任务处理。
- 实际生产 MySQL 数据、正式 MinerU 和上线验收未执行。

## 生产 Compose 专项

通过。使用生产 Dockerfile、锁定的 MySQL/Redis 镜像和真实队列，在独立 Colima aarch64 VM 通过 QEMU 执行 Linux amd64 容器。API 和 Worker 为同一镜像、UID 均为 1000，唯一共同可写卷为 `/app/var`，两者的 bundled seed 均不可写且前后哈希一致。空库先启动 API 完成非模板 seed 登记，再启动 Worker；业务请求开始前确认 Worker 已就绪。仅外部 MinerU I/O 使用本地合成夹具。

七个任务成功生成 DOCX，并验证正文、版本化页眉和绑定。覆盖 v1/v2 草稿验证、普通任务、API 与 Worker 分别重启后的重新列表和生成，以及模板级停用与删除后已有绑定继续执行。停用或删除后新建与继承源快照的克隆返回 404，三份历史 DOCX 哈希不变。显式禁用非默认 v2 后，已绑定任务 `docjob_7009f81170ae` 在渲染阶段失败，原因码为 `resource_snapshot_invalid_status`。

见 [Compose 报告](compose-report.json)。诊断中的 Docker 动态端口在 API 重启后由 32774 变为 32775，最终验收通过重新发现回环端口继续执行。诊断中的非模板 translation profile seed 首次登记竞争由上述空库启动顺序规避。
