---
doc_type: gap-analysis
status: current-vs-target
baseline_commit: e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8
last_reviewed: 2026-10-03
---

# 当前实现与目标差距

## 1. 使用说明

本文件是 Codex 开始任务前的调查清单。每个任务必须先验证当前代码是否已经变化，不得机械按本文重复实现。

状态：

- **已有**：目标基本具备，主要补测试/文档；
- **部分**：已有基础，需要收口；
- **缺失**：目标合同尚未形成；
- **不确定**：必须在任务 research 中确认。

## 2. 产品模式

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| direct/en2zh/ru2zh/zh2en/zh2ru | `modes.py` 已定义 | 保持 | 已有 |
| zh2zh Prompt | 未定义，别名映射 direct | 不新增 | 已有 |
| 一任务一 DOCX | 当前 `result_file_id` 单值 | 明确为不变量 | 已有/补文档测试 |
| 创建页按模式显示资源 | 已区分翻译资源 | direct 文案改为原文转换 | 部分 |

## 3. MinerU 与 DocumentIR

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| nested/flat content list | converter 已支持 | 保持 | 已有 |
| DocumentIR v2 | 已有 pages/layout/caption/footnote | 兼容扩展 | 已有 |
| source→IR integrity | `integrity.py` fail-closed | 扩展 table/image/page evidence | 部分 |
| caption 重新绑定 | 连续编号图片已有严格修复 | 扩展不确定 QA | 部分 |
| 空表续页处理 | 已有近期修复 | 固化 ZK7044 回归 | 部分 |
| 运行页眉页脚误分类 | role 基于 source type | 需要跨页重复归一 | 缺失/部分 |
| 跨页段落合并 | 未发现明确统一服务 | source spans + 合并 | 缺失 |
| 逻辑跨页表格 | 有 placeholder continuation/height | 需要 LogicalTableGroup | 部分 |

## 4. 表格

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| HTML parser | `SimpleTableHTMLParser` | CanonicalTableGrid | 部分 |
| rowspan/colspan Word 合并 | 常规表已有 | 保持并增强 | 已有 |
| 大表 | 超阈值展开 span | 保留合并语义 | **差距** |
| 表格 QA | 主要是 DOCX 数量/形状 | 结构、粘连、跨页、blocked | 缺失 |
| reference image | MinerU block 有路径但 IR asset 主要用于 image/chart | 一等 QA Artifact | 缺失/部分 |
| HTML 缺失 | integrity 可阻断，近期有 placeholder 修复 | 内部占位+blocked+下载策略 | 部分 |
| 表格翻译 | HTML text nodes | CellRun + context | 部分 |

## 5. 翻译

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| 四个 Prompt | 已有 | 保持 | 已有 |
| ID 结构验证 | 已有 | 保持 | 已有 |
| 批次/重试/拆分 | 已有 | 保持 | 已有 |
| 术语匹配/trace | 已有 | 保持并校验输出 | 部分 |
| caption/footnote 翻译 | extract 入口显式包含 text/list/table nodes，需确认 annotation | 全部 annotation | 不确定/可能缺失 |
| ProtectedTokenCodec | 未发现 | 必须实现 | 缺失 |
| 数字/单位/公式后验校验 | 未发现统一服务 | 必须实现 | 缺失 |
| table context | TranslationTextItem 只有 id/text | 增加只读 context | 缺失 |
| 四方向正式回归 | 当前 P1 manifest 主要 en2zh | 每方向独立 | 缺失 |

## 6. Renderer 与模板

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| Renderer 模块化 | layout/text/table/image/quality 已拆 | 保持 | 已有 |
| Word 原生 heading/list/table/image | 已有 | 增强 | 已有 |
| 公式 | 已有简单语义处理 | 明确 OMML/降级策略 | 部分 |
| 横向宽表 | 已有 layout 能力/质量证据 | 按 CanonicalGrid 完善 | 部分 |
| Template version | API 和验证任务成熟 | 复用 | 已有 |
| DOCX OOXML QA | 已有轻量证据 | 增加 block/page/preview QA | 部分 |
| Word preview | 未在核心文档中确认 | 发布前预览 Artifact | 不确定/可能缺失 |

## 7. QA、批准和发布

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| translation QA | 有队列、状态和证据 | 扩展统一 document review | 部分 |
| direct QA | 主要是人工 Golden signoff | 任务级统一 review | 缺失 |
| quality_status | quality flags 有，但独立状态未明确 | pending/passed/warning/blocked | 缺失/部分 |
| delivery_status | 未发现任务级状态 | draft/ready/published | 缺失 |
| publication record | 模板有发布，文档结果发布未确认 | 不可变发布记录 | 缺失 |
| blocked 下载提示 | 当前下载主要由 available action | 明确 warning/classification | 缺失 |
| 三栏审核 | translation QA panel 已有部分证据 | PDF/内容/Word preview 同步 | 部分 |

## 8. 状态机与事件

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| 执行状态 | pending/queued/running/... | 保持 | 已有 |
| 阶段 | 无 translating/quality_checking | 显式阶段 | 缺失 |
| translation batch status | 已有 | 保持 | 已有 |
| review/publish events | translation QA event 有 | 统一 review/publish | 部分 |

## 9. 测试

| 能力 | 当前 | 目标 | 状态 |
|---|---|---|---|
| P0 Golden | 4 个 OPA228 | 保持 | 已有 |
| component samples | 体系已建立 | 加入 ZK7044 最小页组 | 部分 |
| P1 translation samples | 3 个 en2zh | 四方向 | 缺失 |
| frontend unit/smoke | 已有 | 增加 review/publish | 部分 |
| release/online gates | 已有 | 扩展新状态和门禁 | 部分 |

## 10. 优先级结论

### 第一优先级

1. 状态/合同冻结；
2. CanonicalTableGrid 和表格 QA；
3. ProtectedTokenCodec 和翻译完整性；
4. 统一 quality/review/delivery 状态。

### 第二优先级

1. Word preview 和三栏审核；
2. 文档发布记录；
3. 四方向样本和门禁；
4. ZK7044 复杂样本回归。

### 不应优先

- 重写 UI；
- 更换框架；
- 微服务；
- 在线编辑；
- 多解析器；
- 泛 PDF。
