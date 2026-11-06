# 部署与线上验收

2026-11-06，用户明确授权提交、推送、部署及线上表格占位失败验证。本记录补充并取代实施记录中“尚未提交/部署”的历史状态。

## 发布身份

- 功能提交：`af33c9401f1b71db6fe7dd509fe599fde714f57f`。
- PR：[#32](https://github.com/ccisnoxx/md2word/pull/32)，已合并。
- 线上源码：`28cacd8a3afea2cd02fc36230ad9d6bc0e7b89e8`。
- 主机：`hostdzire`；公网入口：https://md2word.962850.xyz 。
- 后端 release：`/root/md2word-releases/28cacd8a-table-diagnostics`。
- API/Worker 使用同一实际镜像：`sha256:77176d1903e9f266814b9ec3464551d1920c50b33683f3707889d570243dac7a`。
- 发布标识：`hostdzire-20261106T152635Z-28cacd8a`。
- 前端：`/var/www/md2word-frontend/releases/frontend-28cacd8a-table-diagnostics`，current 已原子切换。
- 服务器制品、脚本与日志：`/root/md2word-validation/table-diagnostics-deploy/`；release 内保留 deployment-context.json、deployment-result.json 和 Compose 文件清单。

## 发布验证

- 当前 Docker daemon 无 registry mirror 或 HTTP/HTTPS proxy；活动 builder 为 default/docker。按官方固定 Python tag/digest 执行 docker pull 成功，未换源。
- 从 GitHub bare 缓存导出目标提交；57 个运行 wheel 与既有官方来源记录及当前锁的 SHA-256 一致。构建成功，临时容器的 pip check 与应用/Worker 导入通过。
- 复用已通过的类型检查，仅执行 Vite 构建生成发布包；104 个前端文件上传后全部哈希一致。只有既有第三方 PURE 注释和 chunk 大小警告。
- 沿用生产完整分层 Compose 配置，只重建 API/Worker；MySQL/Redis 容器 ID 未变化，部署前无活动转换任务。未调整凭据、模板挂载、数据库结构或其他站点。
- API/Worker 实际 image ID 相同，Worker 启动就绪。内网及公网 live/ready 为 200/ok，公开 ready 返回版本 28cacd8a。
- 公网 index.html、JobDetailPage、IncidentTriagePage、failureDiagnostic 相关资源 4 项内容哈希与制品一致。

## 真实失败验收

通过用户已登录的 Chrome 正常重试入口，仅重试 `docjob_914c18d077b8` 一次，沿用原配置。retry_count 从 0 变为 1，复用既有 MinerU 产物，从 parsed 恢复到 ir_converting；未重新提交 MinerU、批量重试或改写历史事件。

北京时间 **23:31:34** 产生新 stage_failed：

- 分类仍为 `failed / ir_converting / document_ir_failed`。
- 新 failure_context 为 `operation_kind=table_placeholder`、`reason_code=table_placeholder_geometry_invalid`、`block_ids=[block_0634]`。
- `source_page_index=52`，API 投影 `page_number=53`、`affected_page_numbers=[53]`、`source_page_count=53`、`page_count_basis=mineru_layout`。
- 同事件 MinerU 报告仍为 `can_convert=true / first_fatal=null / fatal_count=0`，不再遮蔽操作诊断。
- 只读核对原始解析 ZIP 的登记哈希；其第 639 个零基内容项为 page_idx=52 的空 HTML 表格，源 PDF 登记页数为 53。与此次异常源片段一致，未用旧非致命告警回填页码。
- Chrome 真实页面的概览、诊断页签、异常抽屉三处均显示“表格占位区域无效”“源 PDF 第 53 页”。技术详情同时显示 block_0634 / table_placeholder。已查看异常抽屉截图确认可见结果。

脱敏机器证据见 `research/online-verification.json`。本轮验收证明诊断记录与展示修复，不表示原始几何问题已修复或该文档已转换成功；其余历史失败任务未重试。

## 部署过程中的恢复

最初准备脚本使用了宿主 Python 不支持的 tarfile filter 参数，在服务切换前退出；改用系统 tar 解包同一已知制品后继续。

首次服务切换时 API 先于 Worker 就绪，脚本立即查 Worker ready 日志导致过早判失败，已自动恢复旧镜像与前端目录。旧版健康正常后，将该检查改为限时等待 Worker 完成启动，复用同一镜像和静态包重新切换，全部通过。没有为发布修改产品代码或放宽健康条件。

## 回滚

后端按 deployment-context.json 的 previous_files 清单，在原 compose_cwd 中执行原分层配置的 `up -d --no-deps --no-build api worker`；上一版本镜像及 `/root/md2word-releases/1da199f-20261106T114319Z` 保留。前端可将 current 原子指回 `/var/www/md2word-frontend/releases/frontend-0c5fc3fc-20261106`。恢复后核对 live/ready、实际镜像和公网静态文件。

部署和重试之后没有再次修改应用代码；不重复已通过的本地测试，不运行全仓回归、完整发布聚合或多样本 Golden Sample。
