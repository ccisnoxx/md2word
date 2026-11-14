# RND-504 实施清单

规划获确认后执行。

1. 核对届时主干的 Word 预览领取、登记、下载授权和配置入口。按 AC1 至 AC3 在 `tests/test_word_preview_compatibility.py` 补三个定向场景，复用现有测试夹具。
2. 在 `docs/runbooks/backend.md` 添加运行说明。保留既有文档核验范围，为新增小节注明静态源码依据和未核验边界，链接现有 B1 待验证说明。
3. 核对差异范围和文档链接。若定向用例揭示现有产品行为偏离计划，记录复现和影响，交由用户决定是否另开修复。

## 计划验证

实施获准后，按用户届时授权执行 `.venv/bin/python -m unittest tests.test_word_preview_compatibility`。进程和对象存储夹具使用临时数据。当前规划阶段只校验任务材料及工作区范围。
