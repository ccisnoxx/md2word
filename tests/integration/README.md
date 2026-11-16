# 生产 Compose 冷启动与模板目录验收

在可运行 Linux amd64 容器的隔离 Docker context 中执行。按 [Docker 部署说明](../../docs/deploy/p0-docker-deployment.md#依赖锁与构建输入) 准备 57 个已锁定的 wheel，宿主 Python 使用已安装仓库依赖的环境。

```bash
.venv/bin/python tests/integration/template_catalog_compose.py \
  --docker-context "$MD2WORD_TEST_DOCKER_CONTEXT" \
  --wheelhouse "$MD2WORD_TEST_WHEELHOUSE" \
  --report tests/tmp/template-catalog-report.json
```

脚本复制生产 Dockerfile 和 Compose 到临时构建目录，生成专用项目名、随机测试凭据和独立卷，端口由 Docker 在回环地址分配。API、非 root Celery、MySQL、Redis、文件登记与 DOCX 渲染都走正式入口。Worker 的 MinerU 客户端使用合成结果和任务放行标记，支持模板停用、删除和版本禁用场景。

空库通过一次 Compose `up` 启动。报告中的 `cold_start` 记录 API 健康探针成功、Worker 启动和容器重启计数。`restarts` 记录保留数据分别重启 API 和 Worker 后的旧产物校验值与新任务。`initialization_failure` 记录另一个空库项目中 API 因错误账号配置初始化失败、Worker 未启动的结果。报告同时保留镜像与 seed 哈希、任务绑定、DOCX 哈希和禁用原因码。

脚本退出时清理本次项目容器和卷，以及本次构建的候选镜像。
