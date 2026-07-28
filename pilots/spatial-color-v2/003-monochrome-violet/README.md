## Variant: 黑白 + 紫色光效

### Design stance
以黑白灰承担绝大部分信息，只在关键交互和空间光中使用紫色。

### Key choices
- Layout：与当前竞品洞察台一致，顶部全宽工作区、固定宽度 Tab、卡片与矩阵。
- Color：该方案独立色彩与材质 Token。
- Interaction：Tab 选中、按钮反馈、卡片 Hover 海拔变化。
- Accessibility：实色数据区、清晰焦点与 reduced-motion 降级。

### Trade-offs
- Strong at：最克制、最耐看，数据可读性和专业感最佳。
- Weak at：品牌情绪更冷，沉浸感依赖精细材质和动效，开发要求较高。

### Best for
用于对比 Spatial Insight 的品牌色方向，不是生产代码。

### V2 refinement
- Tab 锁定单行省略，不再换行。
- 采用锐利无倒角的工业几何系统。
- 增加坐标网格、区块编号、十字标记和装饰分割线。
- 标题/UI 使用 Space Grotesk，技术标签使用 IBM Plex Mono。
- 主要操作统一为 1.7px 方端线性 SVG 图标。
