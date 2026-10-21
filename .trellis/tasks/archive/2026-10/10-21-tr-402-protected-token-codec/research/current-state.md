# TR-402 调查证据

## 1. 调查身份和范围

日期：2026-10-21，Asia/Shanghai。仓库 /Users/sc/PycharmProjects/md2word，分支 main，HEAD 4c40e6c52bde072a7ad3afab67eb425f757bd33c。

首条命令已执行 pwd 和 git status --short。原有 tracked dirty 为父任务 task.json、workspace/777 的 index/journal、CON-104 prompt、backlog 和 manifest；另有 SC1259、RND-504、TAB-307/308 及多份归档任务的 untracked 文件。创建前以 SHA-256 记录 386 个现存 dirty/untracked 文件用于收尾核对，不修改其业务内容。

已读取根 AGENTS.md、用户补充规则、RTK.md、workflow、backend/frontend/guides index；backend directory-structure、quality-guidelines、error-handling 和 document-job-mode-contract。已阅读用户指定的 11 份产品/实施/ADR/IR/翻译/测试/rollout 文档，以及 TR-402 完整 backlog 定义和既有 task prompt（后续实施段仅为证据，不是当前授权）。

读取父任务三份规划和 task.json，以及 BAS-001 的 task.json/验收记录/事实报告及相关研究结论。现有任务与基线记录足以回答历史事实，无需另读原始会话或调用跨会话全文索引。

## 2. 依赖和任务定位

- docs/implementation/codex-task-manifest.yaml:24：BAS-001=done，路径为 .trellis/tasks/archive/2026-10/10-12-bas-001-current-capability-baseline。
- 归档 task.json.status=completed，meta.human_acceptance 含 implementation/validation/residual_risks，commit=107624d7e87f8287c83020d9c751e9d54d23d855。
- git merge-base --is-ancestor 107624d7e87f8287c83020d9c751e9d54d23d855 HEAD 退出 0。
- manifest:276–287 的 TR-402 初始 todo，depends_on 只有 BAS-001，trellis_task_path=null。
- 全任务目录（包括 archive）按 slug/id/title 查找未发现 TR-402；父任务为 .trellis/tasks/10-12-datasheet-docx-delivery-quality。
- task.py create --parent ... --no-start 创建唯一子任务 .trellis/tasks/10-21-tr-402-protected-token-codec，状态 planning；没有执行 task.py start。

## 3. 正式链路

| 位置 | 已观察行为 |
|---|---|
| app/domains/translation/models.py:200 起 | TranslationTextItem 仅 id/text，frozen/slots；Request/Result 有 terms、prompt、batch 等字段，无 Token ledger。 |
| app/domains/translation/document_ir_translator.py:114–154 | 同步 translate 深拷贝 IR，拆批、调用 Provider、验证后累计 replacements，最后统一 apply。 |
| 同文件 :250–288 | build_provider_request 将传入 items 原样构造请求，术语基于原文匹配；没有 encode。 |
| 同文件 :435–517 | 抽取 text/list/html，公式 block 跳过；使用 strip；不显式抽取 captions/footnotes。 |
| 同文件 :519–528 | validate_result 只判断返回 ID 顺序与输入相等，不验证技术内容。 |
| 同文件 :530–569 | 回填 text/list/html；不做 decode。 |
| app/domains/translation/provider.py:128–170、:257–270 | 固定/绑定 Prompt 和 id/text JSON；输出 parse 会 strip；没有本任务 Codec。 |
| app/domains/document_jobs/execution.py:1180–1230 | 独立 Worker batch 重新抽取 items、构造 request、直接 Provider 调用、validate_result、登记 replacements；仅修改同步 translate 不能覆盖生产批次。 |
| 同文件 :1553–1576、:2502–2520 | fan-in 对账后回填；已有失败映射归属执行服务，本任务不改。 |

源码全文搜索 app/tests/scripts 未发现其他正式 ProtectedTokenCodec；核心配置、基础设施、OpenAPI、scripts/resources 未发现 protected token feature flag 或 DB/API 字段。TRANSLATION_PROTECTED_TOKENS_ENABLED 只在目标 rollout 文档中建议，不能声称当前已有开关。

## 4. legacy 能力及可复现反例

app/conversion/runtime/translation_runtime.py:21–27：有限正则保护 HTML 下标变量、若干数值单位和大写型号；:323–339 每个 protect_text 调用重新分配 PH_001，restore 用逐项 replace；:518–543 比较占位符集合，不比较次数。

本轮用项目 Python 直接调用现有函数的内联只读探针，无临时脚本落盘：

~~~text
source  = literal {{PH_001}} OPA228
encoded = literal {{PH_001}} {{PH_001}}
decoded = literal OPA228 OPA228
roundtrip = False
~~~

另一个探针输入：

~~~text
OPA228 25°C 0x0028[4:0] VCC1_VCO $V=IR$ https://example.test/v1
~~~

legacy 只保护 OPA228 和 25°C；地址、位字段、信号、公式、URL 未被保护。以 expected={{PH_001}} 验证返回 {{PH_001}} {{PH_001}} 时未抛错，证明集合检查接受重复。

正式服务只读反例：

~~~python
service.validate_result(
    [TranslationTextItem(id="i", text="Voltage 25°C")],
    TranslationProviderResult(
        items=(TranslationTextItem(id="i", text="Voltage 99°C"),)
    ),
)
# 实际返回 {"i": "Voltage 99°C"}，没有拒绝。
~~~

结论：不能标为现有能力完整满足，不建议 skipped_existing；也不在规划阶段修复 legacy 或正式业务路径。

## 5. 测试、API、DB、脚本和样本

- tests/test_translation_runtime_characterization.py:28–69、:166–197、:238–249 锁定旧 PH 格式/恢复和“丢失”检测，没有覆盖碰撞/重复；本任务保留，不为了新 Codec 改掉旧契约。
- tests/test_document_ir_translation.py:191–270 覆盖结构、资产、批次、顺序和审计调用；:130 等覆盖语言方向/Prompt。没有新 Codec 检测合同。
- 实际命令：PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_runtime_characterization。
- 实际结果：Ran 21 tests in 0.008s，OK（退出 0）；这是当前基线，不是未来实现验证。
- scripts/ops/check_release.py:28–64 选定现有 API/Renderer/资源等测试，未列新 Codec；无需为本任务提前实施 REL-701 发布门扩展。
- 已检查 docs/api/openapi.json 与 app/core、app/infrastructure 的 Token 相关引用，无新的 HTTP/DB codec 入口。新原语只需内部模型，不产生 migration 或状态机。
- tests/fixtures/p1_translation_samples/manifest.yaml 当前是 en2zh 的 3 个正式样本，不能等同四方向 translation-core。
- 已读取 component 样本 manifest 和公开最小化 OPA228 content_list。真实文本含 OPA228、3 nV/sqrt(Hz)、10 V/us；适合作为纯 Codec 的格式样本证据。计划复用正式 converter/extractor，临时 zip 在 TemporaryDirectory 内清理。

## 6. 文档与 seed 的可消解差异

产品 PRD FR-006、ADR-008、translation-design §7 要求技术内容保护；当前用户进一步明确字符/字节级恢复。

seed Prompt 中 en2zh 的 :52–66 允许翻译 $PACKAGE^{(1)}$ 内的人类词；ru2zh :52–67 允许 В/А 等单位本地化；zh2en 仍点名 PH_### 语法。这些是未来接线要版本化审查的实现差异，不是修改产品冻结决策的授权。

本任务不调用 Provider、不修改 Prompt/Profile/flag，选择原字符恢复满足当前请求，无不可消解的 PRD/ADR 冲突。未来接线若需修改绑定 Prompt，必须保留已有快照/seed 不可变，不可趁本任务顺手更新。

## 7. 调查结论和验证边界

采用独立纯内存 domain Codec 作为唯一新 owner，现有 TranslationTextItem 可复用；无需改 API/DB/状态/权限/generation，也无需新依赖。普通词误保护、重叠/碰撞、逐项次数及非递归恢复由定向行为测试约束。

尚未运行未来 Codec 测试（代码不存在），未运行 release/full suite、P1/runtime、真实模型、DB、浏览器或 Microsoft Word；本轮没有生产接线，不能报告生产技术保持率或正式四方向验收。全部缺口留在计划验收和相邻任务边界，不伪造已通过证据。
