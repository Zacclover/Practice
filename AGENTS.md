# Project Agent Rules

## Visual source of truth

Before adding or modifying any UI, read and follow the repository-root `DESIGN.md`.

All new features, pages, dialogs, states, buttons, icons, cards, forms, rich-text controls and matrix UI must conform to **Spatial Insight Orange Industrial**. Reuse its tokens and component rules; do not introduce an independent palette, radius, shadow, gradient, typography or icon language.

If a requested design change intentionally conflicts with `DESIGN.md`, update `DESIGN.md`, its visual contract tests and the affected UI in the same change.

## Functional safety

Visual work must not change DOM IDs, storage formats, migration behavior, import/export semantics, sanitization, evidence relationships or matrix data logic unless the task explicitly requires it.

## Code comments

Keep Chinese comments for each HTML, CSS and JavaScript feature section, explaining what that section implements.
