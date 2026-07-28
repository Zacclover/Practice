---
version: alpha
name: Spatial Insight Orange Industrial
description: 数据密集型竞品洞察工作台的黑白灰工业视觉系统，以克制橙色、锐利几何、分层线条和轻量十字底纹建立识别。
colors:
  primary: "#111111"
  ink: "#191919"
  graphite: "#343434"
  lineMedium: "#595959"
  gray500: "#8B8B88"
  lineSubtle: "#C9C8C3"
  gray100: "#EFEEE9"
  paper: "#F7F6F1"
  white: "#FFFFFF"
  orange: "#FF5A1F"
  danger: "#B42318"
typography:
  display:
    fontFamily: Archivo Black, Noto Sans SC, Arial Black, sans-serif
    fontSize: 3.5rem
    fontWeight: 900
    lineHeight: 0.98
    letterSpacing: "-0.07em"
  heading-lg:
    fontFamily: Noto Sans SC, Arial, sans-serif
    fontSize: 1.375rem
    fontWeight: 900
    lineHeight: 1.25
    letterSpacing: "-0.04em"
  heading-md:
    fontFamily: Noto Sans SC, Arial, sans-serif
    fontSize: 1.125rem
    fontWeight: 800
    lineHeight: 1.35
    letterSpacing: "-0.03em"
  body:
    fontFamily: Noto Sans SC, Arial, sans-serif
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.6
  label-mono:
    fontFamily: IBM Plex Mono, ui-monospace, monospace
    fontSize: 0.6875rem
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
rounded:
  none: 0px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
components:
  page-canvas:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "{spacing.xl}"
  header:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "{spacing.xl}"
  button-primary:
    backgroundColor: "{colors.orange}"
    textColor: "{colors.primary}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "{spacing.md}"
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.white}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.primary}"
    rounded: "{rounded.none}"
    padding: "{spacing.md}"
  button-dark:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.white}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.white}"
  content-surface:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.xl}"
  muted-surface:
    backgroundColor: "{colors.gray100}"
    textColor: "{colors.primary}"
    rounded: "{rounded.none}"
  secondary-copy:
    backgroundColor: "{colors.white}"
    textColor: "{colors.lineMedium}"
    typography: "{typography.body}"
  line-medium-swatch:
    backgroundColor: "{colors.lineMedium}"
  gray-marker-swatch:
    backgroundColor: "{colors.gray500}"
  line-subtle-swatch:
    backgroundColor: "{colors.lineSubtle}"
  mono-label:
    backgroundColor: "{colors.white}"
    textColor: "{colors.primary}"
    typography: "{typography.label-mono}"
---

## Overview

**Spatial Insight Orange Industrial** 是竞品洞察台唯一正式视觉规范。所有后续新增功能、页面、弹窗、组件和交互状态必须先复用本文件 Token 与规则；不得另建一套颜色、圆角、阴影或按钮语言。

体验关键词：**工业制图、编辑部排版、锐利几何、数据优先、克制沉浸**。

界面以黑、白、灰承担 85%–90% 的信息秩序。橙色只占约 **10%–15%** 的视觉预算，用于最高优先级操作、编号、定位点、当前状态和焦点提示。

## Colors

- **Primary / #111111：** Header、关键结构、矩阵表头、最高层分割线和 Primary Hover。
- **Ink / #191919：** 正文和主要信息，不与纯黑结构线混用。
- **Graphite / #343434：** 卡片反转 Hover、深色次级表面。
- **Line Medium / #595959：** Tab、卡片组和次级区域边界。
- **Gray 500 / #8B8B88：** 只用于辅助标识，不承载小字号正文。
- **Line Subtle / #C9C8C3：** 矩阵内部、轴线和十字底纹。
- **Paper / #F7F6F1：** 页面底色。
- **White / #FFFFFF：** Hero、卡片、弹窗、表单和数据表面。
- **Orange / #FF5A1F：** 最高优先级按钮与少量定位信号；橙底必须使用黑字。
- **Danger / #B42318：** 仅用于删除、覆盖等破坏性动作，不得取代橙色品牌强调。

禁止使用渐变。不得将橙色铺满普通卡片、矩阵、正文区或次级按钮。

## Typography

- **展示文字：** Archivo Black；中文回退 Noto Sans SC 900。用于 Hero 的强风格标题，采用紧字距和接近 1 的行高。
- **中文标题：** Noto Sans SC 800–900，字距 `-0.03em` 至 `-0.04em`。
- **正文与表单：** Noto Sans SC 400–600，优先保障中文可读性。
- **技术标签：** IBM Plex Mono，用于 Tab、编号、状态、时间、坐标和 Tooltip 快捷键信息。
- 不允许用 Mono 字体承载长段中文正文。

## Layout

- 主体内容保持居中最大宽度；顶部 Header 与工作区 Tab 继续全宽。
- 页面底色使用单层重复 SVG 小十字：网格 `44px × 44px`、十字 `6px × 6px`、线宽 `0.6px`、颜色 `#C9C8C3`。
- 小十字只出现在页面底色；Hero、卡片、弹窗、表单和矩阵必须使用不透明实底。
- Tab 桌面固定 `200px`、移动端固定 `160px`，必须 `nowrap + hidden + ellipsis`。
- 信息密度高的矩阵可以横向滚动，但不得让整个页面横向溢出。

## Elevation & Depth

不使用常规阴影和玻璃模糊。层级只通过以下方式建立：

1. 黑白灰反差。
2. `1px–2px` 分割线权重。
3. 尺度、留白、遮挡和局部黑白反转。
4. `translateY(-2px)` 以内的短促 Hover 位移。

三级分割线：

- **Strong / #111111：** 页面主结构、Hero 外框、区块标题线、矩阵外框。
- **Medium / #595959：** Tab 分隔、卡片组边界、次级区域边界。
- **Subtle / #C9C8C3：** 矩阵单元格、表单内部和辅助轴线。

## Shapes

- 功能性容器统一 `0px` 圆角：Hero、卡片、Tab、弹窗、输入框、Tooltip、矩阵和证据图块。
- Primary Button 左上角和右下角斜切 `9px`：
  `polygon(9px 0, 100% 0, 100% calc(100% - 9px), calc(100% - 9px) 100%, 0 100%, 0 9px)`。
- Secondary Button 保持完整矩形，不使用斜切。
- 圆形仅允许表达真实圆形语义，例如色点、单选按钮或装饰性几何体；不能作为通用按钮造型。

## Components

### Buttons

- **Primary：** 橙底、黑字、透明边框、双角斜切；每个视区或弹窗只保留一个最高优先级动作。
- **Primary Hover/Focus：** 黑底白字，外置 `2px` 橙色焦点轮廓。
- **Secondary：** 白底黑字、`1px` Strong 边框、完整矩形。
- **Danger：** 深红底白字，仅用于明确破坏性动作；仍需二次确认。
- 顶层操作按钮使用 `16px` 线性 SVG Icon：`1.7px` 线宽、square linecap、miter join。不得使用 Emoji 作为正式图标。

### Tabs

- 当前 Tab 使用黑底白字和 `3px` 橙色底线。
- 未选中 Tab 使用浅灰底、深灰文字与 Medium 分隔线。
- 编辑和关闭默认隐藏，只在 Hover 或键盘聚焦时出现。
- 完整名称必须通过 `title` 或可访问名称发现。

### Cards and Evidence

- 普通卡片白底、Medium 边界、无阴影、无圆角。
- Hover 可使用 Graphite 黑白反转和最多 `-2px` 位移。
- 证据图片允许使用实色半透明黑色遮罩保证白字可读；禁止渐变遮罩。
- 标签使用矩形，不使用药丸形圆角。

### Matrix

- 外框使用 Strong，内部单元格使用 Subtle。
- 表头可使用黑底白字；数据单元格保持白底黑字。
- 不对正文单元格使用橙色背景。
- Sticky 列不使用阴影，改用 Medium 分割线。

### Dialogs, Forms, Rich Text, and Tooltips

- 弹窗白底、Strong 边框、无圆角、无阴影。
- 输入框白底、Subtle 边框；Focus 使用黑色边框和 `2px` 橙色 outline。
- 富文本工具栏保持纯 Icon + Tooltip；图标遵循统一线性规范。
- Tooltip 使用黑底白字、Mono 标签、无圆角。

### Motion and Accessibility

- 动效只使用 `transform` 与 `opacity`，常规持续时间 `120ms–180ms`。
- `prefers-reduced-motion: reduce` 下移除非必要位移和过渡。
- 正文对比目标 WCAG AA `4.5:1`；控件边界和状态至少 `3:1`。
- 所有操作必须支持键盘；Hover 信息必须在 `:focus-visible` 时同样可见。
- 触屏目标尺寸不小于 `40px × 40px`。

## Do's and Don'ts

### Do

- 先复用 Token，再新增组件。
- 用线条层级、排版和黑白反差表达空间深度。
- 把橙色留给最重要动作和明确状态。
- 让矩阵、富文本和表单保持实底、平整、低噪声。
- 每次新增 UI 同步更新本文件与对应视觉回归测试。

### Don't

- 不新增紫色品牌色、玻璃拟态、渐变、常规阴影或大面积橙色背景。
- 不使用圆角卡片、药丸按钮和统一圆形 Icon Button。
- 不让装饰纹理穿透数据表面。
- 不因视觉改造改变 DOM ID、存储格式、导入导出、清洗或数据迁移逻辑。
- 不发布未验证桌面、窄屏、键盘、Reduced Motion 和高密度矩阵的视觉变更。
