# md2word

PDF 到 Word 转换与内部工作台项目。当前 P0 发布主链路是：

1. 上传 PDF：`POST /api/v1/files/upload-url` 后 `PUT /api/v1/files/{file_id}/content`
2. 创建任务：`POST /api/v1/document-jobs`，默认 `mode=direct_pdf_to_word`
3. 查询任务：`GET /api/v1/document-jobs/{job_id}` 和 `/events`
4. 下载结果：`GET /api/v1/document-jobs/{job_id}/download-url`

## 发布与联调入口

- 后端运行手册：[docs/runbooks/backend.md](docs/runbooks/backend.md)
- 正式内部门户说明：[docs/runbooks/internal-portal.md](docs/runbooks/internal-portal.md)
- P0 内部联调步骤：[docs/testing/pdf-to-word-p0-integration-guide.md](docs/testing/pdf-to-word-p0-integration-guide.md)
- Golden Sample 状态：[docs/testing/pdf-to-word-golden-sample-acceptance-report.md](docs/testing/pdf-to-word-golden-sample-acceptance-report.md)
- API 清单：[docs/api/manifest.yaml](docs/api/manifest.yaml)
- OpenAPI 快照：[docs/api/openapi.json](docs/api/openapi.json)

发布前最小检查：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run build
```

前端工作台位于 `frontend/`，本地开发命令：

```bash
cd frontend
npm run dev
```
