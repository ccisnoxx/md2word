# hostdzire 发布合同摘要

来源：`docs/deploy/hostdzire-dmit-md2word.md`、`docs/deploy/online-first-validation-workflow.md` 和归档任务 `07-22-redeploy-production`。

## 正常路径

1. 目标 commit 先推送到 GitHub并锁定完整 SHA。
2. hostdzire 从 bare repo fetch，通过 `git archive` 创建新的 `/root/md2word-releases/<short-sha>`。
3. 复用上一 release 的 `.env` 和内部账号文件，只更新 `APP_VERSION`/`DEPLOYMENT_ID`。
4. 构建共享 `md2word-p0:latest`，启动 API/Worker；不得执行 `down -v`。
5. 运行 Compose、日志、live/ready/metrics、runtime release check 和 Golden Sample preflight。
6. 前端 dist 使用独立 release 目录，后端门禁通过后才原子切换 nginx `current` symlink。
7. 公网只核验入口；普通代码发布不修改 dmit。

## 回滚

- 后端新旧 release 共用 mutable `latest` tag，回滚时必须在旧 release 重新 build，再 force-recreate API/Worker。
- 前端恢复旧 symlink 后执行 `nginx -t` 和 reload。
- 本任务会重置旧版本状态；若新 V1 已 bootstrap 后必须回滚，先停止新服务并删除新 V1 的版本/默认/序列状态，再切回旧 release，让旧 V2 seed 从旧 release 自身资产重新 bootstrap，避免不同字节复用同一个 V1 payload。
- 不删除 release、volume 或失败证据。

## 安全边界

- 只使用 SSH alias `hostdzire`；host-key conflict 时停止。
- 不读取、输出或写入私钥内容。
- 命令和任务证据不得输出 `.env`、数据库密码、admin token 或内部账号 JSON。
- 生产写操作前重新解析当前 release 和精确目标，不依赖过期路径或宽泛 glob。
