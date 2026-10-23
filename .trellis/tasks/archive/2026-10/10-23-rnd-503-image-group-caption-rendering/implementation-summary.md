# RND-503 实施摘要与待确认 commit plan

2026-10-23最新授权：用户已人工验收并接受列明边界，授权任务限定提交和归档；此前review/待授权内容保留为历史，当前收口以closeout.md为准。

2026-10-23，实际分支md2word/RND-503。实现已完成本地验证，manifest=review，Trellis=in_progress；尚未人工验收，不提交/push/archive。批准v2三件套字节保留，执行事实见implementation-preflight.md，完整AC映射/实际命令/失败与未验边界见implementation-validation.md。

## 实现结果

严格bbox图片计划→固定无边框布局表→各图完整caption/footnote→源IR/冻结输入/实际OOXML三方认证。已有能力不足，实际有实现增量，不建议skipped_existing。仅接入已接受依赖，不重做IR-204；源连续、全组阈值、不确定单图、inline比例、内容表原生化与原公式完整性保持。

独立持久化复核六项和Trellis检查两类OOXML缺口均由主会话核实修复，实际LO裁切也经对照定位修复。最终301真实链+13隔离legacy、component1/1、direct5/5、release202/OpenAPI current、实际B1双向恢复通过。Golden缺认证/API，Word/部署预览/真实存储/生产回退待验。RS2G04旧LaTeX残留与新候选计数变化已解释，不改质量阈值；FIELD-002更新编号限制保持列明。

无OpenAPI/generated types、DB/迁移/仓储写协议、权限/前端/状态机变化，无新feature flag或外部服务。保留CAS/generation/first-valid receipt/不可变和错误映射，图片报告与最小格式快照不入普通事件。新增及实改注释/docstring/开发错误用中文，机器字段/协议值保持英文。

## 实际修改清单

以下按本轮实施前工作树hash比较，包含已接受依赖集成；不把HEAD差异中原有journal/backlog/CON-104 prompt或302项暂存删除计入本任务。

### 原有文件的本轮改动

- `.trellis/spec/backend/template-layout-configuration.md`
- `.trellis/spec/backend/word-generation-rules.md`
- `app/conversion/docx_rules/mineru_content.py`
- `app/conversion/docx_rules/terminology.py`
- `app/domains/document_jobs/execution.py`
- `app/domains/templates/layout_config_schema.py`
- `app/services/document_ir/layout_signals.py`
- `app/services/document_ir/mineru_converter.py`
- `app/services/document_ir/mineru_package.py`
- `app/services/document_ir/models.py`
- `app/services/document_ir/table_annotations.py`
- `app/services/renderer/docx_quality.py`
- `app/services/renderer/evidence.py`
- `app/services/renderer/image_renderer.py`
- `app/services/renderer/layout_plan.py`
- `app/services/renderer/word_renderer.py`
- `docs/contracts/document-ir-contract.md`
- `docs/design/docx-rendering-template-design.md`
- `docs/implementation/codex-task-manifest.yaml`
- `scripts/dev/formal_mineru_conversion.py`
- `tests/test_conversion_sandbox_dev_tools.py`
- `tests/test_document_ir_layout_contract.py`
- `tests/test_document_ir_mineru_converter_layout.py`
- `tests/test_document_ir_word_renderer_layout.py`
- `tests/test_document_job_result_persistence.py`

### 本轮新增业务/测试/授权fixture

- `app/services/document_ir/artifact_validator.py`
- `app/services/document_ir/caption_reconciler.py`
- `app/services/renderer/image_evidence.py`
- `tests/test_caption_reconciler.py`
- `tests/test_mineru_artifact_validator.py`
- `tests/test_image_group_rendering.py`
- `tests/test_rnd503_dependency_integration.py`
- `tests/fixtures/component_pdf_samples/samples/source-redacted/datasheet/zk7044-caption-pair/mineru/content_list_v2.json`
- `tests/fixtures/component_pdf_samples/samples/source-redacted/datasheet/zk7044-caption-pair/mineru/images/neutral-1.png`
- `tests/fixtures/component_pdf_samples/samples/source-redacted/datasheet/zk7044-caption-pair/mineru/images/neutral-2.png`
- `tests/fixtures/component_pdf_samples/samples/source-redacted/datasheet/zk7044-caption-pair/mineru/layout.json`

### Trellis记录

仅当前子任务目录：批准规划/context、dependency-integration及指纹、preflight、实现/复核/验证、B1清单和质量差异/工作区保护记录；父任务与其它任务目录不纳入提交候选。Spec定向摘录小于32768字节，implement/check各11条。

## 待人工确认的 commit plan

1. 审查上述清单及当前子任务全部记录；不bulk stage，不带入现有302项暂存删除、workspace journal、CON-104 prompt、backlog、.serena、父任务或RND-501目录。原索引已有内容须在实际提交时单独隔离并再次核对，不能直接git commit把它们混入。
2. 建议将“接入已接受IR-201/IR-204最小依赖及兼容测试”和“RND-503图片分组/绑定/证据/恢复及文档”分成两个可审查commit；重叠evidence/execution/test文件须按依赖基线精确分层，不能凭文件整包分组。若人工偏好单个任务commit，只包含本清单，并在描述中明确依赖来源。
3. 候选提交文案：`feat(renderer): 严格图片组布局与题注绑定（RND-503）`。验证写本轮311核心/203 release/组件1/1/direct5/5/实际B1七selectors及17+2产物互读；13项隔离characterization为原成功证据复用；Golden与Word等未验如实保留。
4. 人工验收后才可另行授权提交；完成状态是否done/归档由用户决定。本轮不执行以上提交步骤，不push，不启动后续任务。

后续仅列出：RND-504预览、RND-505页映射、RND-506视觉门禁，既有FIELD-002字段更新编号与RS2G04风险复核；本轮未实现。

## 本轮全新实际复审收口

三类P2修复及单位/省略默认兼容补充已纳入同一RND-503未提交候选，详post-implementation-review.md。没有新增业务文件，新增/调整只在前述7个源/测试文件及当前任务/Spec/DOCX设计/manifest本任务notes。当前精确命令和结果见post-review-validation.json，首轮数字保留为历史。现有commit plan仍待人工确认，两commit建议的第二个包含所有复审修复，不另制造已提交修复历史。仍排除302暂存删除、其它任务及原dirty；不stage、不commit、不push、不archive。
