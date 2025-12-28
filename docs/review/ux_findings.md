# UX Findings & Review

## 1. Core Journeys Mapping

### Journey A: New Sale (Scan-First)
1.  **Start**: User opens "Sales" tab.
2.  **Customer**: User can optionally select a customer (defaults to anonymous/walk-in?). *Observation: Input defaults to "Department number". Might be confusing for pure retail.*
3.  **Scan**: User focuses "Barcode" field (Ctrl+B) and scans item.
4.  **Interaction**: `SaleItemDialog` opens **modal** for every scan.
    -   *Friction*: User must press "Enter" to confirm quantity/price for every single item. This breaks the "beep-beep-beep" flow of high-volume retail.
5.  **Completion**: User presses "Complete Sale" (Ctrl+Enter).

### Journey B: Add Product by Scan (Inventory/Stock)
1.  **Start**: User opens "Inventory" tab.
2.  **Scan**: User focuses Barcode field and scans.
3.  **Result**: Table filters to show that item.
4.  **Edit**: User clicks "Edit" or uses context menu to update stock.
    -   *Friction*: No direct "Add Stock" shortcut. Must open Edit dialog.

### Journey C: Void / Return
1.  **Void (Current Sale)**: User can "Remove" items from the list via a button in the row.
    -   *Friction*: Mouse-heavy. No obvious keyboard shortcut to remove last scanned item.
2.  **Return (Past Sale)**: **MISSING**.
    -   *Critical Gap*: There is no dedicated interface to look up a past receipt and process a return/refund. User would likely have to manually calculate and open a "negative" sale or use an external process.

## 2. Friction Points

### 🛑 Critical Friction
-   **Modal Dialog on Scan**: The biggest blocker for "scan-first" speed. Every scan interrupts the flow.
    -   *Recommendation*: Implement "Quick Scan" toggle. When enabled, scanning auto-adds 1 unit.
-   **No Return Workflow**: Users cannot process refunds natively.
-   **Mouse Dependency**: Deleting items from a sale requires finding a small "Remove" button.

### ⚠️ Moderate Friction
-   **Dashboard Defaults**: Dashboard shows "Last 4 Weeks" by default. Retailers often care most about "Today" vs "Yesterday".
-   **Error Feedback**: Errors (e.g., "Product not found") rely on temporary status messages or popups. A dedicated "System Message" area that persists slightly longer or is more visible (red flash) could help.

## 3. Proposed Improvements (Immediate)

### Analytics / Dashboard
The current `DashboardView` is good but missing real-time operational alerts.
-   **Add**: "Today's Sales" card (currently only has Total over period).
-   **Add**: "Low Stock Alerts" widget.
-   **Refine**: "Top Products" is already present.

### Sales UI
-   **Quick Scan**: Add checkbox to skip confirmation dialog.
-   **Returns**: Needs a dedicated view or a "Mode" in Sales (e.g., "Refund Mode").

## 4. Analytics Panel Specification
*As requested, a minimal analytics panel to be added/refined:*
-   **Location**: `DashboardView` (Upgrade existing).
-   **New Metrics**:
    -   `Today's Sales` (Real-time count & value).
    -   `Low Stock` (List of items < threshold).
    -   `Top Products` (Already exists, ensure it defaults to Today or Week).
