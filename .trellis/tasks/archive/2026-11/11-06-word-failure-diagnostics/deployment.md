# 前端上线记录

- 用户明确授权提交、推送及部署；本次仅部署前端静态资源。
- 功能提交：`1a346905095a11f4150e5f4d0572a24ae4bef336`。
- PR：[ #30 ](https://github.com/ccisnoxx/md2word/pull/30)，已合并；线上源码版本为 `0c5fc3fc09e0a898789005245acee6b375442a1a`，与构建时前端源码完全一致。
- 上线时间：2026-11-06 22:43:50（Asia/Shanghai）。
- 主机：`hostdzire`。公开入口：https://md2word.962850.xyz 。
- 前端目录：`/var/www/md2word-frontend/releases/frontend-0c5fc3fc-20261106`；`current` 已原子切换。
- 回滚目录：`/var/www/md2word-frontend/releases/frontend-adapt-3ecb2a19ded6`，完整保留。
- 服务器制品与记录：`/root/md2word-frontend-artifacts/frontend-0c5fc3fc-20261106/`，含 tar、逐文件 manifest 和 deployment.json。
- 制品 SHA-256：`34fbbfe812e8ff60f4a9bed0ddfe45a27da1201acd6e174250f61037e3bf908b`。

## 验证

- `npm run build` 通过，生成 104 个文件；只有既有第三方 PURE 注释和 chunk 大小警告。
- 上传后逐文件 SHA-256：104/104 一致。
- nginx 配置检查通过，重载成功；源站首页及 index、failureDiagnostic、JobDetailPage、IncidentTriagePage 相关资源共 8 项均为 200，内容哈希与 manifest 一致。
- 公网对相同 8 项校验通过；公网和内网 `/api/v1/health/live`、`ready` 均为 HTTP 200、status=ok。
- API/Worker 镜像保持 `md2word-p0:1da199f-20261106T114319Z`；容器 ID、镜像 ID、启动时间均未变化。未操作数据库、Redis 或其他站点配置。
- 既有 22/22 定向测试和独立复核成功结果继续有效，没有重新跑应用回归。

## 发布过程中的恢复

首次直接推送 main 被 GitHub 的 PR 必须规则拒绝，随后通过功能分支和 PR #30 正常合并，未绕过规则。

首次切换后的源站校验错误使用 loopback 443，连接失败后脚本已自动恢复旧目录。检查实际监听后确认站点位于 WireGuard 地址且要求 PROXY protocol；使用 curl 的 `--haproxy-protocol` 和对应源站解析验证旧站点 200 后，复用同一份已校验制品重新切换，全部校验通过。未修改网络配置或后端以适配错误校验方式。

## 回滚方式与边界

如需回滚，原子地将 `/var/www/md2word-frontend/current` 指回上述回滚目录，执行 nginx 配置检查/重载，并复核首页与 API 健康。保留的新旧制品足以支持回滚，不需要重建后端镜像。

本次证据证明构建产物已经由公网提供，不等于浏览器视觉、响应式或具体失败任务根因验收；没有新建或重试生产转换任务。历史任务没有保存页码时，新 UI 仍只说明未记录失败页码。
