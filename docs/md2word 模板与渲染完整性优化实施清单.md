# md2word 模板与渲染完整性优化实施清单

以下内容可以直接作为 Codex 的任务说明。实施目标是**补强现有模板、资源快照和渲染质量闭环**，不是新增另一套模板系统。

---

## 1. 当前实现基线

Codex 开始工作前，应先确认当前 `main` 的 commit SHA，并以该提交为实施基线。

当前模板机制如下：

```text
resources/templates/default/datasheet_template.docx
    └── 承载 Word 模板本身、页眉、页脚、公司 Logo、Word 样式等

resources/template_configs/datasheet_template_v2.yaml
    └── 承载页面设置、字体、字号、颜色、间距、表格样式等渲染配置

resources/template_configs/templates_manifest.yaml
    └── 将 default@2 绑定到上述 DOCX 和 YAML
```

当前 manifest 明确将默认模板绑定为 `datasheet_template.docx + datasheet_template_v2.yaml`。

默认 YAML 中 `header.enabled=false`、`footer.enabled=false`，其语义是保留 DOCX 模板原有页眉、页脚和 Logo，而不是从 YAML 重新生成。

Renderer 当前会打开模板 DOCX、清除正文、保留 Section 属性，并在此基础上生成正文、表格、公式和图片；只有显式启用页眉或页脚覆盖时，才重写模板装饰。 

---

# 2. 实施边界

## 2.1 本轮需要完成

- 模板 DOCX 和 YAML 的运行时内容哈希校验；
- Renderer 使用任务冻结的模板、YAML 和术语规则资源；
- 模板页眉、页脚和 Logo 的 OOXML 完整性检查；
- DOCX 与 YAML 联合发布前预检；
- YAML 字段到 Renderer 的消费覆盖检查；
- 模板符合性证据接入现有质量报告；
- 补充相应回归测试与发布门禁。

## 2.2 本轮明确不做

- 不增加云平台；
- 不增加多个 PDF 解析器；
- 不增加新的用户可选渲染模式；
- 不把 Logo 移到 YAML 中配置；
- 不修改默认 Logo 的来源方式；
- 不增加品牌配置系统；
- 不增加在线 Word 编辑；
- 不接收用户修改后的 Word；
- 不增加图片内部 Logo 自动替换；
- 不重写现有表格、公式和 DocumentIR 架构；
- 不修改 `datasheet_template.docx` 的实际视觉内容；
- 不删除或重命名历史 `datasheet_template.yaml`；
- 不在本轮进行大规模命名样式重构。

---

# 3. 实施顺序与完成状态

```text
TPL-BASE-001 现状特征测试
        ↓
TPL-RSC-001 任务资源快照闭环
        ↓
TPL-QA-001 模板页眉/页脚/Logo 完整性证据
        ↓
TPL-VAL-001 DOCX + YAML 联合预检
        ↓
TPL-CFG-001 YAML 字段消费覆盖
        ↓
TPL-QA-002 模板符合性接入现有质量报告
        ↓
TPL-GOV-001 发布门禁和文档治理
```

截至 2026-11-12，七项均已在本地实施并合入 `main`，Trellis 任务已归档为 `completed`。第 4 至 10 节的「验收标准」按实施阶段的本地证据勾选。各节的测试和检查清单记录设计范围，实际验证结果见下表和第 13 节。 [Trellis 任务归档](../.trellis/tasks/archive/2026-11/11-12-template-render-integrity/task.json)

| 提交 | 用途 |
| --- | --- |
| `30081252df51acdc3205809fe51f8b7df315a2e6` | 实施前的 `main` 基线 |
| `2a6a4cb03e93be398f20990b4bf695847c8d42d6` | 七项共用的实现提交 |
| `e2bb5c7c98449e519aec5efcbe9f0d4a78e28d91` | Trellis 任务归档 |
| `f00a5445ddbe6813c7eef37f17c4547018b5689d` | Trellis 会话日志 |
| `384f805c1c5765d59db530222a576596b35a6c45` | 本地 `main` 合并提交 |

| 任务 | 状态 | 交付和已通过的验证 |
| --- | --- | --- |
| `TPL-BASE-001` | 已完成 | 运行时代码修改前，真实默认模板的 2 项特征测试和 78 项基线回归通过，覆盖页眉、页脚、Logo 哈希和五个 Section 的装饰继承。 |
| `TPL-RSC-001` | 已完成 | DOCX、YAML 和术语规则经 SHA-256 校验后原子物化到任务目录。渲染、重试和发布证明使用绑定资源，84 项相关测试通过，其中包含 13 项资源专项。 |
| `TPL-QA-001` | 已完成 | `template-conformance/v1` 检查各节实际生效的页眉、页脚、Logo 媒体和 OOXML 引用关系，72 项装饰与版式相关测试通过。 |
| `TPL-VAL-001` | 已完成 | 创建、替换、草稿、发布和 bootstrap 共用 DOCX + YAML 预检，116 项模板及 API 定向测试通过，另有 29 项历史版本复核和 38 项版本与发布专项通过。 |
| `TPL-CFG-001` | 已完成 | 登记可编辑字段的消费位置。5 项字段消费测试通过，包含 169 个可编辑叶子的 OOXML 单字段变异验证。 |
| `TPL-QA-002` | 已完成 | 符合性报告进入 Renderer evidence、质量门、管理摘要和 Datasheet 质量报告。18 项质量度量与采集测试通过，覆盖阻断、历史证据兼容和安全摘要。 |
| `TPL-GOV-001` | 已完成 | manifest 解析当前默认模板，历史 YAML 用途已写入 manifest 和维护文档。四项模板专项检查随发布检查通过，绑定门禁调整后的 5 项定向复核通过。 |

---

# 4. 任务一：冻结当前模板行为

## 任务编号

`TPL-BASE-001`

## 目标

在修改运行时代码前，为当前默认模板建立稳定的特征测试，防止优化过程中误删页眉、页脚、Logo 或破坏 Section 继承。

## 修改范围

建议新增：

```text
tests/test_template_package_contract.py
```

可复用或扩展：

```text
tests/test_document_ir_word_renderer_layout.py
tests/test_template_seed_history.py
```

## 实施内容

### 4.1 提取默认模板特征

从 `datasheet_template.docx` 中解析：

- `word/header*.xml`；
- `word/footer*.xml`；
- 对应 `.rels` 文件；
- 页眉和页脚引用的媒体文件；
- 页眉媒体 SHA-256；
- `headerReference` 类型；
- `footerReference` 类型；
- `w:titlePg`；
- `w:evenAndOddHeaders`；
- 默认 Section 数量；
- 默认页眉、页脚关系是否有效。

不要硬编码 Logo 文件名，应从 OOXML relationship 动态发现。

### 4.2 建立生成结果特征测试

使用当前默认模板渲染一个最小 DocumentIR，至少包含：

```text
纵向单栏
→ 双栏
→ 横向页面
→ 恢复纵向单栏
```

验证：

- 输出 DOCX 可正常打开；
- 模板页眉仍存在；
- 模板页脚仍存在；
- 模板页眉媒体仍存在；
- 页眉媒体内容哈希与模板一致；
- 后续 Section 正确继承页眉和页脚；
- 横向 Section 不丢失页眉；
- 双栏 Section 不丢失页眉；
- 没有悬空 relationship。

已有测试已经覆盖模板页眉页脚文字和 Section 继承，本任务是在此基础上补充媒体和 Logo 关系。

## 验收标准

- [x] 默认模板中至少检测到一个有效页眉 part；
- [x] 默认模板页眉至少引用一个媒体资源；
- [x] 输出 DOCX 中对应媒体哈希与模板一致；
- [x] 样本中所有生成 Section 的页眉关系均可解析；
- [x] 样本中所有生成 Section 的页脚关系均可解析；
- [x] 测试不依赖固定 relationship ID；
- [x] 测试不依赖固定 `header1.xml` 文件名；
- [x] 测试不修改模板二进制文件。

---

# 5. 任务二：建立任务级渲染资源闭环

## 任务编号

`TPL-RSC-001`

## 优先级

P0

## 目标

确保一次任务渲染时实际使用的：

- 模板 DOCX；
- 模板 YAML；
- 术语及上下标规则；

全部来自任务创建时绑定的资源快照，而不是运行时当前默认文件。

当前模板版本 payload 已经保存 `docx_sha256` 和 `layout_config_sha256`。

但当前资源物化主要检查文件是否存在，并未在每次正式渲染前将磁盘上的实际文件字节与 payload 中的内容哈希进行完整对账。

当前渲染执行还会将全局 `settings.subscript_config_path` 传入 Renderer，而不是任务快照物化出来的规则文件。

## 主要修改位置

```text
app/domains/jobs/resource_snapshots.py
app/domains/jobs/paths.py
app/domains/document_jobs/render_execution.py
app/domains/templates/read_service.py
app/domains/document_jobs/publication_provenance.py
```

可能涉及：

```text
app/services/renderer/word_renderer.py
```

## 实施内容

### 5.1 增加统一文件哈希校验

新增内部 helper，语义类似：

```python
def verify_file_sha256(
    path: Path,
    expected_sha256: str,
    *,
    error_code: str,
) -> bytes:
    ...
```

要求：

- 一次读取文件；
- 计算 `sha256:` 前缀格式；
- 与资源 payload 比较；
- 不一致时抛出稳定业务错误；
- 错误信息不暴露服务器绝对路径；
- 返回已经验证的字节，避免同一次逻辑再次读取不同内容。

建议错误码：

```text
template_docx_hash_mismatch
template_layout_config_hash_mismatch
```

### 5.2 将模板资源物化到任务目录

建议扩展 `JobPaths`：

```text
resource_template_docx
resource_template_layout_config
resource_subscript_config    # 已有则复用
```

物化流程：

```text
读取资源版本记录
→ 验证 snapshot_hash
→ 读取模板原文件
→ 验证 docx_sha256
→ 原子写入任务资源目录
→ 验证任务目录副本
→ 返回任务目录路径
```

YAML 使用相同流程。

文件写入要求：

- 临时文件；
- `flush`；
- `fsync`；
- 原子 `replace`；
- 已存在文件先校验哈希，相同则复用；
- 已存在但哈希不符则失败；
- 并发 Worker 不得产生部分文件。

### 5.3 统一正式渲染资源解析

在 `WordRenderExecution` 中增加统一入口，例如：

```python
def _resolve_render_resources(
    self,
    job: DocumentJobRecord,
) -> ResolvedRenderResources:
    ...
```

推荐规则：

```text
有 job.resource_snapshot
    → 使用 JobResourceSnapshotService.materialize()
    → 使用任务目录中的 DOCX/YAML/规则文件

无 resource_snapshot 的历史任务
    → 保留现有 TemplateReadService legacy 路径
```

正式 Renderer 调用改为：

```python
self.word_renderer.render_to_result(
    document,
    template_path=resources.template_path,
    config_path=resources.layout_config_path,
    image_loader=...,
    options=DocumentIRRenderOptions(
        subscript_config_path=resources.subscript_config_path,
        document_language=...,
        template_version_id=...,
    ),
)
```

对于带快照的任务，不得再使用：

```python
self.settings.subscript_config_path
```

### 5.4 Publication provenance 使用同一资源来源

`capture_render_publication_provenance()` 不应重新选择“当前默认资源”。

应当：

- 使用任务绑定快照；
- 使用相同的资源物化和哈希校验逻辑；
- 或直接使用渲染阶段已经认证的资源身份；
- 不允许渲染和发布证明分别解析出不同资源。

## 测试清单

### 文件哈希

- [ ] 模板 DOCX 未变化时正常渲染；
- [ ] 模板 DOCX 在任务创建后、首次渲染前被修改，任务失败；
- [ ] YAML 在任务创建后、首次渲染前被修改，任务失败；
- [ ] 错误码稳定；
- [ ] 错误信息不泄露绝对路径。

### 任务资源隔离

- [ ] 任务第一次执行后修改共享模板，重试仍使用任务目录副本；
- [ ] 任务第一次执行后修改共享 YAML，重试仍使用任务目录副本；
- [ ] 全局术语规则变化不影响已创建任务；
- [ ] 新任务使用最新默认规则；
- [ ] direct 任务和翻译任务均使用快照规则；
- [ ] draft 模板验证任务继续可用；
- [ ] published 模板任务不允许绑定 draft；
- [ ] legacy 无快照任务保持原有兼容行为。

## 验收标准

- [x] 有资源快照的任务不读取当前全局默认模板；
- [x] 有资源快照的任务不读取当前全局术语规则；
- [x] 实际模板字节和 YAML 字节都经过哈希校验；
- [x] 渲染、重试和 publication provenance 使用同一资源身份；
- [x] 任务资源快照沿用现有 HTTP API；
- [x] 默认模板混合 Section 样本的 DOCX 部件与实施前基线逐字节一致。

---

# 6. 任务三：页眉、页脚和 Logo 完整性证据

## 任务编号

`TPL-QA-001`

## 优先级

P1

## 目标

将模板 DOCX 自带页眉、页脚和 Logo 的保留情况纳入现有 Renderer 质量证据。

当前 `docx_quality.py` 已检查正文、表格、公式、编号、图片数量、横向 Section 等，但未见对页眉媒体 relationship 和 Logo 内容哈希的专项检查。

## 建议新增文件

```text
app/services/renderer/template_conformance.py
```

建议新增测试：

```text
tests/test_template_conformance.py
```

## 数据结构

建议增加：

```python
class TemplateDecorationContract(BaseModel):
    schema_version: Literal["template-decoration-contract/v1"]
    header_parts: list[str]
    footer_parts: list[str]
    header_media_sha256: list[str]
    footer_media_sha256: list[str]
    first_page_header: bool
    even_odd_headers: bool
```

生成结果报告：

```python
class TemplateConformanceReport(BaseModel):
    schema_version: Literal["template-conformance/v1"]
    mode: Literal["preserve_template", "override", "no_template"]

    header_parts_preserved: bool | None
    footer_parts_preserved: bool | None
    header_media_preserved: bool | None
    footer_media_preserved: bool | None

    section_header_references_valid: bool
    section_footer_references_valid: bool
    broken_relationship_count: int

    missing_header_media_sha256: list[str]
    missing_footer_media_sha256: list[str]
    blocking_flags: list[str]
```

## 模式规则

### `preserve_template`

适用于：

```yaml
header:
  enabled: false

footer:
  enabled: false
```

要求输出保留模板原有：

- header part；
- footer part；
- header media；
- footer media；
- relationship；
- Section 引用。

### `override`

适用于显式开启页眉或页脚覆盖。

此时不要求模板原页眉字节不变，但要求：

- 新页眉关系有效；
- 新页脚关系有效；
- 新媒体关系有效；
- Section 引用完整。

### `no_template`

`template_path=None` 时使用，不检查模板保留。

## 建议阻断码

```text
template_conformance:header_part_missing
template_conformance:footer_part_missing
template_conformance:header_media_missing
template_conformance:footer_media_missing
template_conformance:relationship_broken
template_conformance:section_header_reference_invalid
template_conformance:section_footer_reference_invalid
```

## 集成位置

```text
DocumentIRWordRenderer._freeze_result()
WordRenderResult
build_renderer_evidence()
ensure_renderer_integrity()
build_renderer_event_summary()
```

推荐流程：

```text
模板原始字节
+
生成 DOCX 字节
→ build_template_conformance_report()
→ 放入 WordRenderResult
→ 放入 renderer evidence
→ ensure_renderer_integrity 判断是否阻断
```

## 测试清单

- [ ] 默认模板正常生成时报告通过；
- [ ] 删除输出中的 Logo 媒体后产生阻断；
- [ ] 删除 `header*.xml.rels` 后产生阻断；
- [ ] relationship Target 指向不存在媒体时产生阻断；
- [ ] 删除 `headerReference` 后产生阻断；
- [ ] 多 Section 双栏文档正常通过；
- [ ] 横向 Section 正常通过；
- [ ] 页眉 override 模式不误判为模板 Logo 丢失；
- [ ] `template_path=None` 返回 `no_template`，不阻断。

## 验收标准

- [x] 公司 Logo 丢失能够在生成阶段被机器发现；
- [x] 页眉或页脚 relationship 断裂能够阻断任务成功；
- [x] 检查基于 OOXML relationship，不依赖媒体文件名；
- [x] 不要求将 Logo 配置到 YAML；
- [x] 不改写默认模板页眉。

---

# 7. 任务四：DOCX 与 YAML 联合预检

## 任务编号

`TPL-VAL-001`

## 优先级

P1

## 目标

在模板版本进入可验证或可发布状态前，验证 DOCX 模板和 YAML 配置能够作为一个完整模板包工作。

## 建议新增

```text
app/domains/templates/package_validator.py
```

接口示例：

```python
@dataclass(frozen=True)
class TemplatePackageValidationReport:
    ok: bool
    errors: tuple[TemplatePackageValidationError, ...]
    warnings: tuple[TemplatePackageValidationWarning, ...]
    template_fingerprint: dict[str, Any]


def validate_template_package(
    *,
    template_path: Path,
    layout_config_path: Path | None,
) -> TemplatePackageValidationReport:
    ...
```

## 检查内容

### DOCX 文件

- [ ] 文件存在且非空；
- [ ] ZIP 结构可读取；
- [ ] `[Content_Types].xml` 存在；
- [ ] `word/document.xml` 存在；
- [ ] python-docx 可打开；
- [ ] `sectPr` 存在；
- [ ] 所有页眉 relationship 可解析；
- [ ] 所有页脚 relationship 可解析；
- [ ] 页眉引用的媒体文件存在；
- [ ] 页脚引用的媒体文件存在；
- [ ] relationship Target 不越界；
- [ ] 不存在损坏的内部 part。

### YAML 文件

- [ ] schema version 受支持；
- [ ] 未知字段拒绝；
- [ ] 页面尺寸有效；
- [ ] 页边距有效；
- [ ] 正文区域宽高为正；
- [ ] 字号和间距范围有效；
- [ ] 颜色格式有效；
- [ ] `table_style.style_name` 在 DOCX 中真实存在；
- [ ] 所有非空 `word_style_name` 在 DOCX 中真实存在；
- [ ] header/footer override 配置内部一致。

当前代码已验证表格样式名称是否存在于模板文档中，应将这一能力纳入统一模板包验证器，而不是重复实现。

## 调用位置

建议在以下入口调用：

```text
bootstrap_manifest_versions()
create_template()
replace_template_file()
create_template_version()
create_template_layout_config_version()
publish_template_version()
```

其中：

- 创建 draft 前做基础预检；
- 发布前再次做完整预检；
- 当前已有“必须绑定成功验证任务才能发布”的规则继续保留；
- 不使用联合预检替代真实验证任务。

## 测试清单

- [ ] 当前默认模板包验证通过；
- [ ] 损坏 DOCX 被拒绝；
- [ ] 缺少 `word/document.xml` 被拒绝；
- [ ] 页眉关系指向不存在媒体时被拒绝；
- [ ] YAML 指定不存在的表格样式时被拒绝；
- [ ] YAML 指定不存在的段落样式时被拒绝；
- [ ] 非法页面尺寸被拒绝；
- [ ] 非法页边距被拒绝；
- [ ] 合法 draft 可以创建；
- [ ] 非法 draft 不产生残留版本目录；
- [ ] 预检失败不修改默认模板指针；
- [ ] 预检失败不写入半成品资源记录。

## 验收标准

- [x] 无效模板不能进入 published 状态；
- [x] 预检错误具有稳定的字段路径和错误码；
- [x] 模板发布继续沿用现有权限和验证任务流程；
- [x] 不修改默认 DOCX；
- [x] 不增加 Logo YAML 配置。

---

# 8. 任务五：YAML 字段消费覆盖检查

## 任务编号

`TPL-CFG-001`

## 优先级

P1

## 目标

确保前端可编辑、YAML 可保存的每个字段，都满足以下两种情况之一：

```text
A. Renderer 实际消费该字段，并有 OOXML 测试；
B. 字段明确标注为只读或暂不参与渲染。
```

不允许出现：

```text
字段可编辑
→ YAML 校验通过
→ Renderer 实际忽略
```

## 主要修改位置

```text
app/domains/templates/layout_config_schema.py
app/services/renderer/text_renderer.py
app/services/renderer/page_layout_renderer.py
app/services/renderer/table_renderer.py
app/services/renderer/native_table_renderer.py
tests/test_template_config_consumption.py
```

## 实施步骤

### 8.1 建立字段清单

从：

```python
editor_field_schema()
GROUP_FIELD_SCHEMA
```

自动提取所有叶子字段，例如：

```text
page_setup.top_margin
normal.font_name
normal.font_size
heading1.color
table_style.header_fill
table_content.min_font_size
header.enabled
footer.show_page_number
```

### 8.2 建立消费注册表

建议测试层维护：

```python
TEMPLATE_CONFIG_CONSUMER_REGISTRY = {
    "page_setup.top_margin": "section.pgMar.top",
    "normal.font_name": "paragraph.run.rFonts.eastAsia",
    "normal.font_size": "paragraph.run.sz",
    "heading1.color": "heading.run.color",
    "table_style.header_fill": "table.header.cell.shading",
    ...
}
```

字段分类：

```text
rendered
conditional
readonly
metadata_only
unsupported
```

`unsupported` 不允许进入发布状态；应删除字段、改为只读，或补实现。

### 8.3 增加变异测试

针对高价值字段，执行：

```text
基线配置渲染
→ 单独修改一个字段
→ 再次渲染
→ 检查目标 OOXML 是否按预期变化
```

必须覆盖：

#### 页面

- 页面宽高；
- 上下左右边距；
- 页眉距离；
- 页脚距离。

#### 标题和正文

- 中文字体；
- 西文字体；
- complex script 字体；
- 字号；
- 粗体；
- 斜体；
- 颜色；
- 对齐；
- 行距；
- 段前段后；
- 首行缩进；
- 左右缩进；
- `word_style_name`。

#### 表格

- 表格样式名；
- 表头粗体；
- 表头底色；
- 边框颜色；
- 表格文字样式；
- 最小字号逻辑。

#### 页眉页脚 override

- enabled；
- title text；
- 字体；
- 字号；
- 颜色；
- 页码；
- 左右文字；
- 对齐。

## 验收标准

- [x] 所有可编辑字段均已分类；
- [x] 所有 `rendered` 字段都有对应测试；
- [x] 所有 `conditional` 字段都有触发条件测试；
- [x] 不存在未登记的可编辑字段；
- [x] 新增 YAML 可编辑字段时，缺少消费注册会导致字段消费检查和本地 release check 失败；
- [x] 默认模板混合 Section 样本在 LibreOffice 26.2.4.2 导出的 3 页画面与基线一致。

---

# 9. 任务六：模板符合性接入现有质量报告

## 任务编号

`TPL-QA-002`

## 优先级

P1

## 依赖

依赖 `TPL-QA-001`。

## 目标

不新增独立质量平台，而是把模板符合性并入现有 Renderer evidence 和 Datasheet 质量报告。

## 建议 evidence 结构

```json
{
  "template_conformance": {
    "schema_version": "template-conformance/v1",
    "mode": "preserve_template",
    "template_docx_hash_match": true,
    "layout_config_hash_match": true,
    "header_parts_preserved": true,
    "footer_parts_preserved": true,
    "header_media_preserved": true,
    "footer_media_preserved": true,
    "section_header_references_valid": true,
    "section_footer_references_valid": true,
    "broken_relationship_count": 0,
    "blocking_flags": []
  }
}
```

## 集成位置

```text
app/services/renderer/render_evidence.py
app/services/renderer/render_evidence_validation.py
app/services/renderer/render_event_summary.py
scripts/ops/datasheet_quality_metrics.py
```

## 报告原则

- 对外事件只输出统计和稳定错误码；
- 不输出服务器路径；
- 不输出 Logo 原始字节；
- 哈希只进入私有证据或内部质量报告；
- `blocking_flags` 非空时不能标记质量检查成功。

## 验收标准

- [x] 模板完整性出现在 Renderer 质量报告；
- [x] 模板 Logo 丢失会阻断成功；
- [x] 模板 YAML 哈希不匹配会阻断成功；
- [x] 管理端任务文件 API 提供稳定的模板符合性摘要；
- [ ] 在管理界面核对模板符合性摘要，随第 13 节的在线验证任务确认；
- [x] 历史 evidence 仍能读取；
- [x] 新字段采用嵌套版本，不破坏旧字段含义。

---

# 10. 任务七：模板文件治理与发布门禁

## 任务编号

`TPL-GOV-001`

## 优先级

P2

## 目标

消除默认模板文件使用上的歧义，并将模板检查接入现有发布流程。

## 实施内容

### 10.1 manifest 作为唯一权威入口

代码、测试和文档应统一：

```text
先解析 templates_manifest.yaml
→ 再确定 DOCX 和 YAML
```

不得通过猜测文件名决定当前默认模板。

### 10.2 标记旧 YAML

`resources/template_configs/datasheet_template.yaml` 是已发布的 `default@1` 资源。按确认后的方案，在 `templates_manifest.yaml` 和维护文档中说明历史用途，保留 YAML 的原路径、原始字节、SHA-256 和版本绑定。当前默认资源由 manifest 绑定为 `default@2`。

### 10.3 扩展 release check

在现有发布检查中增加：

```text
template-package-preflight
default-template-manifest-binding
template-config-consumer-coverage
default-template-decoration-contract
```

建议输出：

```text
PASS template-package-preflight: default@2
PASS template-decoration-contract: header media preserved
PASS template-config-consumer-coverage: 100%
```

## 验收标准

- [x] 修改历史 YAML 不会被误认为修改当前默认模板；
- [x] 内置默认模板通过 manifest 解析；
- [x] 损坏的默认模板包会使本地 release check 失败；
- [x] 文档明确 DOCX 和 YAML 的职责；
- [x] 不修改已有资源版本历史。

---

# 11. 暂缓任务

以下任务不应与本轮一起实施。

## 11.1 命名样式与直接格式重构

当前 Renderer 会同时使用 Word 样式和直接格式，以保证 YAML 结果确定。

减少直接格式可能提高用户在 Word 中整体修改样式的便利性，但也可能改变：

- 字体继承；
- 表格字体；
- 标题颜色；
- Office 与 LibreOffice 的渲染；
- Golden Sample 结果。

因此应另开 Epic：

```text
TPL-EDIT-001 Measure direct formatting ratio
TPL-EDIT-002 Compile YAML into named Word styles
TPL-EDIT-003 Reduce direct formatting by style group
```

只有在本轮资源完整性和模板符合性完成后再实施。

---

# 12. 建议 PR 划分

以下为原计划的 PR 划分。实施和验证按五组记录，最终汇总为第 3 节所列的本地实现提交，远端 PR 尚未创建。 [实施与验证记录](../.trellis/tasks/archive/2026-11/11-12-template-render-integrity/validation.md)

## PR 1：基线与资源快照闭环

包含：

```text
TPL-BASE-001
TPL-RSC-001
```

要求：

- 不改变正常 DOCX 输出；
- 只增加资源校验和任务级物化；
- 加入全部 P0 回归测试。

## PR 2：模板装饰完整性

包含：

```text
TPL-QA-001
TPL-QA-002
```

要求：

- 新增模板符合性报告；
- 缺失 Logo 或 relationship 时失败关闭；
- 不修改默认模板文件。

## PR 3：模板联合预检

包含：

```text
TPL-VAL-001
```

要求：

- draft 和 publish 共用同一验证器；
- 无效模板不留下半成品资源。

## PR 4：配置覆盖和治理

包含：

```text
TPL-CFG-001
TPL-GOV-001
```

要求：

- 字段覆盖率为 100%；
- release check 接入；
- 更新相关文档。

---

# 13. 全局完成标准

以下勾选以实施阶段的本地证据为准。线上验证见本节待办。

## 功能

- [x] 默认 DOCX 模板继续提供页眉、页脚和 Logo；
- [x] YAML 继续负责页面、字体、颜色、段落和表格配置；
- [x] Renderer 不从 YAML 重新生成默认 Logo；
- [x] 带快照的任务使用创建时绑定的模板和规则资源；
- [x] 普通重试使用相同资源；
- [x] Logo 丢失可被机器检测；
- [x] 联合预检拒绝 DOCX 与 YAML 不匹配的模板；
- [x] YAML 可编辑字段均有实际消费证明。

## 兼容性

- [x] 本轮涉及的 HTTP API 保持兼容；
- [x] 实施阶段通过 OpenAPI 快照一致性检查；
- [x] 本轮涉及的历史任务资源快照和 Renderer evidence 保持可读；
- [x] 历史模板版本保持可用；
- [x] legacy 无资源快照任务保持兼容；
- [x] 默认模板混合 Section 样本的 DOCX 部件和 LibreOffice 导出画面与基线一致。

## 已通过的本地验证

- 实施工作树的最终 `unittest` 定向组合通过 184 项。门禁调整后通过 5 项专项复核，`python scripts/ops/check_release.py` 通过全部 8 项检查，包含 OpenAPI 和四项模板专项检查。各批次覆盖有重叠。 [验证记录与完整命令](../.trellis/tasks/archive/2026-11/11-12-template-render-integrity/validation.md#最终本地验证)
- 默认模板的混合 Section 样本在基线和候选生成的 DOCX 中有 19 个 ZIP 成员逐字节一致。用同一隔离的 LibreOffice 26.2.4.2 进程打开并导出，3 页栅格像素逐页一致。OPA228 本地组件样本 `ti-opamp-opa228-p1-smoke` 通过。 [产物对照和组件验证](../.trellis/tasks/archive/2026-11/11-12-template-render-integrity/validation.md#最终本地验证)
- 扩展回归中在原基线也复现的历史失败已记入验证记录。合入本地 `main` 的 `384f805c` 后仅做了静态核对，**未重跑测试或发布检查**。上面的通过结果来自实施阶段。 [原对话中的合并记录](codex://threads/01a1cf09-d51c-7972-9adc-3c19fe90d067)

## 线上验证待办

- [ ] 远程 Golden Sample preflight。
- [ ] 在线执行真实默认模板验证任务，并核对管理界面的模板符合性摘要。
- [ ] 在线 Word Preview。

---
