# MinerU 正式发布与当前接入兼容性

- 核查第五阶段逐页比对是否需要同步升级 MinerU，及开源新版有哪些值得单独评估的能力。
- 范围含当前工作树、已保留的真实托管回包、MinerU 官方托管文档与开源发布。核查日期为 2026-11-15。

## 已发布的版本

GitHub 官方最新发布接口返回 `mineru-4.2.2-released`，于 2026-11-13 发布，`draft=false`、`prerelease=false`，标签指向 `0621ddbab8bf85294d6bac101c0a6def843195d8`。核对时 `master` 的 `f0497e0…` 晚于标签，提交说明为同步 issue 模板。用正式标签确认随版本发行的契约。 [最新发布 API](https://api.github.com/repos/opendatalab/MinerU/releases/latest) · [4.2.2 发布说明](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.2.2-released)

- 4.2.0 有 PDF 原文与结果区域双向定位、跨页来源可视化，并修复旋转页表格方向、表内图片与公式分配及跨页单元格拼接。4.2.2 主要补本地 VLM 故障传播、任务清理及批量输入错误处理。旋转/CropBox 与跨页表格可以纳入后续比较，具体值列是否改进仍需用相同原件对照实物和 finding。 [4.2.0 发布说明](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.2.0-released) · [4.2.2 发布说明](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.2.2-released)

## 当前代码与回包

| 位置 | 已核实的依赖合同 |
| --- | --- |
| `app/clients/mineru_client.py:34–37,72–126,159–175` | 用请求客户端访问 `https://mineru.net/api/v4`。申请批量上传链接后 PUT PDF，按 `batch_id` 查询 `extract_result`。托管文档仍描述该流程。 |
| `app/domains/document_jobs/mineru_execution.py:78–122,466–527,592–605` | 解析和归档复核任务、批次及 data ID。正式处理有历史单结果缺 data ID 的兼容分支。逐页比对需核验的来源身份由第五阶段另行实现。 |
| `app/services/document_ir/mineru_package.py:189–203` | 归档中先定位唯一的 `content_list_v2.json` 或带前缀的同名成员，缺 v2 时可读旧 `content_list.json`。两者均缺时为 `mineru_content_list_missing`。 |
| `app/services/document_ir/layout_signals.py:31,63–88,293–315,319–333` | 读 `layout.json` 或 `middle.json`，按旧结构的版本、页框和归一化范围解释 bbox。后续同文档取证定位唯一 layout，依赖 `pdf_info` 和按页的块，例如 `para_blocks`。 |
| `requirements.txt`、`requirements/locks/cp311-linux-amd64.txt` | 当前依赖未引入 `mineru` 或 `docvortex`。托管回包的 `_version_name` 为供应方产物标记。 |

保留的真实 P7、LOW/HIGH 托管 ZIP 均报告 `_version_name=3.4.4`、`_backend=hybrid`，含实际选中的 v2 和旧结构 layout。托管 API 的 `model_version` 公开选择有 `vlm`、`pipeline` 和 `MinerU-HTML`。开源发行版本与给托管账号返回的后端版本、文件合同分别验证。 [托管 API](https://mineru.net/apiManage/docs) · [隔离 Worker 实验记录](worker-acceptance.md) · [回包版本和 PDF 重写调查](mineru-upstream-rewrite.md)

## 4.x 接入评估

- 自托管 API Server、Router 与兼容服务的 `/v1/tasks` 接受 JSON 文件清单，逐文件发上传地址，使用服务端生成的 `task_id/file_id` 轮询，然后按 `files[].result_url` 下载。其状态、错误和结果模型需要专门适配。4.2.2 已移除未实现的 webhook 声明。已核对的托管 v4 则以批次和调用方 `data_id` 回显为中心。 [4.2.2 标签的 Tasks 合同](https://github.com/opendatalab/MinerU/blob/0621ddbab8bf85294d6bac101c0a6def843195d8/docs/en/usage/tasks.md) · [4.1 迁移说明](https://github.com/opendatalab/MinerU/blob/0621ddbab8bf85294d6bac101c0a6def843195d8/docs/en/reference/migration_4_1.md)
- 4.x Tasks 的默认 ZIP 包括 `markdown.md`、`middle_json.json`、`structured_content.json`、`images/`。Middle JSON 的协议为 `schema=docvortex.middle`、`schema_version=2.0`，正文以 `pages[].blocks` 为主。页面尺寸和来源页索引可从 PDF 的 `extensions.docvortex_layout` 读取。旧 `pdf_info`、`_version_name` 不在新合同内。SDK 渲染器支持导出 Content List V2，需要另验导出结构、图像、坐标和原始节点范围。根据当前选包代码，将 4.x Tasks 默认 ZIP 直接交给旧入口会缺少 content list。 [4.2.2 标签的输出合同](https://github.com/opendatalab/MinerU/blob/0621ddbab8bf85294d6bac101c0a6def843195d8/docs/en/reference/output_files.md)
- 4.x `files[].sha256sum` 是可选的输入 SHA-256，供服务端校验实际上传或下载的源字节，并可用于上传预检。命中缓存只复用源字节，各任务按本次参数解析。结果公开字段包含 `file_id`、执行版本和结果 URL，迁移说明明确完成响应不回显请求的 `sha256sum`。WebUI 双向定位和 DocVortex 页面索引可补来源位置，现有公开结果合同未提供绑定本项目托管 v4 本次上传 PDF 和 ZIP 的摘要证明。即使自托管能验上传摘要，数值列取证和 Word 逐格认证仍由本项目完成。 [输入校验与结果字段](https://github.com/opendatalab/MinerU/blob/0621ddbab8bf85294d6bac101c0a6def843195d8/docs/en/usage/tasks.md#creation-request) · [4.1 兼容变化](https://github.com/opendatalab/MinerU/blob/0621ddbab8bf85294d6bac101c0a6def843195d8/docs/en/reference/migration_4_1.md#http-api-replacement)

## 建议与边界

本次在现有托管 v4 链路完成原件指纹和逐页比对。同源路径只加强已有回包的身份核验及本地证据持久化，托管 HTTP 协议、已支持的回包结构和应用依赖保持现状。适配上游的触发点是目标托管账号的实际回包/API 契约变化，或明确选择自托管 4.x 后可验证的收益。

若触发迁移，单独增加相应协议的适配入口，按明确文件合同分派，沿用旧包读法。先在隔离环境验证上传和任务归属、状态恢复与结果租约、ZIP 结构与大小边界、图像资源、页序和坐标映射，再用相同 PDF 对照数值列、错配阻断与 Word 实物。相关依据为 [Word 生成规则](../../../../../spec/backend/word-generation-rules.md)、[质量规范](../../../../../spec/backend/quality-guidelines.md)，以及 `tests/test_mineru_download_boundary.py`、`tests/test_mineru_result_root_uniqueness.py`、`tests/test_document_ir_mineru_converter_layout.py` 和参数值列回归。

本次核查使用官方合同、固定标签及已保留样本。目标托管账号的新协议可用性、自托管 4.2.2 的实物收益与迁移工作量待该路径的独立验收。
