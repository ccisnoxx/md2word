# Preview、持久化与产品合同调查

## 阅读范围与事实

已读取用户指定11份产品/设计/合同/实施文档；产品PRD FR-013、RND-505 backlog（449–459行）要求可降级同步定位，未要求像素分页；FR-015、ADR-010/012/015及质量发布设计仍要求预览存在、后端权威发布条件。RND-506视觉QA、QA-602公开查询、QA-603三栏UI均属后续任务。两项依赖已done；未发现要求改变冻结任务模式/下载/发布语义的冲突。

以下为8fa11d97已验收源，不是根目录现有运行能力：

- `app/services/preview/models.py:63–81` 的PreviewPage/PreviewResult只有PDF bytes、可选页图、零基page_index、page_count、provider/version/profile；没有文字位置或bookmark→page结果。
- `provider.py:7`端口只接收DOCX bytes和PreviewPolicy，不依赖IR/job。`executor_protocol.py:38–46`的ExecutorResult是extra=forbid的v1；不应偷偷扩展外部launcher输出并假装旧执行器兼容。
- `app/domains/document_jobs/preview.py:118–233`：receipt校验→claim→provider→begin_registration CAS→PDF/PNG→manifest→证据校验→finish CAS。源文件完整metadata在receipt中不可变。写入后不能补改主DOCX/主件metadata。
- 同文件208–215行`word-preview/v1`为普通JSON dict，已有安全来源/run/attempt/profile、文件descriptor及页数；292–387行读者按明确必需字段/所有文件绑定校验，允许不识别的附加JSON键。这是可选、独立版本page_mapping的兼容落点。
- `preview_state.py`复用CON-102同job序列化点，source_generation、result ID/hash、profile、current key、revision、run、attempt、lease、artifact_stage/confirmed_attempt决定唯一当前预览。RND-505不再建状态账本或重试接口。
- `preview.py:390–443`共享观测/可见文件/TTL验证；service文件列表与单件授权、router两S3签发路径复用。manifest是现有word_preview_manifest文件类型，可经现有授权下载，不需新HTTP路由或file_type。
- 文件内容通过FileUploadService登记，pending→uploaded、独立file_id key、不超过主件期限。file/SQLite/MySQL都以JSON payload保存；无新DB列是本任务的设计选择，不等于可忽略兼容/并发。
- `quality_state.py`独占word_preview质量贡献；映射缺失不能加入该贡献、阻止preview成功或恢复批准。
- 根requirements.txt没有PDF解析依赖；脚本搜索未找到正式bookmark→PDF页提取链。首版明确采用已有page_count的确定性推断，不新增PDF解析/OCR/外部引擎/文本匹配/Provider协议。

## 目标与最小落点

通用书签由renderer最终输出点生成；映射算法放services/preview/page_mapping.py（纯输入输出，不读取服务/仓储），从已选generated_word私有block evidence取得source spans/稳定ID，从独立可选block_anchor_evidence取得已认证的通用bookmark（修订2；不得从旧首名字段推定创建成功），应用preview.py构造身份并把映射放在已有manifest.page_mapping。该manifest本身是映射Artifact，独立schema与内容hash，不另建孤立sidecar或跨文件提交协议。

多页仅推断跳转页，confidence=low；单页预览且该block确有正文目标时可证明起始页为0，仍不证明bbox/视觉一致。页眉/页脚多页重复、长表覆盖页范围不能靠源页/section推成精确值。详design。

## 安全和失败边界

源PDF与主DOCX字节不被映射阶段修改；算法不打开源PDF，只使用既有可信来源投影。manifest保留完整受权ID与坐标，但事件/普通API摘要只用白名单计数/版本/原因，不回显自由ID、正文、路径、lease或actor/reason。

新增映射缺证据、超限、不可定位为本地diagnostic；manifest存储失败仍沿RND-504真实存储错误，不能降级成功。身份错误只拒绝mapping结果，不伪造最近页；已有DOCX/preview hash/权限错误继续原fail-closed。历史无映射不回填，不重新render，预览无变化。
