# 纯依赖中间树验证与提交分层

日期：2026-10-22。用户已验收TR-406并批准commit-plan.md，要求先重建验证纯依赖中间树，再执行两笔业务提交，不push、不归档、不记录会话。

## 重建与范围

- 起点：596a2de7ed29edb7fdb378d91c17bda09b7f1066；来源为CON-102 52810b6/4d30682、CON-103 bd828da（80b82db为验收复核记录）、CON-104 48c9402。
- 纯依赖树：7fb0acfa499e95cb87809157426b306490e3907b，恰好修改批准的60个路径。通过独立临时Git目录重建，没有覆盖主工作区或真实index。
- 41个非共享依赖路径与已验收候选逐字节一致；19个共享路径按内容分层，保留TR-403完整性/来源/脱敏/唯一物理身份，整合阶段/receipt/质量/下载资格。
- 没有提前加入TR-406 reducer、批次根安装/claim/snapshot、execution DTO、UI旧响应保护或3个新测试模块。OpenAPI为164 paths/323 schemas，最终候选为324 schemas。
- 主会话将该临时树的60个文件blob装入独立index，确认它到验收产品参考树9a56f1f6e1c85bec9feef8e61058f1dec2cb7321的31个差量路径只包含30个TR-406路径和manifest，没有范围外业务改动。

## 实跑验证与独立check

重建代理实跑132项后端、31 files/150项前端unit、build/vue-tsc、OpenAPI生成/check、release聚合检查（36 targets），全部通过。

独立trellis-check在冻结60路径上另实跑：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_delivery_state tests.test_document_job_delivery_state_api tests.test_document_job_delivery_state_migration tests.test_document_job_download_availability tests.test_document_job_download_availability_api
48 tests: OK

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_integrity_execution tests.test_document_ir_translation tests.test_generated_artifact_identity tests.test_document_job_modes tests.test_document_job_execution_stages tests.test_document_job_result_persistence
84 tests: OK

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q app tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/export_openapi.py --check
```

合计132项通过，OpenAPI无变化；无冲突标记，开始/结束60路径hash相同。前端和release按相同冻结hash复用，不宣称独立重复实跑。独立check结论：可以作为第一笔提交的纯依赖中间树。完整hash与结构化记录见dependency-intermediate-validation.json。

已有2项原始HEAD fake renderer callback失败不属于这132项，按已有证据保留，未扩大修复。该树不证明尚未进入的TR-406终态/claim合同。

## 完整树空白诊断

raw tree diff --check报告delivery_state.py:97有一个EOF空行；它与已验收候选一致。最终候选test_translation_batch_failure_semantics.py:1386也有同类EOF空行。此前工作树git diff --check不涵盖当时未跟踪的新文件，因此不将旧通过记录扩大为完整树无诊断。

为满足本轮最终结果与验收候选逐字节一致的明确要求，保留这两处格式字节。`git -c core.whitespace=-blank-at-eof diff --check`通过，没有其他空白诊断。未更改仓库配置或业务源文件。

## 风险复核与停止边界

独立critical reviewer复核通过：未发现本次重建引入的P1/P2/P3，第一笔可按授权执行。开始/结束60路径hash与Git blob均零差；19共享路径中13个与CON-104验收实现逐字节相同，剩余执行器/兼容测试/Spec差异已围绕真实diff检查。TR-403字节与evidence保护、receipt选定/物化、原子retry、阶段generation复查及权限owner保留；三adapter批次类AST仍与原HEAD一致，没有提前加TR-406窄端口。60路径有序映射汇总SHA-256为71503301cea0a6055da77777dbaf00d2067cd7dc98de23e466075e5e918bb6b7。该复核独立执行hash/blob/AST/实际差异检查，未冒充重复实跑132/150项测试。真实MySQL/InnoDB、部署文件系统锁、真实Provider/S3和Word人工证据继续保留为原有上线/人工门，本轮不连接、不部署。

## 第一笔实际提交

依赖业务提交：`0946326b0f457ef4b4f60895f17feb915d657c14`。提交树与上述冻结中间树完全相同，父提交为原HEAD；恰好60路径，无任务/archive/journal/manifest/backlog/prompt历史混入。提交后仅同步已提交路径的索引，原有6项已暂存删除的binary patch完整保留。
