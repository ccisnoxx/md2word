---
doc_type: technology-stack
status: current-and-target
last_reviewed: 2026-10-03
---

# 技术栈与技术约束

## 1. 后端

| 技术 | 当前用途 | 约束 |
|---|---|---|
| Python 3.11 | API、Worker、转换与脚本 | 生产 Docker 基线 |
| FastAPI 0.136.x | HTTP API | OpenAPI 快照必须同步 |
| Uvicorn 0.47.x | ASGI Server | API 容器运行时 |
| Pydantic Settings 2.14.x | 环境配置 | 所有 secret 走环境或现有配置服务 |
| Celery 5.4.x | document job 与 translation batch 异步任务 | Redis broker/backend |
| Redis 7 | 队列和 Celery 状态 | 不作为业务状态真源 |
| MySQL 8.4 | 任务、配置、审计和文件元数据 | `utf8mb4` |
| PyMySQL 1.1.x | MySQL 驱动 | 使用现有 repository/adapters |
| python-docx 1.1+ | DOCX 生成 | 高级 OOXML 不足时使用低层 OXML |
| BeautifulSoup4 4.12+ | 表格 HTML 文本抽取和翻译回填 | 不让模型修改 HTML 结构 |
| OpenAI Python SDK 1.x | OpenAI-compatible 翻译 Provider | Provider 可配置，密钥不进入日志 |
| boto3 1.34+ | S3 Artifact Storage | local_object 仍是可用后端 |
| requests/urllib3 | MinerU 和外部 HTTP | 所有下载执行大小、域名和超时限制 |
| Loguru | 结构化日志 | 生产建议 JSON |
| PyYAML | 配置、规则和样本 manifest | 写入必须经过 schema 验证 |

## 2. 前端

| 技术 | 当前用途 |
|---|---|
| Vue 3.5 | 内部门户 |
| TypeScript 5.7 | 类型和 API 合同 |
| Vite 6 | 构建与开发服务器 |
| Element Plus 2.9 | UI 组件 |
| Pinia 2.3 | 客户端状态 |
| Vue Router 4.5 | 路由和权限入口 |
| Axios 1.7 | HTTP Client |
| Sass | 样式 |
| Vitest 3.2 | 单元测试 |
| Playwright 1.54 | 浏览器 smoke/E2E |

## 3. 生产部署

```text
Docker Compose
├── api: FastAPI/Uvicorn
├── worker: document worker/Celery
├── redis: Redis 7 Alpine
└── mysql: MySQL 8.4
```

产物：

- `local_object`：Docker volume `/app/var`；
- `s3`：通过 `S3ArtifactStorageAdapter`；
- 生产 API 默认只绑定宿主机回环地址，由外部反向代理负责访问入口。

## 4. 测试工具

### 后端

当前仓库主要使用 Python `unittest` 和项目脚本：

- targeted unit tests；
- Golden Sample regression；
- component PDF regression；
- local MinerU quality matrix；
- P1 translation regression；
- release check；
- runtime/online gate。

### 前端

```bash
npm run build
npm run test:unit
npm run test:smoke
```

## 5. 技术选择原则

1. 保持 Python 单体，不引入第二语言渲染服务，除非 Open XML 验证出现无法解决的刚性需求。
2. 不更换 FastAPI、Vue、MySQL、Redis/Celery 主栈。
3. 表格能力优先扩展现有 parser/renderer，不引入浏览器 HTML→DOCX 黑盒转换器。
4. 翻译 Provider 保持 OpenAI-compatible port，不把业务绑定到单一模型供应商。
5. Word 预览可通过受控 Office/LibreOffice 转 PDF 适配器实现，但必须作为可替换基础设施端口，不能进入文档语义核心。
6. 不为架构外观引入微服务、事件总线、CQRS 框架或通用工作流引擎。
7. 数据库 schema 变更使用项目现有迁移机制；若尚无正式 migration，实施任务必须先建立版本化迁移，不在应用启动时追加不可追踪 DDL。
8. 所有新依赖需要明确：用途、替代方案、许可证、体积和生产镜像影响。

## 6. 推荐新增但非强制依赖

| 能力 | 优先方案 | 备注 |
|---|---|---|
| HTML 规范化 | 继续使用标准库/BeautifulSoup | 避免引入大型浏览器引擎 |
| DOCX 预览 | LibreOffice headless adapter 或公司 Word 自动化环境 | 必须隔离为 adapter |
| 页面图像比较 | Pillow + 项目现有脚本 | 不进入在线主链路的硬依赖，先作验收工具 |
| 数据库迁移 | Alembic 或有序 SQL | 根据现有 persistence 约束选择 |
| 静态检查 | 现有 release check；可逐步增加 ruff/pyright | 不在同一任务中大范围改造工具链 |

## 7. 版本策略

- 现有依赖版本以仓库 lock/requirements 为准；
- 实施功能任务不得顺便全量升级框架；
- 依赖升级应独立 Trellis 任务；
- 生产镜像发布应使用 commit SHA 或 release ID，不只依赖 `latest` 标签；
- 任务快照必须记录 renderer、Prompt 和配置版本，但不要求记录所有 Python 包版本。
