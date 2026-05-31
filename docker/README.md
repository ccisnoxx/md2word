# docker/README.md: 说明开发与生产 Docker 编排入口。

## 目录

- `dev/`：本地开发环境，代码热挂载，适合临时用 Docker 跑 API、Worker、MySQL、Redis。
- `prod/`：生产/测试部署环境，镜像内复制代码，适合 hostdzire 这类单机部署。

两套环境都读取仓库根目录 `.env`。真实密钥和账号文件不要提交。

## 开发环境

```bash
docker compose --env-file .env -f docker/dev/docker-compose.yml up -d --build
```

## 生产环境

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --build
```
