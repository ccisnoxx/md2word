---
doc_status: active
last_verified_commit: d45e46e1233c3f173fa1d738cf75b3ef7a393eb9
owner: null
verification_scope: >-
  静态对照该提交的 dev/prod Dockerfile、Compose 与 requirements.txt，核对运行锁、wheelhouse、pip 参数和共用镜像声明；未构建、拉取、启动或访问生产。 依据与内容身份：.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b1-implementation.md。
---

# docker/README.md: 说明开发与生产 Docker 编排入口。

## 目录

- `dev/`：本地开发环境，代码热挂载，适合临时用 Docker 跑 API、Worker、MySQL、Redis。
- `prod/`：生产/测试部署环境，镜像内复制代码，适合 hostdzire 这类单机部署。

两套环境都读取仓库根目录 `.env`。真实密钥和账号文件不要提交。

两套镜像都通过 apt 安装 `poppler-utils`（`pdfinfo`/`pdftoppm`，用于表格占位裁切、图片 PDF 回退和整页降级）。`requirements.txt` 是直接依赖声明入口；实际镜像安装共同消费 `requirements/locks/cp311-linux-amd64.txt` 的完整版本/hash 锁和构建前补齐的 `requirements/wheels/`。

两个 Dockerfile 均使用 `--isolated --no-index --find-links=/tmp/wheels --require-hashes --only-binary=:all:` 离线安装；缺少匹配 wheel 或 hash 不符时停止，不回退索引或 sdist。当前锁只覆盖 CPython 3.11.18 / Debian 13 trixie / linux/amd64，apt 系统包未锁快照；这不代表整镜像逐字节可复现或生产验收通过。wheelhouse 的来源、57 个运行制品及发布准备见 [P0 依赖锁与构建输入](../docs/deploy/p0-docker-deployment.md#依赖锁与构建输入)。

API/Worker 共用 `MD2WORD_IMAGE`：开发默认 `md2word-dev:local`，生产必填版本化引用。先构建一次 API 镜像，再用 `--no-build` 启动两者；生产切换还需核对实际 image ID。下面是仓库 Compose 的入口，hostdzire 既有分层 override 方式见[部署记录](../docs/deploy/hostdzire-dmit-md2word.md#分层-override-上线当前生产方式)，不能直接套用仓库编排覆盖线上配置。

## 开发环境

```bash
docker compose --env-file .env -f docker/dev/docker-compose.yml build api
docker compose --env-file .env -f docker/dev/docker-compose.yml up -d --no-build
```

## 生产环境

```bash
export MD2WORD_IMAGE="md2word-p0:${RELEASE_VERSION:?请设置本次发布版本}"
docker compose --env-file .env -f docker/prod/docker-compose.yml build api
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --no-build
```
