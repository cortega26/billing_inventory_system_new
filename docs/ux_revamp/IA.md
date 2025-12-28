# Information Architecture (IA) - Retail POS

## Design Philosophy
**"Keyboard-First, Scan-Driven"**
The interface is designed for minimarket operators who need speed. The mouse is a fallback, not the primary input method.

## 1. Global Navigation (Tabs)
Mnemonic: **F-Keys** for rapid switching.

| Tab | Hotkey | Priority | Purpose |
| :--- | :--- | :--- | :--- |
| **Sales (POS)** | `F1` | **High** | Core activity. Scan, Sell, Return. |
| **Inventory** | `F2` | **High** | Stock checks, Quick updates, Price checks. |
| **Products** | `F3` | Medium | Deep product management (Create, Edit details). |
| **Customers** | `F4` | Medium | Customer lookup, Pay tab/debt (Future). |
| **Dashboard** | `F5` | Low | Daily stats, Opening/Closing shifts. |
| **Purchases** | `F6` | Low | Inbound stock (Suppliers). |

## 2. Screen Specifications

### A. Sales (POS) - `F1`
**Layout**: Two-Pane (Left: Cart, Right: Context/Actions)
- **Focus Default**: Barcode Input.
- **Modes**:
    1.  **Scan Mode** (Default): Scanning adds to cart.
    2.  **Command Mode** (Triggered by `/` or `Ctrl+Space`): Type commands like `qty 5`, `disc 10%`, `return`.
- **Key Elements**:
    -   **Cart Grid**: Large font, high contrast. Columns: Qty, Name, Price, Total.
    -   **Total Banner**: Massive font size (e.g., 48pt) visible from 2 meters.
    -   **Status Bar**: "Ready to Scan" (Green) vs "Processing" (Yellow) vs "Error" (Red).

### B. Inventory - `F2`
**Layout**: Search/Filter Header + Data Grid
- **Focus Default**: Barcode/Search Input.
- **Quick Action**:
    -   Scan Item -> row highlights -> `Enter` to "Quick Edit Stock".
    -   `Space` -> Toggle "Stock Check Mode" (Read-only price check).

## 3. Keyboard Shortcut Strategy

| Action | Shortcut | Context |
| :--- | :--- | :--- |
| **Focus Scan** | `Ctrl+B` | Global |
| **Complete/Pay** | `F12` or `Ctrl+Enter` | POS |
| **Cancel/Clear** | `Esc` | Global |
| **Search Product** | `Ctrl+F` | Global |
| **New Sale** | `Ctrl+N` | POS |
| **Void Item** | `Del` | POS (Selected Row) |
| **Qty Up/Down** | `+` / `-` | POS (Selected Row) |

## 4. Visual Feedback
- **Success Tone**: High beep (Scan OK).
- **Error Tone**: Low buzz (Not Found, Low Stock).
- **Visual Flash**: Screen border flashes Green (OK) or Red (Error) for peripheral visibility.
