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
- **Orange / #FF5A1F：** 最高优先级按钮、少量定位信号及破坏性上下文操作的描边；橙底必须使用黑字。

禁止使用渐变。不得将橙色铺满普通卡片、矩阵、正文区或次级按钮。

## Typography

- **展示文字：** Archivo Black；中文回退 Noto Sans SC 900。用于 Hero 的强风格标题，采用紧字距和接近 1 的行高。
- **中文标题：** Noto Sans SC 800–900，字距 `-0.03em` 至 `-0.04em`。
- **正文与表单：** Noto Sans SC 400–600，优先保障中文可读性。
- **技术标签：** IBM Plex Mono，用于 Tab、编号、状态、时间、坐标和 Tooltip 快捷键信息。
- 不允许用 Mono 字体承载长段中文正文。
- 字体栈只使用系统已安装字体或项目自托管字体；正式页面不得直接请求 Google Fonts 等第三方字体服务。远程字体不可用时必须保持完整可用性和清晰层级。

## Layout

- 主体内容保持居中最大宽度；顶部 Header 与工作区 Tab 继续全宽。
- 页面底色使用单层重复 SVG 小十字：网格 `44px × 44px`、十字 `6px × 6px`、线宽 `0.6px`、颜色 `#C9C8C3`。
- 小十字只出现在页面底色；Hero、卡片、弹窗、表单和矩阵必须使用不透明实底。
- Tab 桌面固定 `200px`、移动端固定 `160px`，必须 `nowrap + hidden + ellipsis`。
- 信息密度高的矩阵可以横向滚动，但不得让整个页面横向溢出。
- 竞品档案卡片固定为 `480px × 480px` 正方形，并在档案轨道内横向排列；竞品过多时只允许轨道自身左右滚动，不得拉伸卡片或造成整页横向溢出。常规纵向内容应完整显示，极端超长内容才在卡片内部纵向滚动。
- 横向对比的对比维度列固定 `160px` 并持续吸附在矩阵左侧；正文固定列使用暖灰 `#EFEEE9` 实底，黑色表头保持不变。竞品列固定 `280px`，竞品过多时只允许矩阵容器自身左右滚动。固定列使用 Medium 分割线，不使用阴影。

### Mobile Density

- `760px` 以下进入紧凑工作台模式：产品主标题 `18px`、Hero 主标题 `30–38px`、区块标题 `17px`、卡片标题 `19px`，正文和辅助信息以 `12–13px` 为主。
- 移动端主体左右留白 `12px`，Hero 内容内边距约 `18–22px`，卡片内边距 `16px`；区块间距应比桌面减少约三分之一。
- Hero 几何板移动端高度约 `180px`，装饰图形应同步缩放，不得让装饰占据首屏主体。
- 工作区工具在窄屏使用三等分紧凑布局；文字和视觉高度可以缩小，但按钮、Icon、Tab 操作及富文本工具的触控目标不得小于 `40px × 40px`。
- 移动端 Tab 仍固定 `160px` 并在 Tab Track 内横向滚动；矩阵和流程引导图只允许在自身容器内滚动，不得造成整页横向溢出。
- 紧凑模式不得通过 `transform: scale()` 缩放整个应用，也不得改变 DOM ID、工作区数据或交互语义。

### Hero Composition and Bilingual Hierarchy

- 产品表面属于以 **Operate** 为主、**Compare** 为辅的工作台；Hero 是工作区命令头，不得扩张为营销落地页。
- Hero 使用最终 Pilot 的双栏构图：左侧类型海报约 `1.12fr`，右侧几何坐标板约 `.88fr`；`760px` 以下改为单栏。
- 左侧标题可将中文主语义与单个英文描边词组合；英文只承担系统名、技术标签和区块辅助标题，按钮与危险确认仍以清晰中文为主。
- 右侧几何板只使用轴线、圆盘、轨道、橙色板和坐标标签，不承载业务信息；必须设置 `aria-hidden="true"`。
- 几何板只允许出现在 Hero 或明确的空状态，不得穿过竞品正文、证据、表单或矩阵数据面。

### System Introduction and Onboarding

- 新用户首次访问时自动展示一次系统介绍；首次状态使用独立偏好 Key，不得写入或改变工作区 version 2 数据结构。
- 首次介绍显示“初次见面，自我介绍一下”欢迎语和工业几何撒花；从主标题入口再次打开时必须隐藏欢迎语和撒花。
- 系统介绍入口位于产品主标题旁，使用至少 `40px × 40px` 的纯 SVG 问号 Icon；Tooltip 和可访问名称统一为“系统介绍”。
- 引导图使用项目内本地 SVG，不依赖外部图片、字体或运行时；图中必须解释“竞品档案 → 调研证据 → 横向对比 → 洞察结论”的真实操作关系。
- 撒花只使用黑、白、灰与克制橙色的矩形、十字、菱形等几何图元；禁止 Emoji、渐变、阴影和多彩纸屑语言。
- `prefers-reduced-motion: reduce` 下撒花保持静态，不执行位移、旋转或缩放动画。
- 引导图必须提供完整文本替代；窄屏保持自身容器横向滚动，不得造成整页横向溢出。
- 后续新增大板块或改变主流程前，必须先询问产品负责人是否同步更新引导图，不得自行改写已确认内容。

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
- **Primary Hover：** 黑底白字。
- **键盘焦点：** 使用 `2px` 黑色外轮廓确保在白色与浅灰表面达到至少 `3:1`，并用橙色边框或局部状态保留品牌提示；不得只依赖低对比橙色外轮廓。
- **Secondary：** 白底黑字、`1px` Strong 边框、完整矩形。
- **Destructive Context Action：** 默认透明底、橙色 Icon 与 `1px` 橙色描边，复用弹窗关闭 `X` 的视觉语言；Hover 与 Focus 使用橙色实底、黑色 Icon。破坏性语义仍须通过垃圾桶/关闭 Icon、可访问名称和二次确认共同表达。
- 顶层操作、创建、保存、确认、取消和关闭按钮使用 `16px` 线性 SVG Icon：`1.7px` 线宽、square linecap、miter join；Icon 与文字间距统一为 `8px`。不得使用 Emoji、`×`、`✎` 或字母字符模拟正式图标。
- 竞品、证据、矩阵维度、洞察、Tab 与图片的编辑/删除属于上下文操作：桌面端默认隐藏，仅在父信息区 Hover 或 `focus-within` 时显示；键盘聚焦按钮自身时也必须可见。触屏或粗指针设备第一次点按信息区后显示，第二次点按原内容继续原操作；不得默认常驻，也不得变成触屏不可达。
- 上下文编辑使用黑白 Secondary 语义；上下文删除和移除使用 Destructive Context Action 的橙色描边语义。Graphite 反转卡片内仍保持橙色描边，不能退回红色或低对比灰色。
- 所有 Icon Button 的实际点击区域不得小于 `40px × 40px`，包括 Tab 编辑/关闭、卡片编辑/删除、矩阵维度编辑/删除、洞察编辑/删除、富文本工具、证据编辑/删除和图片移除。

### Tabs

- 当前 Tab 使用黑底白字和 `3px` 橙色底线。
- 未选中 Tab 使用浅灰底、深灰文字与 Medium 分隔线。
- 编辑和关闭在桌面默认隐藏，只在 Hover 或键盘聚焦时出现；触屏或粗指针设备点按 Tab 信息区后显示，再次点按操作按钮执行动作。
- 不显示左右移动按钮；键盘排序使用 `Alt + ArrowLeft / ArrowRight`，必须复用拖拽排序逻辑、恢复焦点，并通过 `aria-posinset` / `aria-setsize` 表达位置。边界按键必须阻止浏览器历史导航，同时保持顺序和焦点不变。
- 完整名称必须通过 `title` 或可访问名称发现。

### Cards and Evidence

- 普通卡片白底、Medium 边界、无阴影、无圆角。
- Hover 可使用 Graphite 黑白反转和最多 `-2px` 位移。
- 证据图片允许使用实色半透明黑色遮罩保证白字可读；禁止渐变遮罩。
- 多图证据使用 Subtle 分割线组织拼图；Hover/Focus 图片缩放上限为 `1.025`，不得使用滤镜、渐变遮罩或影响证据真实性的视觉处理。
- 白色正文面上的链接使用黑色文字和橙色下划线；Graphite 反转面使用白色文字和橙色下划线。橙色不得单独承担普通正文文字颜色。
- 竞品官网地址只允许 `http:` 和 `https:`；录入、导入归一化及最终链接渲染必须使用同一协议白名单。
- Graphite 反转卡片内的链接焦点使用橙色 outline，确保焦点与黑色背景至少 `3:1`。
- 可点击证据卡片必须暴露按钮语义和可聚焦状态，并支持 Enter/Space 打开详情；内部编辑、删除按钮不得触发卡片详情。
- 标签使用矩形，不使用药丸形圆角。

### Matrix

- 外框使用 Strong，内部单元格使用 Subtle。
- 表头可使用黑底白字；数据单元格保持白底黑字。
- 不对正文单元格使用橙色背景。
- Sticky 列不使用阴影，改用 Medium 分割线。

### Insight Findings

- 洞察结论位于横向对比之后，并继承当前激活 Tab 的数据边界；不新增顶层导航或独立全局洞察库。
- 单条洞察固定使用 `事实信号 → 共性模式 → 关键差异 → 机会假设 → 行动建议` 五阶段结构。允许阶段暂为空，空内容显示“待补充”，不得伪装成完成状态。
- 桌面端五阶段使用五列平面链；`760px` 以下转为单列纵向链，顺序保持 01→05，不得通过整页缩放或强制横向拖动阅读。
- 洞察卡片使用白底、Strong 外框、无圆角、无阴影。阶段内部使用 Subtle 分隔线；行动建议允许使用单个橙色数据面，其他阶段保持白底，避免超出橙色预算。
- 竞品与维度关联使用矩形灰白标签；证据回链使用白底黑字、Strong 边框和橙色下划线，点击后复用证据详情，不复制证据正文与图片。
- 洞察筛选只影响当前视图，不写入导出数据；空数据和无筛选结果使用不同文案。
- 洞察属于每个 workspace Tab 的 `insights[]`，与 `competitors`、`evidenceItems`、`comparisonData` 同级。Schema version 3 必须兼容旧 version 1/2 导入，旧 Tab 缺少洞察时归一化为 `[]`。
- 删除竞品、分析维度或证据时保留洞察，只解除对应 ID 引用；删除洞察不得改变其他研究数据。

### Dialogs, Forms, Rich Text, and Tooltips

- 弹窗白底、Strong 边框、无圆角、无阴影。
- 输入框白底、Subtle 边框；Focus 使用黑色边框和 `2px` 橙色 outline。
- 富文本工具栏保持纯 Icon + Tooltip；SVG 必须显式使用 `fill: none` 和 `stroke: currentColor`，避免旧规则同时填充与描边。
- Tooltip 使用黑底白字、Mono 标签、无圆角。

### Motion and Accessibility

- 动效只使用 `transform` 与 `opacity`，常规持续时间 `120ms–180ms`。
- `prefers-reduced-motion: reduce` 下移除非必要位移和过渡。
- Reduced Motion 下证据图片 Hover/Focus 的 `transform` 必须为 `none`，不能只把持续时间缩短。
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
