---
doc_type: reference
slug: chinese-datasheet-layout-recommendations
scope: `template_configs/datasheet_template.yaml` 的版式建议值，面向中文电子元器件数据手册 / 器件手册
summary: 给出标题、目录、正文、表格、图注、表注、页边距等推荐值，并逐项说明这些值为什么适合中文器件手册
status: current
last_reviewed: 2026-05-17
tags: [layout, style, datasheet, chinese, docx]
---

# 中文器件手册版式建议值

这份文档记录的是一套更适合**中文电子元器件数据手册**的推荐排版值，目标是解决三个常见问题：

1. 标题层级不明显，看起来像正文“挤”在一起。
2. 正文、目录、图表说明的节奏不统一，文档显得松散或发闷。
3. YAML 参数很多，但单看数字不容易判断为什么这么配。

这些建议值主要对应 [datasheet_template.yaml](/Users/sc/MinerU/md2word_file/template_configs/datasheet_template.yaml)。它们不是唯一正确答案，但适合作为当前仓库的默认基线。

## 使用原则

- 标题的“气口”主要靠 `space_before` / `space_after` 控制，不要误以为只靠 `line_spacing`。
- `line_spacing` 主要影响**同一段落内部多行**之间的距离；单行标题本身几乎看不出来。
- 中文器件手册一般追求“紧凑但不挤”，所以正文和表格通常不用太大的段后距。
- 目录、表格、图注、表注要比正文更规整，减少花哨感。

## 推荐配置总表

下面这段是建议直接对照使用的一套基线值，注释写的是“为什么是这个值”。

```yaml
# 页面设置：保持技术文档常见的紧凑版芯，既不压得太满，也不浪费页面。
page_setup:
  top_margin: 2.30        # 上边距略收紧，减少首页和正文页顶部空白。
  bottom_margin: 2.30     # 下边距与上边距对称，页脚仍有足够呼吸空间。
  left_margin: 1.60       # 中文正文每行不宜过长，左边距略大于极限压缩值。
  right_margin: 1.60      # 与左边距对称，保证双页视觉平衡。
  header_distance: 1.20   # 页眉与正文适度分离，避免页眉“压下来”。
  footer_distance: 1.40   # 页脚和正文保留安全距离，适合带页码模板。

# 首页器件型号：作为封面第一视觉锚点，字号要明显大于正文和标题。
part_number:
  font_name: Arial
  font_size: 22
  bold: true
  alignment: center
  space_after: 8          # 与副标题之间拉开层次，但不要空太多。

# 首页品类行：承接型号，不能抢主标题风头。
category:
  font_name: 宋体
  font_size: 12
  bold: true
  alignment: center
  space_after: 6          # 比当前 4pt 略宽，封面层次更自然。

# 一级标题：要有明确“章节切换感”，但仍保持器件手册的紧凑风格。
heading1:
  font_name: 宋体
  font_size: 13
  bold: true
  color: '#0c69b2'
  alignment: left
  space_before: 8         # 章节切换时显著拉开与上文距离。
  space_after: 6          # 标题与下文之间保留足够呼吸空间。
  line_spacing: 1.20      # 多行标题略松于单倍，但不松散。
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 二级标题：层级感弱于一级标题，但必须从正文中站出来。
heading2:
  font_name: 宋体
  font_size: 11
  bold: true
  color: '#000000'
  alignment: left
  space_before: 6         # 与上段保持明显区隔。
  space_after: 4          # 下接正文时不要紧贴。
  line_spacing: 1.15
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 三级标题：更像段首小标题，仍要比正文清晰，但不能过重。
heading3:
  font_name: 宋体
  font_size: 10
  bold: true
  color: '#000000'
  alignment: left
  space_before: 4
  space_after: 2
  line_spacing: 1.10
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 目录标题：目录页需要明确起始感，段后距可比正文更宽。
toc_title:
  font_name: 宋体
  font_size: 13
  bold: true
  color: '#000000'
  alignment: center
  space_before: 0
  space_after: 8
  line_spacing: 1.0

# 目录一级项：可略粗，帮助用户快速扫章节。
toc_level1:
  font_name: 宋体
  font_size: 11
  bold: true
  color: '#000000'
  alignment: left
  space_before: 0
  space_after: 1          # 轻微拉开一级项，便于扫描。
  line_spacing: 1.0

# 目录二级项：与一级项形成层次，但不宜过疏。
toc_level2:
  font_name: 宋体
  font_size: 10.5
  bold: false
  color: '#000000'
  alignment: left
  space_before: 0
  space_after: 0
  line_spacing: 1.0

# 目录三级项：尽量克制，避免目录页过高。
toc_level3:
  font_name: 宋体
  font_size: 10
  bold: false
  color: '#000000'
  alignment: left
  space_before: 0
  space_after: 0
  line_spacing: 1.0

# 正文：中文器件手册正文通常是“密而不挤”，首行缩进保留两字位。
normal:
  font_name: 宋体
  font_size: 10.5
  bold: false
  line_spacing: 1.20      # 比 1.15 略松，中文大段阅读更轻松。
  space_before: 0
  space_after: 0          # 同类正文段落之间一般不额外留白。
  color: '#000000'
  alignment: justify
  first_line_indent_pt: 21
  left_indent_pt: 0
  right_indent_pt: 0

# 表格正文：优先信息密度和整齐度，通常坚持单倍行距。
table_content:
  font_name: 宋体
  font_size: 9
  color: '#000000'
  alignment: left
  line_spacing: 1.0
  space_before: 0
  space_after: 0
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 表注：字号可小于正文，但不能小到“掉下去”。
table_note:
  font_name: 宋体
  font_size: 8.0          # 比 7.5 更稳妥，中文表注可读性更好。
  italic: false
  alignment: left
  line_spacing: 1.0
  space_before: 1         # 与表格底部轻微分离。
  space_after: 3
  color: '#666666'
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 图注 / 表题：器件手册一般比较规整，图题和表题不要太松。
caption:
  font_name: 宋体
  font_size: 9
  bold: false
  color: '#000000'
  alignment: center
  line_spacing: 1.0
  space_before: 4         # 图或表与标题之间保留一点距离。
  space_after: 4          # 标题与下文/表注之间不要紧贴。
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0

# 超长续表标题：需要和普通表题一致，但略偏紧凑。
long_table_caption:
  font_name: 宋体
  font_size: 10.5
  bold: false
  color: '#000000'
  alignment: center
  line_spacing: 1.0
  space_before: 2
  space_after: 3
  first_line_indent_pt: 0
  left_indent_pt: 0
  right_indent_pt: 0
```

## 分组说明

### 1. 标题组

标题组最关键的不是字号，而是“段前段后节奏”。

- 一级标题要负责“换章”的视觉信号，所以 `space_before` 最大。
- 二级标题需要从正文中立起来，但不能像一级标题那样跳。
- 三级标题更接近段首小节说明，应该短促、清楚、不过度留白。

当前仓库已经把标题值调整到了这一套建议附近，因此现在最直接的观感改善就会体现在标题层次上。

### 2. 目录组

目录页的目标不是“好看”，而是“好扫”。

- 目录标题的段后留白应明显大于目录项。
- 一级目录项略粗、略松，便于快速定位大章节。
- 二三级目录项保持紧凑，否则目录页高度容易失控。

### 3. 正文组

正文是整份文档的体感核心。

- `font_size=10.5` 是比较稳妥的中文器件手册正文大小。
- `line_spacing=1.2` 比 `1.15` 更适合中文连续阅读，但不会显著增页。
- `first_line_indent_pt=21` 仍建议保留，器件手册的说明性正文会更像中文原生文档。

### 4. 表格组

表格的首要目标是压缩信息密度并保持齐整。

- 表格正文通常不建议超过 `9pt`，否则大表很快失控。
- 单元格段前段后一般坚持 `0`，否则会把表格行高撑得很难看。
- 表注字号可以略小于正文，但建议至少 `8pt`，避免中文注释阅读吃力。

### 5. 图注 / 表题组

图题和表题在中文器件手册里一般要比正文更“规整”，而不是更“抒情”。

- 段前距要有，但不能大到像论文插图。
- 段后距建议与表注节奏配合。
- 一般使用居中、单倍行距即可。

## 哪些值优先改

如果只想做最小改动，优先顺序建议是：

1. `heading1/heading2/heading3`
2. `normal`
3. `caption` / `table_note`
4. `toc_*`
5. `page_setup`

原因：

- 标题和正文最直接决定“像不像中文文档”。
- 图注、表注会影响器件手册的专业感。
- 目录和页边距更多是全局整理项，通常排在后面。

## 当前状态

- 标题组已经按这套思路做了第一轮调整。
- 目录、正文、表格、图注、表注目前仍以“建议值”形式归档，尚未全部批量写回 YAML。

如果后续要继续推进，建议一次性把 `normal`、`caption`、`table_note` 也一并落地，这三组和标题组配合起来，整体气质会更接近中文器件手册。
