# 技术设计

## 1. 5.1 单一实现

- 唯一 owner：`app/services/renderer/layout_plan.py::split_two_col_blocks`（已声明为共享 owner，已被 `logical_table_plan` 使用）。
- `render_plan.py`：删除本地 `split_two_col_blocks`（256–270 行），在现有 `from app.services.renderer.layout_plan import ...` 中加入该函数；354、389 行调用不变。
- 两份实现逐行等价，替换后 RenderPlan 输出（含 `plan_sha256`）不变，因此无需改合同版本或兼容逻辑。

## 2. 一致性回归测试

放在 `tests/test_document_ir_word_renderer_layout.py`（已有双栏夹具）：

- 构造 two_col region 的 blocks：`column_hint` 为 left/right/wide 各一，无 bbox 一个，按 bbox 中心落左/右各一。
- 断言 `build_render_plan` 产出的该 region 左栏、右栏 block_id 顺序等于 `layout_plan.split_two_col_blocks` 的结果。
- 另断言 `render_plan` 模块不再定义自己的 `split_two_col_blocks`（`render_plan.split_two_col_blocks is layout_plan.split_two_col_blocks`）。

## 3. 5.2（按 D1）

- 不改 `_set_section_columns` 与 RenderPlan 合同。
- 新增测试：用不含 `w:space` 的模板 sectPr 渲染双栏，断言 `_content_width_and_columns` 返回的单栏宽度 = (页宽 − 左右边距 − 720 twips) / 2，即与 LibreOffice 实测缺省一致。
- 规格 COL-002 增加：“栏距随模板 `w:space` 继承；缺省按 720 twips，渲染器宽度计算与图片证据读取实际值。LibreOffice 26.2 实测缺省等同 720；Word 未验证。”

## 4. 风险与回滚

- 5.1 为纯重复删除，风险在于两份实现存在未察觉差异——设计第 2 节的一致性测试与既有 COL-002 测试覆盖。
- 回滚即回退提交；无数据或合同变化。
