# 定向验证

## 实际命令与结果

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ai_provider_config_api_updates_runtime_config_and_masks_secret tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_invalid_ai_provider_config_file
```

原始修改前基线 2 项通过，无基线失败。本次 AC-3 返工后重新运行，2 项通过（0.158s）。覆盖成功写入、响应脱敏、审计和损坏配置健康报告。

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_provider_config -v
```

实施代理在本次 AC-3 返工后重新运行 8 个方法，全部通过（0.021s）；主会话已阅读完整测试及最终服务差异。AC-1 保留 umask 0 下实际创建瞬间、替换前、最终 mode 和 inode/JSON 格式断言；AC-2 保留 fchmod/fstat/创建/实际 mode 不符，以及 fdopen/replace 失败与旧记录保全断言，检查整个配置目录确认无随机临时文件泄漏；AC-3 覆盖历史固定名和随机名普通残留/符号链接同时存在时保存成功，残留内容、inode、权限及独立链接目标均保持不变；API 失败测试确认 HTTP 500、无密钥和无成功审计。AC-4 由上述两个现有方法证明。

`git diff --check` 通过。测试仅出现既有 Starlette/httpx 及 HTTP 状态常量弃用警告。新增注释、测试文档字符串和创建/权限异常均为中文。

上一轮固定临时名策略未满足用户对 AC-3 可用性的验收要求，已由唯一随机名方案替换；不沿用上一轮 AC-3 通过结论。

本次独立 trellis-check 只读复核已完成，未发现实际缺陷：随机排他创建、残留不阻塞、只清理本次文件及 AC-1/AC-2 保全均符合更新后的任务合同。复核未修改文件或重复执行测试。

## 边界

未运行全仓、前端或发布门禁；未访问生产、数据库、真实 Provider 或 MinerU。历史残留不阻塞写入，也不自动删除不属于本次创建的文件。clear_api_key 仍可回退 OPENAI_API_KEY。只在本机 POSIX 文件系统验证，不声称跨平台或部署验收。

未提交、推送、归档或运行 add_session。任务记录保留 in_progress；本地完成与用户验收、提交归档是不同状态。
