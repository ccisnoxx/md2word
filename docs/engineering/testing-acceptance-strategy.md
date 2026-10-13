---
doc_type: testing-strategy
status: target
last_reviewed: 2026-10-03
---

# 测试与验收策略

## 1. 原则

1. 测试以“真实 DocumentIR/Renderer 主链路”为准，不维护第二套测试实现。
2. 单元测试保证算法，回归样本保证文档行为，人工签字保证 Word 交付质量。
3. 直接转换、表格、翻译、审核和发布分别有独立门禁。
4. 一种语言方向通过不代表其他语言方向通过。
5. 生成 DOCX 可打开不等于质量通过。
6. 专有 PDF、生成 DOCX 和渲染截图默认不提交仓库。

## 2. 测试层级

```text
L1 纯函数/模型单元测试
L2 组件测试（MinerU→IR、Translation、Renderer）
L3 任务应用集成测试（repository/queue/artifact）
L4 API 合同测试与 OpenAPI 快照
L5 前端单元和浏览器 smoke
L6 本地 MinerU 样本回归
L7 线上真实链路回归
L8 Admin 人工 Word 签字
```

## 3. L1 单元测试

### MinerU/DocumentIR

- nested page list 和 flat list；
- source order；
- bbox；
- page header/footer 角色；
- caption 重新绑定；
- 跨页段落；
- 续表归并；
- 空表占位；
- integrity fail-closed。

### 表格

- HTML 解析；
- CanonicalGrid；
- rowspan/colspan；
- span 冲突；
- formula/sup/sub runs；
- 大表；
- 粘连检测；
- 空 HTML；
- 列宽。

### 翻译

- translation unit ID；
- captions/footnotes；
- ProtectedTokenCodec；
- Provider response validation；
- term matching；
- batch split/retry；
- direct mode 不能调用 Provider。

### Renderer

- Heading/numbering；
- inline formula；
- image；
- table merge；
- landscape section；
- template style；
- DOCX quality evidence。

### 状态机

- 合法/非法迁移；
- blocked 下载；
- blocked publish 拒绝；
- result 变化使 review 失效；
- publication immutable。

## 4. L2 组件测试

### MinerU→DocumentIR

给定真实最小化 MinerU 包：

- 生成 v2；
- block/order/type/asset 对账；
- quality flags 符合预期；
- 不依赖网络。

### Translation

使用 fake Provider：

- 固定结构化响应；
- 模拟截断、429、超时、缺失 ID、改 Token；
- 验证拆分、重试、失败关闭。

### Renderer

给定固定 DocumentIR 和模板：

- 生成 DOCX；
- 解析 OOXML 验证结构；
- 不依赖 Microsoft Word 即可执行基本门禁。

## 5. L3 应用集成测试

覆盖：

- 任务创建和配置快照；
- direct/translation 分支；
- MinerU callback 幂等；
- Celery/eager queue 合同；
- Artifact 注册；
- retry generation；
- quality/review/publication persistence；
- owner/admin 权限。

## 6. API 合同测试

任何以下改动必须更新 OpenAPI：

- job stage/status 字段；
- quality/review/delivery 对象；
- download warning；
- preview；
- publish；
- publication list。

验证：

```bash
.venv/bin/python scripts/ops/check_release.py
```

## 7. 前端测试

### Vitest

- 模式选择资源显隐；
- 质量/复核/交付状态文案；
- blocked 下载提示；
- publish 按钮权限和禁用原因；
- 三栏审核状态管理；
- API 错误处理。

### Playwright

- 创建 direct 任务；
- 创建 translation 任务；
- 任务详情进度；
- blocked 下载确认；
- unreviewed 下载确认；
- QA 保存；
- Admin 发布；
- 三种 viewport。

```bash
cd frontend
npm run build
npm run test:unit
npm run test:smoke
```

## 8. 样本体系

### P0 Golden Samples

保留现有 OPA228 canonical 样本，验证：

- 首页双栏；
- 目录和列表；
- 表格、脚注、公式符号；
- 宽表横向页。

### Component PDF Samples

按风险沉淀最小 MinerU 包：

```text
brand/category/sample-id/mineru/
```

重点加入 ZK7044 最小页组：

| Sample | 页/区域 | 关注点 |
|---|---|---|
| zk7044-overview | 1–4 | 双栏、列表、图片、inline formula、页眉页脚 |
| zk7044-complex-table | 6 | rowspan、公式、参数表 |
| zk7044-corrupted-table | 10 | 数字和单位粘连、blocked |
| zk7044-missing-table | 14–16 | 跨页引脚表、空 HTML 占位 |
| zk7044-caption-pair | 18 | 图 5/图 6 caption 错配 |
| zk7044-cross-page-paragraph | 40–41 | 段落续页 |
| zk7044-register-map | 42–49 | 超大多页寄存器表 |

### Translation Samples

按语言方向拆分：

```text
tests/fixtures/translation_samples/
├── en2zh/
├── ru2zh/
├── zh2en/
└── zh2ru/
```

每个方向至少覆盖正文、列表、表格、caption、footnote、单位、公式、地址和位字段。

## 9. 本地回归命令

```bash
.venv/bin/python scripts/dev/run_component_pdf_regression.py
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode direct --sample-set phase2-core
```

实施新 translation matrix 后建议：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode en2zh --sample-set translation-core
```

其他语言方向使用对应 mode。

## 10. 线上回归

### P0

```bash
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url <api-base-url> \
  --golden-sample-preflight

.venv/bin/python scripts/ops/run_golden_sample_regression.py
```

### 翻译

保留现有 P1 脚本，并扩展 `--mode` 或按语言方向建立 manifest：

```bash
.venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
```

### 总门禁

线上结果必须保留 run directory、报告、任务 ID、质量 flags 和 Admin signoff。

## 11. 人工验收

在公司实际 Microsoft Word 环境检查：

- 可打开；
- 可编辑；
- 表格合并；
- 图片；
- 标题和目录；
- 横向页；
- 公式和符号；
- 未复核/blocked 状态与系统一致；
- 发布下载指向正确文件。

## 12. 发布门禁

### 阻断

- 测试失败；
- OpenAPI snapshot 过期；
- Golden Sample 回归失败；
- direct 调用翻译 Provider；
- 表格 HTML 存在但输出不是 Word Table；
- Protected Token 变化；
- blocked 可发布；
- 已发布文件被覆盖。

### 可解释 warning

只有 Admin 在同一 run 记录原因后可放行：

- 非核心 spacing；
- 轻微分页；
- 浏览器预览与 Word 差异；
- 观察样本 P2 美观问题。

## 13. 完成定义

每个 Trellis 子任务完成时必须：

1. 需求验收项逐条有测试或人工证据；
2. targeted tests 通过；
3. `check_release.py` 通过或明确说明为何不适用；
4. 相关文档更新；
5. 没有未解释的新 quality flag；
6. Trellis check 和 spec update 完成。
