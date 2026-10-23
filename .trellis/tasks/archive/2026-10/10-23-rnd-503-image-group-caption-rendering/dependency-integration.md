# RND-503 已接受依赖集成与实施前置（2026-10-23）

用户本轮已明确接受v2和独立复核结论并授权实施。manifest IR-204=done，无其它in_progress任务，三件套SHA与reviewed_v2_sha256一致。实际分支已从md2word/RND-502切到md2word/RND-503，HEAD仍1835263；原302项暂存删除及其它dirty已保存快照，未stage/覆盖/提交。

## 集成来源与边界

只复用已接受IR-204最终提交17cde1f及其已包含的IR-201输入安全闭合代码：document_ir的models、mineru_package、layout_signals、mineru_converter、table_annotations、artifact_validator、caption_reconciler取该接受快照。现有integrity未变；不引入IR-205/TAB/新状态或第二解析链。

共享mineru_content只追加接受快照的六个字段选择/分类/列表纯函数及Literal类型，**保留当前RND-502的clean_text、math run和footnote数学边界**。renderer evidence只移入已接受的build_renderer_metadata，不覆盖当前公式库存/报告验证。execution仅为三个已接受依赖摘要键补明确历史兼容：旧文件未保存该键时不强求新摘要；原来有该键继续等值比较，核心必需字段完全保留。未整体替换执行器/仓储/翻译树。

测试复用接受版本的validator、reconciler、layout contract及新增converter方法；原RND-502已有测试不覆盖。converter旧helper默认写fake-image及少量chart/body/qr伪字节，现真实解码会拒绝，改为中性可完整解码PNG；注释数学断言保留当前$\\pm$边界，缺公式改为接受IR-201更早的mineru_block_payload_invalid失败，未放宽任何输入门禁。此前失败及修订后验证分开记账。

图5/6去标识fixture只复用180c90a已授权caption-pair目录的四个文件，保留原错配内容，不导入其它样本任务或业务。原授权/provenance见planning研究；输出DOCX不入库。

## 实际验证

原树先运行renderer layout、converter layout、IR contract、formula、result persistence、job modes、local adapter七模块：165 tests / OK，17.307s。

接入后首轮173项检查发现1项旧数学预期差异和13项输入伪图片/较早公式错误映射适配；后续定向确认helper仍默认fake-image并修正，不通过重试掩盖问题。最终运行：

```bash
.venv/bin/python -B -m unittest tests.test_mineru_artifact_validator tests.test_caption_reconciler tests.test_document_ir_layout_contract tests.test_document_ir_mineru_converter_layout tests.test_formula_rendering tests.test_document_job_result_persistence tests.test_document_job_modes tests.test_rnd503_dependency_integration
```

exit0，**174 tests / OK，21.469s**。新增dependency integration一项测试含12个subTest，分别验证缺字段、显式None、原IR非空但旧evidence忽略、原evidence已保存非空四形态在legacy/明确跨代历史指针/receipt三入口成功恢复且不重新render；子案例不加到174测试数中。原公式篡改、结果竞争及状态权限测试也通过。日志位于系统临时目录，不是发布证据。

## 基线身份与后续门

用户禁止本轮提交，故不创建“含依赖的B0提交”。B0准确身份是**HEAD1835263 + dependency-integration-hashes.json中的未提交集成文件SHA**；已接受依赖并未进入当前HEAD祖先，不能声称已cherry-pick/merge提交。共享索引保持原字节；实现前镜像保存在本轮系统临时快照。该表示仅用于开发差异和定向回退，不改变v2的B1部署兼容合同。

以上集成门通过后才start RND-503并实施图片布局。新报告/B1/Word/预览/Golden尚未验证；最终依赖差异与本任务差异分别列入commit plan，不自动提交/push/archive，不改变IR-204或其它任务状态。
