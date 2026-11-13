# 生产 Compose 模板目录验收

在可运行 Linux amd64 容器的隔离 Docker context 中执行。按 [Docker 部署说明](../../docs/deploy/p0-docker-deployment.md#依赖锁与构建输入) 准备 57 个已锁定的 wheel，宿主 Python 使用已安装仓库依赖的环境。

```bash
.venv/bin/python tests/integration/template_catalog_compose.py \
  --docker-context <隔离-context> \
  --wheelhouse <已核对的-wheel-目录> \
  --report tests/tmp/template-catalog-report.json
```

脚本复制生产 Dockerfile 和 Compose 到临时构建目录，生成专用项目名、随机测试凭据和独立卷，端口由 Docker 在回环地址分配。API、非 root Celery、MySQL、Redis、文件登记与 DOCX 渲染都走正式入口。空库先等待 API 完成非模板种子登记，再启动 Worker。Worker 就绪后才创建自定义模板。Worker 的 MinerU 客户端使用合成结果和任务放行标记，支持在模板停用、删除或版本禁用提交后继续消费已绑定任务。脚本退出时删除本次项目容器与卷，运行成功后输出镜像 ID、seed 哈希、任务绑定、DOCX 哈希和禁用原因码。
