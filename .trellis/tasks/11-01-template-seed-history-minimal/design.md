# 技术设计：复用模板读取服务owner

## 边界

只改 `TemplateReadService.bootstrap_manifest_versions()` 和 `list_template_versions()`，复用已有payload/hash/path/response helper，不增加服务、wrapper或依赖。独立回归为 `tests/test_template_seed_history.py`；主会话更新必要Spec与任务记录。

## seed_collision

已有record时不校验同号bundled DOCX身份或持久化payload自洽性
仅对is_default_seed且真实路径在resources/templates下、又不在该模板/版本受管目录内的seed，核对payload template_id/version、docx_path/docx_sha256、非draft及record.snapshot_hash与持久化payload自身hash；冲突ValueError
复用现有payload构建和hash，保持缺失记录create-only及已有默认指针；已有disabled/superseded记录不恢复。

## history_listing

仅枚举受管vN目录与当前manifest版本，可能漏掉只由持久化payload引用的历史版本
按record payload解析当前版本路径，补回未列出的可解析整数版本，沿用响应构建、默认标识及降序排序
同一版本去重；对于目录中已有record的版本，也复用_template_version_path的payload优先规则，避免按目录首个DOCX覆盖记录身份；缺失资产返回exists=false。

## source_patch_limit

受管vN目录里有按文件名排序更靠前的残留DOCX，而该版本record.payload.docx_path指向另一份文件
原main及归档补丁均可能把列表文件名/hash显示为残留文件，与实际版本解析不一致
仅在read_service.py的列表路径选择处复用已有payload优先resolver，不新增服务、wrapper或文件清理。

## 精确保留合同

- manifest只登记seed；MySQL资源默认指针是版本默认唯一owner，已有默认不因启动或列历史而切换
- 缺失seed仍create-only登记published；重复启动不覆盖既有record，冲突仅报告不修复该record
- seed判断保留is_default_seed、bundled真实路径及当前模板/版本managed路径排除，保护自定义和替换默认模板上传draft
- 校验持久化payload自身snapshot hash，不将完整新manifest payload hash与旧record比较；名称/描述/策略元数据变化不覆写旧快照
- 历史列表中已登记版本的DOCX/YAML/render_policy及验证发布字段按原payload回显；生产版本解析器保持现状，既有严格YAML错误不放松
- 历史列表保留draft/published/disabled/superseded状态、默认标识、实际资产存在标记、去重与整数降序；补回逻辑不保存记录、不移动DB默认指针，legacy默认template_id懒初始化保持原行为
- API响应schema、admin权限、版本发布验证、生产任务draft限制及main v2/历史请求幂等保持现状
- 不修改仓库默认DOCX、manifest、YAML或默认指针，不复制归档默认模板，不新增迁移或兼容fallback
- 保持现有hash格式：持久化snapshot_hash/docx_sha256使用sha256:前缀，列表asset.sha256仍为现有裸hex；不新增schema或响应字段

## 实施约束

seed用resolve后的bundled路径和当前模板/版本managed目录排除；同号draft冲突，但身份有效的disabled/superseded不恢复。核对的是record.payload自身snapshot hash，不是完整新manifest hash；冲突不修复record。

历史列表对已有record统一调用 `_template_version_path`，无record的目录沿用原候选；补回时动态更新去重集合。不调用生产 `resolve_template_version` 代替列表路径选择，避免过滤draft/closed或触发生成授权。

生产解析器及其legacy回退保持现状；payload优先调整仅限列表展示和seed核对。没有DDL、数据重写或默认资源变更，回退只涉及本批代码。

## 回归夹具

使用临时目录的自有manifest、DOCX/YAML文件、真实TemplateReadService/ResourceVersionService及本模块最小内存仓储端口。遵守create-only与默认指针语义，不导入旧测试helper，不mock业务正向路径，不启动build_runtime/create_app或真实DB。

## 静态复核修正：整数版本索引

首轮新增模块13/13通过后，独立只读复核证实R6/R7交叉缺口：目录/manifest按str(int)查record，但补回按int去重，只有别名key "01"/"02" 时会被未登记候选遮蔽。此修正落实既有AC5/AC6，不改变范围。

仅在list方法内建立可解析整数record索引，三种来源共用。规范key str(version)优先，其他等价key沿仓储返回顺序首条保留；前者保持原目录/manifest的规范key优先语义。不改raw持久化key或生产解析器。补别名独有且与目录/manifest重叠的直接反例，并使canonical/alias不同payload，防止相同内容掩盖选择错误。

## 本次本地提交边界

本轮只将已经实现并复核的本批9个路径保存为一笔本地提交；源码、回归和Spec保持已审阅内容，不新增应用检查，不推送、合并或删除分支。其余工作区、索引及未提交内容独立保留。
