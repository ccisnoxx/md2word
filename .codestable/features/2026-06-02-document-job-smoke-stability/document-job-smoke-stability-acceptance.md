---
doc_type: feature-acceptance
feature: 2026-06-02-document-job-smoke-stability
status: accepted
summary: 验收 hostdzire 真实部署环境中 gs-003 / OPA228_P1.pdf 的上传、建任务、Worker、MinerU、下载主链路 smoke。
tags: [document-jobs, golden-sample, smoke, pdf-to-word]
accepted_at: 2026-06-02
roadmap: pdf-to-word-delivery-hardening
roadmap_item: document-job-smoke-stability
requirement: fastapi-backend-productization
---

# document-job-smoke-stability 验收报告

> 阶段：阶段 3（验收闭环）  
> 验收日期：2026-06-02  
> 关联方案 doc：`.codestable/features/2026-06-02-document-job-smoke-stability/document-job-smoke-stability-design.md`

## 1. 接口契约核对

本 feature 不修改 document job API、Worker、MinerU callback 或 Golden Sample 脚本合同，只用现有接口做真实部署 smoke。

- [x] 上传接口：Golden Sample 脚本通过现有 upload-url / content upload 完成 PDF 上传。
- [x] 建任务接口：`POST /api/v1/document-jobs` 使用 `mode=direct_pdf_to_word` 创建任务。
- [x] 查询接口：脚本轮询 `GET /api/v1/document-jobs/{job_id}` 得到最终 `succeeded/completed`。
- [x] 下载接口：`download-url` 和临时 `download` 均返回成功。
- [x] 报告层：`report.md` / `report.json` 记录 `gs-003` succeeded、Word 可打开、耗时约 16.559 秒。

## 2. 行为与决策核对

- [x] 使用真实部署链路：hostdzire API、worker、MySQL、Redis 和 MinerU 配置参与执行。
- [x] 使用正式样本：`gs-003 / OPA228_P1.pdf` 来自当前 Golden Sample manifest。
- [x] 卡点定位结果：未卡在上传、建任务、Worker、MinerU、DocumentIR、Word 渲染或下载任一 stage。
- [x] 只读检查网络边界：DMIT/hostdzire WireGuard handshake 正常，nginx 和 firewall 状态已确认，未修改线上配置。
- [x] 明确不做：未修改 renderer/layout/DocumentIR 业务代码，未修排版，未扩 API。

## 3. 验收场景核对

- [x] hostdzire readiness：API readiness 返回 `status=ok`，mysql backend、external worker、local object artifact、MinerU token/callback/uid 和 PDF submission 均可用。
- [x] Docker Compose：`api` healthy，`worker` up，`mysql` / `redis` healthy。
- [x] 网络边界：DMIT 和 hostdzire 的 `wg0` 均有近期 handshake；hostdzire Docker DNAT 暴露 `127.0.0.1:18000 -> api:8000`。
- [x] 真实 Golden Sample 回归：容器内 run dir 为 `/app/tests/tmp/golden_sample_runs/20260602T071017Z`。
- [x] 回归汇总：manifest 样本数 12，正式匹配 PDF 数 1，实际执行 1，缺少 PDF 11，orphan PDF 0，成功 1，失败 0，成功率 100.00%。
- [x] 样本结果：`gs-003 / OPA228_P1.pdf` succeeded，`job_id=docjob_d4c4101592ad`，Word 可打开，产物 `gs-003-docjob_d4c4101592ad.docx` 为 123407 bytes。
- [x] Worker/MinerU 证据：日志显示 worker 收到 `document_jobs.run`，下载 MinerU raw result，生成 `document_ir_file_id=file_330dd8333d11`，最终 `result_file_id=file_35a5e9c43885`。
- [x] 下载证据：`/document-jobs/{job_id}/download-url` 和 `/document-jobs/{job_id}/download` 返回 200。

## 4. 术语一致性

- `真实 smoke`：本报告和 design 均指真实 API + worker + MinerU 配置，不是 dummy bearer inventory smoke。
- `runnable sample`：当前只有 `gs-003 / OPA228_P1.pdf`，不包含缺失 PDF。
- `P0 正式验收`：仍要求 10-20 份样本核心链路成功率 `>= 90%`，本轮 1/1 只说明主链路 smoke 通过。

## 5. 架构归并

本 feature 不改变后端架构，只验证已有部署链路：

- API/worker/mysql/redis 的部署形态不变。
- MinerU callback 与 document job 执行链路不变。
- DocumentIR 和 Word renderer 数据结构不变。

无需更新 `.codestable/architecture/`。部署域名文档与现场 nginx `server_name` 不一致的问题属于后续部署文档校准，不在本 smoke 内修改线上配置。

## 6. requirement 回写

关联 requirement 为 `fastapi-backend-productization`，当前状态已是 `current`。本 feature 只验证已实现能力在真实部署环境可运行，不改变能力愿景、用户故事或边界，因此无需更新 requirement。

## 7. roadmap 回写

- [x] `pdf-to-word-delivery-hardening-items.yaml` 中 `document-job-smoke-stability` 从 `planned` 回写为 `done`。
- [x] `pdf-to-word-delivery-hardening-roadmap.md` 子 feature 清单同步为 `done`。
- [x] roadmap notes 明确本轮结论：主链路 smoke 成功，P0 正式验收仍受样本数量阻塞。

## 8. attention.md 候选盘点

候选但本轮不擅自写入：

- 线上 Golden Sample 复跑不能假设部署容器内已有 `tests/fixtures/golden_samples/`；本次是临时拷入 API 容器执行。
- 部署文档使用 `md2word-api.962850.xyz`，现场 hostdzire nginx `server_name` 为 `md2word.962850.xyz`，后续需要校准公开入口文档。

## 9. 遗留

- 本次 smoke 是容器内临时补齐脚本/fixtures 后执行，不是持久化 CI 或部署运行方式。
- 当前正式可运行样本仍只有 1 个，不能完成 10-20 份 Golden Sample P0 正式验收。
- 下一步应先查看本次生成 DOCX 的结构质量，或继续补齐更多正式 PDF 样本；不需要继续排查上传、Worker、MinerU、下载链路。
