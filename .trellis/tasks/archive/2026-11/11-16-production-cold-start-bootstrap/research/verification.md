# 生产冷启动单一初始化验收

2026-11-16 在独立 Colima 虚拟机中完成。虚拟机为 ARM64，容器通过 QEMU 运行 Linux amd64。使用仓库生产 Dockerfile 与 Compose，固定的 Python、MySQL 和 Redis 镜像，以及 SHA-256 全部匹配生产锁的 57 个运行 wheel。API 与 Worker 使用同一候选镜像，业务任务通过真实 MySQL、Redis 和 Celery 执行，MinerU 外部响应来自合成夹具。完整记录见 [Compose 验收报告](./compose-acceptance.json)。

| 验收 | 结果 |
| --- | --- |
| 空库一次 `compose up` | 通过。API 探针于北京时间 00:46:04.431 成功，Worker 于 00:46:04.693 启动，API 和 Worker 重启计数均为 0。账号登录、Acceptance 记录、术语规则、翻译术语、Translation Profile 和模板默认资源均可读回。专项共成功生成 7 份 DOCX。 |
| API 初始化失败 | 通过。独立空库中，错误账号文件触发 `AUTH_INTERNAL_USERS_FILE 不是合法 JSON。`。Compose 退出码为 `1`，API 为 `unhealthy`，Worker 容器停留在 `created`。 |
| 保留数据并分别重启 | 通过。API 和 Worker 分别重启，另一容器的启动时间保持原值。账号、默认资源版本与摘要、旧任务绑定均通过对照。同一历史 DOCX 的 SHA-256 两次一致。每次重启后均完成一个新任务。 |

16 项定向单测、修改的 Python 文件编译、Trellis 上下文校验与 `git diff --check` 通过。独立复核检查了三个 Worker 入口、API 装配顺序、鉴权和验收断言。

首轮在单独重启 API 后被 Docker Hub 的镜像元数据请求 TLS 超时中断。验收脚本在重启和失败场景明确复用已拉取的固定镜像，随后完整运行通过。生产 Compose 的镜像引用与拉取策略沿用原配置。两套隔离项目、卷、候选镜像和本次专用 Colima 环境已清理。
