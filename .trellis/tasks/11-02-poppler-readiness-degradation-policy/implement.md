# 实施清单

1. `app/core/config.py`：三个配置与 `production_like`。
2. `app/infrastructure/pdf_crop.py`、`scripts/dev/run_document_worker.py`、`app/services/health_service.py`、`app/main.py`：Poppler 检查与接线。
3. `page_degradation.py`、`mineru_converter.py`、`execution.py`：策略对象。
4. 测试：`test_document_worker_entrypoint`、`test_runtime_dependency_declarations`、`test_page_degradation`、`test_render_page_degradation`。
5. 文档：`runtime-configuration.md`、`word-generation-rules.md`、`docs/runbooks/backend.md`、`docker/README.md`。
