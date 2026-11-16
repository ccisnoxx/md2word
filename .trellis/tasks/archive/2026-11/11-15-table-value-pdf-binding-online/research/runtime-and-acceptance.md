# 运行环境与跨版式验收依据

## 可复用的取证条件

- 第三阶段观察器每候选页调用 `pdfinfo`、`pdftotext`、`pdftocairo`、`pdftohtml`，须四者版本一致，既有限额为每次子进程 15 秒、单产物最多 4 MiB，再限制 XML 元素及词数。转换中对同页成功或失败观测均缓存一次。依据 `app/services/document_ir/pdf_value_column_observer.py:21–26,554–596`、`app/services/document_ir/pdf_value_column_review_flow.py:113–129`。
- 仓库生产镜像的构建定义安装 `poppler-utils`，镜像以非 root 用户运行。Celery 的软时限取 `p0_document_job_timeout_seconds`，仓库默认 1200 秒，硬时限加 60 秒。输入 PDF 默认允许至多 200 页。逐页上限不能约束多页累计耗时。建议在新功能入口设置整份文档的剩余取证时限，时限耗尽的候选继续阻断并可定位。依据 `docker/prod/Dockerfile:2–29`、`app/workers/celery_app.py:24–30`、`app/core/config.py:65–74`。
- 仓库镜像定义和第三阶段本机 Poppler 26.06.0 实测分别记录。线上 Worker 实际安装的四个工具、版本、临时目录和真实 MinerU 原包内容本轮均未探查。进入后续启用评审前需独立核验。当前验收用本地依赖、正式 Worker 代码与受控输入。

## 渲染降级的交叉合同

线上非翻译渲染的已知页面失败可以按规则转换为整页栅格。它新登记 IR 后按代次和旧 IR 指针条件更新。现有 `drop_degraded_table_groups` 会去掉相关原生表片段，而第三阶段未决项校验要求片段仍属于该 IR。若直接开启，含未决项的被降级表可能留下悬挂 ID，导致既有降级失败。第四阶段需随原有删除闭包整理最终 IR 的引用，并保持整页降级质量阻断和前一份 IR 的追溯，不能将被移除片段视为通过实物认证。依据 `app/domains/document_jobs/render_execution.py:376–444`、`app/services/document_ir/page_degradation.py:127–150`、`app/services/document_ir/logical_table_group.py:464–469`。

## 可复用的验证对象

| 对象 | 已有证据与第四阶段用途 |
| --- | --- |
| 完整 `gs-008` | 第三阶段相同原包的两次本地正式转换，实际 Word 已验 `±5 µV → TYP`、`±100 µV → MAX`、`±75` 和单位纵向合并，原 23 条保留，9 条认证修正，14 条仍阻断。第四阶段包和 PDF 字节按清单核验后喂给正式 Worker，不替换表格 HTML。 |
| 独立 LOW/HIGH 划线表 | `tests/test_table_value_pdf_binding_poppler.py:20–98` 生成实物 PDF 和错误跨列 HTML。非右对齐的 `7.2e-4 s` 归 HIGH、`43 ms` 归 LOW、压列界的 `48 ms` 仍阻断。复用此输入，加可成功人工核定和全清正例，验对应代次的审批发布。 |
| 真实合并与取证冲突 | `tests/test_table_value_pdf_binding.py` 覆盖候选行内竖线断开、重复值、落点贴边、错误单位；`tests/test_pdf_value_column_observer.py` 覆盖不可见文字、`ActualText` 替代、异常页框及预算。选与线上接入直接交叉的反例跑 Worker，保留其余定向回归。 |
| 在线控制路径的本地替身 | `tests/test_table_value_column_span_delivery.py:43–112` 已走正式 Worker、下载实际 Word、命中审批发布拒绝。其正例是预先修好的 HTML。第四阶段在正式入口复制现有用例外壳，让实际 Poppler 和 converter 处理跨列 HTML，替换范围限 MinerU 网络、预览和存储等环境依赖。 |

同名同文字不同 SHA 的仓库 P7 用作来源拒绝用例。完整缓存留在本地，测试以清单核验 PDF 和 v2 指纹。独立夹具可在可复现测试中自行构造。现有 PDF 错误字体字符映射的观察边界沿用第三阶段，保留为验证说明。

[第三阶段验收](../../11-15-table-value-pdf-binding/validation.md)
