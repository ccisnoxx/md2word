# 实施与定向验证

1. 连接普通转换的结构预检、原生保留、可信图像占位和原页回退。采用现有来源定位、资源注册、页依赖、失败日志和下载路径。
2. 只对已认证的新回退调整活动质量分级，在现有质量报告提供 warning 与人工复核；保留旧证据格式和独立硬门禁。
3. 通过普通 Worker 和真实 HTTP 路由核对三种成功响应，下载实际 Word 并核对内容；验证无可靠回退、摘要错误和实物表缺失三个负例。
4. 核对差异和工作区。补记实际命令、结果和未验证范围。授权范围仅含以上定向用例。

## 实际执行与结果

验收基线为本地 `main@96e7aca2`，使用临时目录、正式直转 Worker 和 TestClient。测试模块为 `tests/test_reviewable_table_structure_fallback.py`。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest -v tests.test_reviewable_table_structure_fallback
```

首轮运行 6 项，耗时 1.553 秒。无可靠回退、参考图摘要不一致和 Word 漏表三个负例通过。三个成功场景的整体质量断言失败。核对发现成功夹具缺少实际 PDF 页尺寸的 `middle.json`，并且预览禁用仍独立贡献 `pending`。为成功用例补齐与 PDF 一致的页尺寸和现有本地预览替身，负例沿用原夹具。保留独立质量提示和预览的原分级。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest -v \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_bad_html_preserves_the_native_cells_and_downloads \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_illegal_merge_preserves_the_verified_reference_and_downloads \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_empty_table_without_crop_preserves_the_single_pdf_page_and_downloads
```

复验只运行首次未通过的三项，退出码 0，3 项通过，0 项跳过，耗时 1.194 秒。每项为 `succeeded/completed`、质量 `warning`。质量 API 返回原页、来源指针、保留方式及 `manual_review_required=true`。三项内部签发和真实 HTTP 下载均返回 200，下载字节与登记主件匹配。Word 分别保留 Alpha/Beta 原生单元格、已验证参考图，以及真实 Poppler 生成的单页原图。图像场景带不可编辑提示。

三个负例分别核对带页定位的 `table_structure_recovery_unavailable`、`table_placeholder_integrity_failed` 和 Word 实物不符的 `render_failed`，均无可下载结果。复用首轮通过记录。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/export_openapi.py
git diff --check -- app tests docs/api/openapi.json .trellis/spec/backend/word-generation-rules.md
```

同步质量 API 维护快照，导出 180 条路径、399 个 schema。差异空白检查通过。使用 Python `ast.parse` 静态核对 19 个变动 Python 文件，并读取快照确认人工复核条目和 `warning` 严重度。

## 未验证范围

v2 图表识别分支、非字符串坏 HTML 的占位证据、旧凭据重读、源 PDF 局部裁图和跨页/多页依赖闭包仅做静态复核。本轮没有重跑既有 P7、LOW/HIGH 或其他历史用例。未验证生产部署、生产预览、Word/WPS 视觉结果、正式发布后最终件下载。未提交，未推送。
