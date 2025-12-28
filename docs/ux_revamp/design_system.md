# Design System: Cortex Billing & Inventory (v1.0)

> [!NOTE]
> This design system uses abstract tokens (e.g., `--color-primary`). Since the application is built with PySide6 (Qt), these tokens are intended to be mapped to `QPalette` roles OR used in specific QSS spreadsheets.

## 1. Principles
-   **Keyboard First**: Focus states must be highly visible. Tab order must be logical.
-   **High Density**: Inventory/Billing systems require seeing 10-20 items at once. Compact spacing is preferred using standard desktop paradigms.
-   **High Contrast**: Text must be legible (WCAG AA minimum).

## 2. Color Palette

### Base Scale (Neutral)
Used for backgrounds, borders, and text.
-   `--color-bg-base`: `#FFFFFF` (Main Background)
-   `--color-bg-alt`: `#F5F5F5` (Table Headers, Disabled Inputs)
-   `--color-border`: `#CCCCCC` (Input Borders, Dividers)
-   `--color-text-primary`: `#212121` (Main content)
-   `--color-text-secondary`: `#666666` (Labels, Help text)
-   `--color-text-disabled`: `#9E9E9E`

### Primary Action (Brand)
-   `--color-primary`: `#1976D2` (Focus Rings, Selected Text, Active Tabs)
-   `--color-primary-dark`: `#1565C0` (Hover states)
-   `--color-primary-light`: `#BBDEFB` (Selection Backgrounds)

### Semantics (Functional)
-   **Success** (Completion, Valid Scans):
    -   `--color-success`: `#4CAF50` (Buttons, Status Icons)
    -   `--color-success-bg`: `#E8F5E9` (Success Toasts/Rows)
-   **Error** (Destructive, Invalid Scans):
    -   `--color-error`: `#D32F2F` (Delete Buttons, Critical Alerts)
    -   `--color-error-bg`: `#FFEBEE` (Input Error State - *Existing Usage*)
-   **Warning** (Low Stock):
    -   `--color-warning`: `#FBC02D`
    -   `--color-warning-bg`: `#FFFDE7`

## 3. Typography
**Font Family**: System Default (Segoe UI on Windows). Reliability > Custom Fonts.

| Token | Size | Weight | Usage |
| :--- | :--- | :--- | :--- |
| `--font-display` | 24px | Bold | Total Amounts (`$ 1.250`) |
| `--font-heading` | 18px | Semibold | Modal Titles, Section Headers |
| `--font-body` | 14px | Regular | Table Content, Input Text |
| `--font-label` | 12px | Medium | Input Labels, Table Headers |
| `--font-caption` | 11px | Regular | Help Text, Timestamps |

## 4. Spacing & Layout
Base unit: **4px**.

-   `--space-xs`: 4px (Tight grouping)
-   `--space-sm`: 8px (Input padding, condensed lists)
-   `--space-md`: 16px (Standard containment, form rows)
-   `--space-lg`: 24px (Section separation)
-   `--space-xl`: 32px (Screen margins)

## 5. Components

### Buttons
**Standard Height**: 32px (Compact) / 36px (Regular)

1.  **Primary Button** (Complete Sale):
    -   Bg: `--color-success`
    -   Text: `#FFFFFF`
    -   Hover: `--color-primary-dark` or darker green
2.  **Destructive Button** (Cancel/Void):
    -   Bg: `--color-error`
    -   Text: `#FFFFFF`
3.  **Secondary/Ghost Button** (Cancel Dialog):
    -   Bg: `Transparent` or `--color-bg-alt`
    -   Border: `1px solid --color-border`
    -   Text: `--color-text-primary`

### Inputs
-   **Height**: 30px
-   **Padding**: `0 --space-sm`
-   **Border**: `1px solid --color-border`
-   **Focus State** (Critical):
    -   Border: `2px solid --color-primary`
    -   Background: `#FFFFFF`

### Tables (QTableWidget)
-   **Row Height**: 28px (High density)
-   **Header**: Bg `--color-bg-alt`, Text `--font-label` (Bold/Medium)
-   **Selection**:
    -   Bg: `--color-primary-light` (or System Highlight)
    -   Text: `--color-text-primary` (Keep contrast high)
-   **Grid Lines**: Visible, `--color-border` (Light grey)
-   **Zebra Striping**: Optional (`--color-bg-alt` on even rows)

### Cards / Panels
-   **Border**: `1px solid --color-border`
-   **Radius**: `4px`
-   **Shadow**: None (Flat design for performance/clarity) or Minimal

## 6. Keyboard & Focus
-   **Focus Ring**: Every interactive element (Input, Button, Row) MUST have a visible focus indicator.
-   **Tab Order**: Left-to-Right, Top-to-Bottom.
-   **Traps**: Modals must trap focus.

## 7. Migration Guide
Existing hardcoded values vs Target Tokens:

| Current Code | Target Token |
| :--- | :--- |
| `#4CAF50` | `--color-success` |
| `#f44336` | `--color-error` |
| `#ffebee` | `--color-error-bg` |
| `#f5f5f5` | `--color-bg-alt` |
| `font-size: 16px; bold` | `--font-heading` or custom `--font-total` |
