# RND-503 最终复核

2026-10-23。主会话核实每项材料发现后修正；代理完成不代替主会话验收。业务/测试源码已冻结，最终来源指纹见b1-build-manifest.json。

## 独立持久化合同复核

`/root/rnd503_result_contract_review`（critical_reviewer）只读审查原IR/模板/格式输入绑定、源独立重算、三恢复入口、CAS/receipt/generation/隐私与B1。首轮六项确认问题：跨span源序、table空格去重、资源/尺寸降级自证、图片段额外正文、私有异常值泄漏、非有限bbox报告JSON往返。主会话逐项独立复现，实施者修正并加回归，审查者按原始探针复验全部关闭。

第二轮只读补核真实B1文件/清单hash/模块路径、三入口45subTests、正常构建旧件→B1及实际B1新件→正常reader两向验证，确认本地兼容成立，deployed=false。也核对最终301+13分进程、首轮314两错误留存及HEAD旧loader反证。结论：其审查范围内无新增确认缺陷、无未关闭代码阻断。

## Trellis完整scope检查

`/root/rnd503_trellis_check` 先加载全部受影响package及check context，审查本任务差异与已接受依赖差异，保持原302项暂存删除。确认tcW单位pct及图片源裁切/填充/翻转/旋转/内部偏移可绕过的两类OOXML认证缺口，主会话独立复现，交接文件所有权后checker局部修正image_evidence与test_image_group_rendering。

25 tests / OK，11.007s（`/tmp/rnd503-trellis-check-tests.log`），七类篡改拒绝和显式0兼容通过；27文件compile()、renderer/adapter/execution导入及diff检查通过；旧tabs图片writer/失去使用者helper搜索零命中。无额外lint/type配置/工具，未安装。checker最终冻结源码，无未关闭确认代码缺陷；critical_reviewer又只读核对这两项源码与回归断言。

## 实际客户端探针

主会话在正式adapter中性图对的LibreOffice预览发现真实裁切，独立核对模板继承缩进与DOCX/PDF几何。实施者用只改OOXML的对照证明省略inline距离会导入约9.05pt左右对象距；四距显式0恢复222.1pt完整clip，无任意缩放/epsilon。主会话实际复看修后PDF/PNG，两个图对四边完整，注释位置保持。段缩进归零、schema子序、四距与内外尺寸认证均有测试。

该探针不代签Word/部署预览；SEQ更新对非1起始/跳号的既有FIELD-002限制保持公开记录，不在本任务提前实现编号策略。

## 最终边界

最终真实链301/OK、隔离characterization13/OK、component1/1、direct5/5、release202/OK和OpenAPI current。首轮314两项既有stub隔离错误保留；B0 flags比较RS2G04候选数10→11已定位为原合并caption按要求拆为两个独立段，文本拼接逐字相等，其它flags一致，无未解释新flag。

Golden缺认证/API环境，Word/实际部署预览、真实MySQL/S3/MinIO和生产回退未验。这些不是已通过证据，也没有转为新增代码缺陷。最终仅manifest=review、Trellis=in_progress，不自动done/archive/提交/push。
