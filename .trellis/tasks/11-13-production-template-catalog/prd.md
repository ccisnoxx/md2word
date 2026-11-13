# [P1] 生产动态模板目录持久化与 Worker 快照解耦

## 目标

标准生产 Docker Compose 中，管理员可创建、上传、验证、发布、设默认、停用及删除模板。API 与 Celery Worker 分容器运行，分别重启后仍能使用已提交的模板目录与已发布版本生成 DOCX。

## 已核实

- 标准环境将清单指向镜像内 `resources/template_configs/templates_manifest.yaml`。非 root API 先保存 DOCX、写入数据库草稿，再覆盖该文件。写失败可留下文件和草稿。API 与 Worker 共享 `/app/var`（`.env.example:79`、`docker/prod/Dockerfile:23`、`docker/prod/docker-compose.yml:32`、`:61`、`app/domains/templates/read_service.py:242`、`:956`）。
- Celery 每次执行任务都重建 runtime。带快照的任务在数据库版本校验前仍检查清单准入（`app/workers/document_tasks.py:19`、`app/domains/document_jobs/render_execution.py:95`）。
- MySQL 已保存版本快照、版本状态和各模板默认版本；模板级元数据和全局默认模板 ID 分别由 YAML 和 `template_state.json` 持有（`app/domains/resources/repository.py:10`、`app/domains/templates/read_service.py:810`）。

## 需求与验收

| ID | 需求与可观察结果 |
| --- | --- |
| AC1 | MySQL 提供运行时目录、启用状态、默认选择和版本。空库幂等登记 bundled seed，旧库保留已登记历史及合法默认。模板 CRUD、上传与设默认成功，seed 和旧默认状态文件在管理操作前后字节一致。file/SQLite 保留本地兼容入口。 |
| AC2 | 保留 API 形状、admin 权限、审计与发布规则。普通用户只绑定可用 published 版本，admin 可显式绑定 draft 做验证，发布须提供同一草稿快照的成功任务。模板级停用、删除提交后，新建和克隆任务均不能绑定该模板。当前默认模板受保护，历史版本和文件保留。 |
| AC3 | 先绑定 `JobResourceSnapshot`，再停用或删除模板，随后执行或重试同一任务时，仍可用原绑定生成 DOCX。Worker 按数据库版本、任务绑定与资源字节校验，不查 manifest、模板级状态或默认选择。若在渲染前显式禁用该版本，Worker 以 `resource_snapshot_invalid_status` 拒绝。缺记录、身份/哈希不符和未授权 draft 仍失败。无快照历史任务沿用既有解析入口。 |
| AC4 | 支持旧清单和旧默认状态的只读预检、显式导入和核对，保留自定义元数据、版本身份及合法默认。合成旧库覆盖已关闭版本、孤立草稿、缺失文件与冲突。重复应用不覆盖历史 payload/hash、不复活删除模板，不改历史任务。 |
| AC5 | 同 ID 并发创建最多提交一套目录与首版；不同模板的更新均保留，并发上传使用唯一版本号。事务失败无可见半成品，提交结果未知时不误清理已提交资产。禁用、删除与切换默认交错时，默认仍指向启用模板的 published 版本。 |
| AC6 | 隔离 Compose 使用生产镜像和真实 API、MySQL、Redis、Celery、Word 渲染。经正式 API 创建自定义草稿、验证并发布，运行中的 Worker 生成成功。分别重启 API 和 Worker，每次重新列表、创建并完成绑定同一模板的任务，检查 DOCX 与 seed 哈希。 |

## 范围

模板目录、版本和任务接线、MySQL 增量结构、旧目录导入、相关 Spec/API/部署说明和定向测试。生产库访问与上线、凭据变更、全仓迁移治理、前端改版、历史文件清理及 bundled 模板字节修改不在本任务范围。
