# RND-503 人工验收后的任务限定收口

2026-10-23，用户已明确接受实现、全新独立复审修复、实际验证证据，并接受列明残余风险与未验边界；授权按两次工作commit计划提交、manifest done及当前子任务归档，保留原302暂存删除和无关dirty，不push、不启动后续任务。该授权取代此前各文档的review/不提交阶段限制，不修改已批准v2三件套。

## 两次工作提交与Trellis记录

1. 接入已接受IR-201/IR-204最小依赖：20个源/测试/IR合同/授权fixture路径。共享evidence、execution、converter测试使用获接受的依赖集成镜像；mineru_content只追加六个选择/分类函数，AST已与17cde1f逐函数相等核对，保留当前RND-502公式owner。依赖集成测试候选不调用后续RND-503的legacy_image_docx helper，确保首笔可独立运行；第二笔恢复已验收的最终测试接线。不通过按整文件打包把图片实现夹入依赖提交。
2. 严格图片组与Caption：完整已验收的最终源/测试、Word Spec/DOCX设计，以及当前子任务规划/调查/审查/验证记录；包含全部复审修复与单位/省略属性兼容。manifest候选仅取RND-503条目，其他HEAD条目保持，不带入其他任务已有dirty。
3. 工作提交完成后以task.py archive --no-commit迁移当前子任务，completed及准确归档路径/manifest done另作Trellis bookkeeping提交；仅当前子任务source/destination与RND-503 manifest条目。
4. add_session.py使用禁用自动提交的干净journal副本生成当前会话，仅其新增会话和index增量另作journal提交；原CON-102未提交会话继续保留在工作树，不混入当前提交。

两次是获批准计划中的工作提交；归档和journal为项目finish-work规定的两个独立bookkeeping提交，主会话已在执行前说明。所有阶段均用独立Git index审查精确候选，提交后只同步当前提交相关index条目；原302删除的cached binary patch逐阶段相等。无关文件不stash、不覆盖、不删除，不运行后续start。

## 验证与证据复用

当前294项业务来源及最终reader/image测试SHA与已人工接受的post-review/B1清单一致，业务源码不再改动。复用最终311核心、203release/OpenAPI current、component1/1、direct5/5、实际B1七selectors/55subTests和17+2产物互读、六份LO八页实看及独立critical无阻断结论；13项isolated characterization为原成功证据。Golden缺认证/API、Microsoft Word、部署预览、真实MySQL/S3/MinIO与生产跨主机回退未验，人工接受边界不等于这些门禁通过；极高缺bbox竖图与注释可能跨页、SEQ更新编号限制和既有RS2G04风险保留。

本轮额外从第一笔独立index导出完整临时树，实际运行依赖集成8模块：174 tests/OK25.233s；日志tests/tmp/rnd503/closeout-dependency-tests.log。不会在工作树切换代码或改用业务兼容fallback来制造首笔可运行。最终cached diff --check和归档后context validate另记收口结果。

源/测试/文档完整清单及每笔tree/hash在本地保护快照与提交记录中保存；保护快照：/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd503-closeout-wkjgl6tp。父任务、RND-501、workspace原改动、backlog、CON-104 prompt及.serena不纳入工作或归档提交。

## 已完成的工作提交

第一笔依赖提交：`e1f5079b695047d95912a541fc00d40e505dfc60`，20个路径；独立树174项通过。共享原索引仅同步该20路径，原302项cached删除binary patch保持相等。第二笔将恢复全部已验收的最终实现和测试，不改业务字节。

第二笔功能提交：`67bc26db2586c264ca038f6f24e2d37714982c71`，49个路径。独立trellis-check对两笔实际候选树确认无范围/合同阻断：依赖20路径可独立运行，最终业务来源和v2三件套字节与人工接受快照一致；两笔均未包含原302暂存删除或无关dirty。

当前子任务由人工验收授权完成；归档使用`--no-commit`，归档后的context和manifest路径将同步验证。历史Golden/Word等未验状态保持原样，不把人工接受写成测试通过。

## 归档收口检查

`task.py archive <当前子任务> --no-commit`已完成，task.json为completed、completedAt=2026-10-23；manifest仅RND-503改为done/implemented及准确归档路径。归档后implement/check各11条validate通过，无警告；已批准v2三件套SHA保持。当前会话无active task，不启动后续任务。父任务文件及其他manifest条目与收口前工作树快照相等，原302暂存删除binary patch相等。归档提交继续使用独立index；会话记录单独生成和提交，原CON-102工作树journal增量保留。
