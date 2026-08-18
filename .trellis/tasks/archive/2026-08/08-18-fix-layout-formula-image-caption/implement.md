# 实施计划

## 前置条件

- [x] 用户审阅并明确批准本 PRD、设计和实施计划。
- [x] 运行 `task.py start` 后再修改产品代码。
- [x] 实施前加载 `trellis-before-dev` 与相关 backend spec。

## 实施步骤

1. [x] 在现有 characterization tests 中加入失败用例：
   - 稳定双栏区间不包含上方单侧标题；
   - 普通双栏与目录产生 `w:cols w:num="2"` 和 column break，不产生布局 1×2 表格；
   - SC2167 形状的“通栏标题/说明 + 2×4 图形”区域顺序正确。
2. [x] 在 `app/services/renderer/layout_plan.py` 收紧稳定双栏范围；在 `word_renderer.py` 以 continuous sections 和 column break 替换正式 `two_col` 布局表格，删除正式路径废弃的 layout-table 调用。
3. [x] 为公式加入失败用例：
   - 公式 block 的 `\frac {(FCW \times f_{CLKIN})}{2^{15}}` 生成 `m:oMath/m:f/m:sSup/m:sSub`；
   - HTML 表格中的相同结构走 OMML；
   - 普通内联 `\times` 输出 `×`；
   - 畸形结构保留残留并被质量分析标记。
4. [x] 在 `text_semantics.py` 补共享 `times` 映射，在 `app/services/renderer/text_renderer.py` 实现最小 OMML 解析/构造，并从公式 block、普通内联与表格单元格共享入口调用；扩充 `docx_quality.py` 残留检测。
5. [x] 为图片加入失败用例：窄 bbox 不再被放大到 45%，嵌入媒体字节不变，settings 含 `w:doNotAutoCompressPictures`。
6. [x] 在 `app/services/renderer/image_renderer.py` 删除固定最小视觉宽度，在 `word_renderer.py` 集中写入 DOCX 图片/字段 settings。
7. [x] 为题注加入失败用例：中英文图/表题注生成独立 `SEQ` 域，初始结果保留，非编号说明无域，字段自动更新设置存在，长表续题不重复递增。
8. [x] 在 `app/services/renderer/text_renderer.py` 实现唯一 caption field helper，让 `table_renderer.py` 和 `image_renderer.py` 复用；保持题注位置、样式、长表续题和表注顺序。
9. [x] 为原生目录和交叉引用加入失败用例：
   - 目录写入带 1–3 级大纲、超链接和 outline-level switches 的 `TOC` 域，不保留源静态页码；
   - 图表题注含唯一书签，正文及表格中唯一匹配的引用生成带超链接的 `REF` 域；
   - 重复、缺失目标和非引用文本保持原文，不生成损坏 field；
   - `updateFields=true` 同时覆盖目录、题注和引用。
10. [x] 在一次 `render_to_bytes()` 内预扫描唯一题注目标，向正式文本渲染入口传递局部引用映射；实现 TOC/SEQ/bookmark/REF 的最小 OOXML helper，不在 renderer 实例保存状态。
11. [x] 追踪 `app/conversion/runtime/*` 的剩余真实调用者和兼容合同；仅当仍受支持路径必须满足同一输出语义时，同步最小改动并复用 `text_semantics.py`，否则记录未改原因。
12. [x] 运行定向测试并修复仅由本任务引起的失败。
13. [x] 使用用户提供的 `/Users/sc/Downloads/mineru_raw_result.zip`，经正式本地转换脚本生成新 DOCX；结果包和生成文件均不提交到仓库。
14. [x] 用 LibreOffice→PDF→PNG 标准链检查“典型性能参数”、示例公式、低分辨率窄图、题注、目录和正文引用，并检查 OOXML：
    - 原生双栏/列分隔符；
    - OMML 分式与上下标；
    - `TOC`、`SEQ`、bookmark、`REF` 域和 settings；
    - 无 `\frac`、`\times` 残留；
    - 无布局 1×2 表格。
15. [x] 运行 Trellis 质量检查，检查 diff 无兼容开关、重复实现、无关改动或静默回退。

## 增补实施步骤

16. [x] 为 MinerU 图注失衡组加入失败用例：严格条件成立时按图片顺序/题注编号重配；数量不等、编号不连续或已一图一注时保持输入。
17. [x] 在 `MinerUToDocumentIRConverter` 的原始 block 归一化阶段实现唯一的守卫式图注重配，不向 renderer 添加页码或文案特例。
18. [x] 为 `\overline`、`\mathbf`、`\boxed`、`\bigotimes`、明确基底的拆分 `_`/`^` 加入公式块、标题/正文、HTML 单元格失败用例，并保留畸形输入残留用例。
19. [x] 扩充现有 `_OmmlParser` 和共享单符号映射，生成 `m:bar`、数学粗体、`m:borderBox`、U+2A02 与正确 `m:sSub/m:sSup`；不增加数学依赖或第二套表格 parser。
20. [x] 复用既有空 table placeholder 判定，让正式 MinerU→DocumentIR 合并真实续表占位；删除同方向 IR 页的无条件分页符，保留方向变化 `NEW_PAGE` 与双栏 `CONTINUOUS`。
21. [x] 在 `TemplateFooterConfig`、字段 schema 和 v2 示例配置增加 `left_text/right_text`；实现单段落 `w:ptab` + 可选原生 `PAGE` 页脚，并确保自定义配置不被源页装饰覆盖。
22. [x] 更新前端页脚预览以显示左文字、可选页码和右文字；复用 schema 驱动表单，不增加专用 API 或状态。
23. [x] 运行增补定向测试，重新转换 SC2167，并在 WPS 与隔离 LibreOffice 中检查图 3–10、六类公式、正文空白页、纵横/分栏相邻页及自定义页脚。
24. [x] 运行 `trellis-check`，更新质量规范和真样本验收记录。

## 推广封底过滤增补步骤

25. [x] 为共享末页判定加入失败用例：SC2167 形状的“明确扫码/小程序行动文案 + 真实 image/figure 资产 + 无实质技术结构”命中；单个关键词、无资产、方形技术图、免责声明、版本表、编号标题/题注、公式/表格/列表和非最后页均不命中。
26. [x] 在 `app/conversion/docx_rules/mineru_content.py` 复用现有递归文本/资产抽取实现单一保守纯判定；不增加依赖、配置开关、模糊评分或第二套关键词。
27. [x] 在正式 `MinerUToDocumentIRService._convert_blocks()` 的 pages/blocks/assets 构造前删除命中页，并确保 `DocumentIR.pages`、blocks、assets/image_assets 均不保留该 page index；写入 `final_promotional_page_filtered:<page_index>` quality flag。
28. [x] 在仍受支持的兼容 MinerU 输入适配路径复用同一纯判定，补最小 characterization test，确保两条路径不会产生不同推广页策略。
29. [x] 使用 `/Users/sc/Downloads/mineru_raw_result.zip` 经正式本地脚本重新生成 SC2167，验证末页推广文案和二维码资产消失、无空尾页、其余页面/图片/公式/图注不回归；同时运行 TPL51200、BL0942、RS2G04 可用负样本或等价合成负样本。
30. [x] 运行推广页增补定向测试、现有必需测试和 `trellis-check`；通过后更新质量规范与最终验收记录。

## 实施记录

- 使用 `/Users/sc/Downloads/mineru_raw_result.zip` 经正式本地脚本和 `datasheet_template_v2.yaml` 重新生成 `/Users/sc/Downloads/SC2167_native_word_verified.docx`；SHA-256 为 `f72808f0b6299e7c00040c62756afd85ab305a2de421d905856f96f077706893`。
- 先前两个隔离 LibreOffice profile 均渲染为 42 页，但“无空白页”结论使用了包含页眉页码的整页文本判定，属于假阴性。增补复查确认 LibreOffice 第 17 页正文为空、第 18 页正文仅有误识别版本文字；本机 WPS 也直接复现空白/近空白页。
- OOXML 确认 4 个原生双栏 section、4 个 column break、29 个真实数据表且无布局 1×2 表格；144 个 OMML 公式、3 个分式、14 个上标和 137 个下标，目标 `2^15`、`f_CLKIN` 结构正确且无 `\frac`、`\times` 残留。
- 题注与引用确认 19 个 `SEQ 图`、24 个 `SEQ 表`、43 个书签及 24 个有效 `REF`；源包没有目录输入，因此真样本不生成 TOC，合成用例验证了检测到目录时的原生 TOC。
- 25 张正文图片与 MinerU 输入字节一致，另含 1 张模板 Logo；窄图约 222 DPI，正文图片最低有效分辨率约 145 DPI，并启用 `w:doNotAutoCompressPictures`。
- 必需自动化验证共 59 项通过；另有 73 项既有文本、版面与表格 characterization tests 通过，改动文件通过 `py_compile` 与 `git diff --check`。
- MinerU 在源页索引 11 已把部分曲线题注合并到错误 image block；增补方案将在严格数量/编号守卫成立时于 converter 边界重配，renderer 仍不按页码或文案猜测。质量扫描报告的 `_{DD}`、`\overline`、`\mathbf`、`\bigotimes`、`\boxed`、`_{TRACK}` 同步纳入增补 OMML 范围。
- 可选后端套件此前观察到 8 项与当前差异无关的既有模板状态/MinerU callback 测试配置异常，未越界修复。
- 用户复查后新增四项阻塞：图注错配、六类公式残留、多个正文空白页和可配置左右页脚；此前生成文件不再作为最终验收成品。
- v3 是已淘汰的中间候选；逐行 continuous 分节在 WPS 中触发栏平衡并把纯图片网格拆成多页。最终改为严格守卫的单栏原生 25%/75% 中心制表位行，普通文字或多题注双栏仍使用一次 `w:cols` + column break。
- 最终候选 `/Users/sc/Downloads/SC2167_native_word_addendum_verified_v6.docx` 的 SHA-256 为 `12fc1fb481d7ad579a40131ce675271f2c7995428c871bf6983787173552cfcf`。正式 converter 已把源页 9/10 的 `type=table + img_path=""` 空续表并入表 3，并把源页 11 的图 3–10 重配为 8 张曲线的一图一注；图 3–10 以完整 2×4 网格保持在同一页。
- 最终 OOXML 含 `m:bar=126`、数学粗体 `m:sty b=3`、`m:borderBox=1`、U+2A02 `⨂=2`、`m:sSub=143`，六类增补 TeX、原 `\frac/\times` 及字面 `</td>` 残留均为 0；同方向物理页 `w:br type=page` 为 0，且 `w:doNotAutoCompressPictures=true`、`w:updateFields=true`。
- 隔离 LibreOffice 渲染最终候选为 35 页，按正文裁剪逐页检查无空白页；图 3–10 完整集中在一页且题注与曲线对应。WPS 最终重排为 31 页，图 3–10 完整集中在第 13 页，抽查原第 17/18 页附近均有正文，未再复现空白页；示例激励频率公式保持上下分式、乘号和上下标结构。
- 自定义页脚样本 `/Users/sc/Downloads/SC2167_native_word_footer_demo.docx` 使用 `版本号：V1.1`、原生 `PAGE` 和 `www.ic-helps.com`；WPS 实测左/中/右按页边距正确对齐且无布局表格。LibreOffice 26 不展开标准 `w:ptab` 的相对 margin 位置，因此页脚视觉以 WPS/Word 为最终互操作验收。
- 增补必需自动化验证及页脚 API 往返共 80 项通过，相关 characterization tests 73 项通过，前端 `vue-tsc --noEmit`、`npm run build`、Python 编译与 `git diff --check` 通过。定向 Playwright smoke 已通过新增字段可见断言，但其既有“保存后重新读取 version=2”请求未被 mock 拦截，最终在既有“创建验证任务”断言处失败；未把该无关 mock 缺口纳入产品修复。
- 推广封底过滤在共享 MinerU 内容规则中使用“明确 CTA 组合 + 可解析的 image/figure 资产 + 无表格/公式/列表/编号标题题注/长正文”的全量守卫；正式 DocumentIR 和兼容输入均调用同一判定，未增加依赖、配置或评分分类器。共享规则、正式 pages/blocks/assets 删除、物理末页优先、无 layout 回退和兼容 v2 路径共 38 项定向测试通过。
- 正式本地脚本生成 `/Users/sc/Downloads/SC2167_native_word_promo_filtered_verified_v7.docx`，SHA-256 为 `eef39e4810371b97be144c2c76b3ab575c1d870e1de65185b22931173193d081`；对应 DocumentIR 为 33 页（索引 0–32）、383 blocks、24 assets，并含 `final_promotional_page_filtered:33`。推广文案、二维码源资产哈希均未进入 DocumentIR/DOCX；隔离 LibreOffice 渲染为 34 页且无文本空白尾页。
- v7 相对 v6 只少 1 个 media；`oMath=257`、`m:bar=126`、`m:borderBox=1`、`m:sSub=143`、`m:sSup=14`、`SEQ=43`、`REF=24` 全部保持一致。TPL51200、BL0942、RS2G04 三个正式负样本分别保留 18、32、13 个物理页，均未产生推广页过滤质量标记。
- 独立 `trellis-check` 补齐兼容 legacy 回归与稳定质量规范后，推广页定向测试和现有必需门共 111 项通过；SC2167 再次得到 33 个 DocumentIR 页面（0–32）、383 blocks、24 assets 与 `final_promotional_page_filtered:33`，二维码源哈希未进入 IR/DOCX。v7 SHA-256 仍为 `eef39e4810371b97be144c2c76b3ab575c1d870e1de65185b22931173193d081`，隔离 LibreOffice 复核为 34 页且末三页均有正文；未在本轮重复声明 WPS 视觉结果。

## 必需验证

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_mineru_converter_layout \
  tests.test_document_ir_word_renderer_layout \
  tests.test_template_layout_config_schema \
  tests.test_golden_sample_manifest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics
```

SC2167 正式转换后的标准视觉检查使用：

```bash
soffice --headless --convert-to pdf --outdir <temp-dir> <generated-sc2167.docx>
pdftoppm -png -r 144 <temp-dir>/<generated-sc2167.pdf> <temp-dir>/page
```

同时在本机 WPS 打开新文件，更新字段后检查状态栏总页数及逐页正文；空白页检测需忽略页眉、页脚和页码区域。

## 可选全量验证

完整后端套件覆盖大量外部配置与历史功能，本任务不把其环境性或既有失败作为交付阻塞；发布准备时可运行：

```bash
.venv/bin/python -m unittest discover -s tests
```

## 风险文件与回滚点

- `app/services/renderer/word_renderer.py`、`layout_plan.py`：section/column 顺序、页眉页脚链接和 render-local 引用目标。
- `app/services/renderer/text_renderer.py`：OMML、TOC/SEQ/REF 与普通富文本回归。
- `app/services/renderer/table_renderer.py`、`image_renderer.py`：题注位置、图片宽度和表注顺序。
- `app/conversion/docx_rules/text_semantics.py`：两条渲染路径共享的公式符号语义。
- `app/services/renderer/docx_quality.py`：质量标记口径。
- `app/services/document_ir/mineru_converter.py`、`layout_signals.py`：图注关联和空续表输入归一化。
- `app/domains/templates/layout_config_schema.py`、`resources/template_configs/datasheet_template_v2.yaml`：页脚配置合同与旧配置兼容。
- `frontend/src/pages/WordPageStyleDetailPage.vue`：schema 驱动页脚预览。

每一步保持可独立回退；不修改 DocumentIR schema、公开 endpoint、数据库或持久化形状，只给现有配置模型增加带默认值的可选字段。
