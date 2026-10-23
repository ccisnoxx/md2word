# RND-503 全新实际实现独立复审

2026-10-23，用户要求全新 critical_reviewer 独立复审真实实现与测试，并授权主会话核实后修复和重验；不提交、不push、不归档。

## 本轮起点

- 新审查身份：`/root/rnd503_fresh_critical_review`（critical_reviewer，fork_turns=none），未复用此前审查者；只读，主会话负责事实复核、修复协调和记录。
- 实际分支：`md2word/RND-503`，HEAD1835263；IR-204=done、RND-503 manifest=review、Trellis=in_progress。未重新start，不提前done/archive。
- 开始前pwd/git status/branch及current已核对。当前294项业务来源与上轮冻结/B1正常构建清单完全相同；已有301真实链+13隔离legacy等证据可复用，不能因本轮审查时间经过而伪称新跑。
- 本轮保护快照：`/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd503-postreview-4bb63wbx`，含原索引binary patch、完整status和文件hash；原302项暂存删除及无关dirty不触碰。
- 审查重点：严格分组阈值/源序、caption-footnote绑定、历史三入口恢复、B1双向兼容回退；同时核对与这些路径有关的源独立重算、权限、不可变receipt/CAS/generation和隐私边界。

## 发现与主会话复核

全新审查者完成初审，确认3项P2，要求修复后复验。17项定向unittest及三份旧正常产物/B1互读在初审中通过；301+13项为旧日志核查，不冒称新跑。原始三反例由同一fresh reviewer复验通过；中断后最终独立复核及B1闭环见文末。

1. **P2：legacy无报告分支未在receipt选择前识别新图片标记。** `execution._get_existing_result_file` 只有发现任一图片/公式新字段才走共享validator；legacy记录（无document_job_result_protocol）若IMAGE_EVIDENCE_KEYS全集和formula_report/formula_summary全缺，普通单图或B1文件仍带新marker，却能通过旧evidence分支。主会话纯方法及完整execute探针确认：lookup返回word，shared validator会拒绝；完整执行最终failed/uploading/oss_failed，但原prepared_result=None已变成选中损坏候选，且未rerender。**不表述为直接成功发布**，实际影响是receipt前认证不一致及无效候选过早占用/物化。原missing_both_reports仅删report/summary而仍留计数键，未覆盖该分支。

   证据：`tests/tmp/rnd503/post-review/legacy-missing-all-probe.log`。已交Trellis implement最小修复execution与result_persistence测试，要求真删全部新字段、覆盖普通单图/B1、三入口错误映射/不重渲染/原receipt不变，并保留真实旧无marker件成功。实现已以3方法/10 subTest先失败后修复；result_persistence+依赖恢复28项通过（29.592s，/tmp/rnd503-postreview-recovery-regression.log）。原始反例已由原fresh reviewer复验，最终候选另有独立复核见文末。

2. **P2：混合原生双栏中的普通单图被提升为整页单栏。** page400×600，left_before→image_left→left_after→right_top→right_bottom属于一个two_col region；当前遇任何image就flush，实际two_col→one_col图片→two_col，报告columns=1且认证通过。B0原writer同输入保留完整two_col流。主会话独立结构探针：`tests/tmp/rnd503/post-review/mixed-column-single-image-probe.log`，已交实现修复，要求普通图/不确定顺序图不破坏原生栏、只消费一次，真实并排组仍保持atomic span，不重新判组。

3. **P2：布局表继承默认模板表样式的非零缩进而越界。** 主会话用合法模板TableNormal/tblInd=20000dxa生成，表无直接覆盖且evidence接受，日志`tests/tmp/rnd503/post-review/template-table-indent-probe.log`。已交实现显式固定零缩进/对齐，认证相关有效属性；必须兼容旧产物无direct tblInd但有效0，拒绝direct/继承非零。主会话另发现“新writer固定left”不能成为旧件硬条件，真实旧件center/right且零缩进仍在可用区内；实现补9形态direct/default/basedOn×left/center/right，先复现6个center/right误拒后修复。精确极小trHeight篡改可过也已确认，作为同一几何合同认证缺口补回归，未冒称另一个writer缺陷。尚无该模板的Word外观证据。

## 修复、复验和停止边界

如有确认问题，仅修复本任务范围内缺陷，按Trellis实现/检查代理流程推进，再由原审查者复验。未变更的成功证据复用；有影响的选择器/构建/预览按实际修改重跑。Golden缺认证/API、Microsoft Word和部署预览待验边界保留，不将其写成已通过。

## 兼容补核与排除的疑点

- 主会话提出并与fresh critical核对：旧无direct表定位且有效零缩进的center/right是合法历史形态，不能施加新writer left默认。实现9形态回归先确认6个误拒，已修复。
- fresh critical另发现旧pct/auto零缩进被dxa-only误拒；主会话核对[微软TableIndentation](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.tableindentation?view=openxml-3.0.1)确认这两类缩进值不生效，应按有效零位移解释，已交同owner最小修复，完成后刷新reader/B1和受影响验证。新writer仍dxa0，不放行非零dxa或未知单位。
- Trellis check提出style/trPr/trHeight=exact是否导致模板裁切的疑点。主会话实际生成baseline/exact-style两份模板/产物、LO导出PDF：pdftotext -bbox HTML完全相同，PNG SHA均`edf7faeb690399c3d951b20241ab756c28500081123932164f281cced50b909c`（tests/tmp/rnd503/post-review/row-style-probe）。[微软Word差异说明](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/36064a5b-267d-4a27-a567-453d8b96a5b3)明确Word不允许该样式子项。两位reviewer均撤回其作为确认缺陷的判断；不新增推测继承拦截，直接row精确行高拒绝保持。
- LO六份中性产物已生成并逐页查看。目标图对5/6、24/25、单图、mixed-column、large-indent-table各1页；图片边界及所属注释清楚。mixed-geometry为缺bbox的极端竖图：3页，已知图/正文位于第1页，极高竖图第2页，其普通caption/footnote第3页。未丢失/错绑，但keep链不能容下整组时无法保证同页；批准设计不引入字体/全书排版测量。独立critical确认属于已声明分页体验局限，必须保留Word人工验收，不能写成“全部单图/注释同页”。
- PDF辅助自动探针的fitz在项目venv与已配置bundled Python均未安装，未安装依赖；改用已安装pdfinfo/pdftotext/Poppler导出并实际查看全部8页PNG，不把缺失工具称为通过。六份最终PDF和PNG清单见tests/tmp/rnd503/post-review/previews/preview-inventory.json。

## 中断后的状态核对

主会话工具执行被中断后，原collaboration代理不再存活；未据此推断完成。继续核对实际文件和原日志，pct/auto生产修复已写入，但其新测试default样式有重复tblInd的fixture错误，image模块28项中2errors，不能写成通过。已交新的Trellis实现owner `/root/rnd503_compat_finish` 只修fixture并补已确认nil有效零位移兼容，不弱化重复属性拒绝。主会话实际加载修复前留存reader与同源模板/报告比较：dxa/pct/auto/nil旧reader都接受，当前仅nil误拒，见legacy-indent-unit-probe.log；[微软已知宽度枚举](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.tablewidthunitvalues?view=openxml-3.0.1)明确nil=No Width。

新的独立只读critical `/root/rnd503_final_critical_verify` 负责最终候选复验与刷新后B1指纹核对，保留原fresh critical初审/原反例修复结论的历史身份。原302暂存删除/dirty不变，继续保持manifest=review/Trellis=in_progress，未重新start，不提交/push/archive。

## 最后定位兼容复核

新critical独立内存探针确认type省略的有效零缩进误拒；主会话又以修复前reader和当前reader比较，type、w、两者三种省略均旧接受/新拒，见legacy-default-attribute-probe.log。[官方Type默认dxa](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.tablewidthtype.type?view=openxml-3.0.1)与[官方Width默认0](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.tablewidthtype.width?view=openxml-3.0.1)已实际核对。实现仅两处get采用已知默认，复用27个单位/默认subTest，修复前3failures/9errors、修复后image28/OK4.822s。nil及pct/auto/default fixture修复的失败和通过日志一并留存在agent-logs，未隐藏先前2errors。

另一探针仅因旧reader接受就把center/right+非零dxa称为有效零位移，主会话用[微软Word实际不忽略该缩进的差异说明](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/a129dffd-ef75-4faa-ab1f-47c3fd4cff26)核实后纠正，reviewer已明确撤回。非零dxa继续拒绝，不为兼容削弱当前Word几何保护；也不为已证伪的style trHeight加冗余guard。

最终冻结reader SHA=`3adce3b48164897de9d483be40df4487b36098aab204bbe408300729a9dc4dcb`，image测试SHA=`f85f3bcc426526be471fa1da87bc35fb91adb678550dab1676652bf292a44eab`。新critical已独立确认字节并实际跑5项受影响内存测试OK1.911s，覆盖27个单位/默认、9对齐、稀疏几何/删覆盖拒绝及mixed普通/uncertain；原23项其它关键合同证据复用，无残留确认代码阻断。最终B1和集中命令以本记录收口部分为准，不复用中间过期指纹。

## 最终复审结论与验证收口

最终独立critical `/root/rnd503_final_critical_verify` 已完成代码/内存测试/B1源码和实际产物补核，确认无尚未解除的代码审查阻断。三项原始P2及合法旧对齐、pct/auto/nil、type/w省略兼容均闭合；非零dxa/未知单位/重复属性/direct exact行高仍拒，阈值未放宽。原fresh reviewer23项与最终verifier23+5项内存测试存在重叠，不简单相加；主会话最终集中311项是单次独立通过。

| 最终实际验证 | 结果 | 原始日志（tests/tmp/rnd503/post-review/下） |
|---|---|---|
| 核心14个模块 | 311 tests / OK，40.943s | closure-core-unit.log |
| Component正式adapter | 1/1，当前仅OPA228 smoke | closure-component.log |
| Direct phase2-core | 5/5，P0=0；既有P1/P2backlog仍在 | closure-direct.log |
| Release/OpenAPI/前端静态合同 | 203 tests / OK，7.379s；164paths/324schemas，changed=false | closure-release.log |
| 实际B1隔离构建 | 7 tests / OK，13.280s，55subTest；B1读17份旧新产物，正常reader读新旧B1各1 | closure-b1.log和b1/child.log |
| task validate | exit0，implement/check各11条，无警告 | task-validate.log |
| git diff --check | exit0 | diff-check.log |

新normal来源清单SHA为`1b87278761248cb80c53eaf37c14b567dd0069baead6c3319ff4223998434bf3`；B1为`a5cfd2bd25437d26ddb9b208af52f12b9c08fbb46966e9f7a12b100dfb90e6d7`，各294项实际SHA均经独立复算，唯一区别为生成策略常量。实际B1模块/留存副本同SHA `5f8d75857937b338f1445bdce3d86a18296df8d5a0c46c1462215ca3e52e825a`。最终verifier另外在真正B1导入进程重读17份原IR/实际文件/原报告、normal重读2份B1全部通过；component/direct的实际DOCX SHA与各report也独立核对相符。主会话额外将18份当前/历史产物经最终reader重验并刷新artifact-hashes，不把重生成冒称旧件恢复。

首次13项isolated characterization成功证据复用，未与真实模块混跑或伪称本轮重跑；Golden缺认证/API的实际失败证据复用，未因无环境变化重复无效命令。未验Word、部署预览、真实MySQL/S3/MinIO和生产跨主机回退；B1 deployed=false。极高缺bbox图第2页/原注释第3页的已声明局限保留，未签字为所有图注同页。

更新的是7个业务/测试文件、Word Spec/DOCX设计、最小context及当前任务证据和RND-503 notes。没有公开OpenAPI/DB列/迁移/前端状态变更；私有image_geometries是可选差异，旧无键原hash不改。原generation/CAS/first-valid身份、错误映射、权限/审计/不可变/内容/路径/敏感事件边界未削弱；无新AI/OCR/外部调用。

准确任务仍`.trellis/tasks/10-23-rnd-503-image-group-caption-rendering`，manifest review、Trellis in_progress，等待人工验收和commit plan授权；未start其他任务、未stage/提交/push/archive。工作区最终保护见post-review-workspace-protection.json；原302暂存删除及无关dirty保持，批准v2三件套字节不改。
