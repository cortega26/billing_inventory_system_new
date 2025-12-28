# Golden Paths

## Path 1: High-Speed Sell (The "Bread and Butter")
**Persona**: Cashier at peak hour.
**Goal**: Process a customer with 5 items in under 10 seconds.

### Steps:
1.  **Start**: System is already on `Sales` tab (`F1`). Cursor is in `Barcode` input.
2.  **Action**: User scans Item A (x2), Item B, Item C.
    -   *System Response*: "Beep" for each. Items appear in cart instantly. No popups.
3.  **Variation (Manual Qty)**: User scans Item D, types `*6` (multiply by 6), presses `Enter`.
    -   *System Response*: Item D Qty updates to 6.
4.  **Finalize**: User presses `Space` (Pay) or `F12` (Quick Complete Cash).
    -   *System Response*: Sale saved. Receipt prints (optional). Cart clears. Ready for next.

## Path 2: Rapid Inventory Update (Truck Unloading)
**Persona**: Store owner receiving a delivery.
**Goal**: Update stock for 20 items quickly.

### Steps:
1.  **Start**: Press `F2` (Inventory). Cursor in `Barcode`.
2.  **Action**: Scan incoming box of Soda.
    -   *System Response*: Table filters to "Soda". Row highly visible. Focus moves to "Add Stock" overlay (or similar).
3.  **Input**: Type `+24` (Adding a case). Press `Enter`.
    -   *System Response*: Stock updated. Toast message "Soda: 50 -> 74". Focus returns to Barcode.
4.  **Repeat**: Scan next item.

## Path 3: Morning Health Check (Analytics)
**Persona**: Manager opening the store.
**Goal**: See yesterday's performance and today's warnings.

### Steps:
1.  **Start**: Press `F5` (Dashboard).
2.  **View**:
    -   **Top Left**: "Yesterday's Sales" (Big Number). Green/Red arrow vs avg.
    -   **Top Right**: "Low Stock Alerts" (List). Items < MinStock.
3.  **Action**: Click/Select "Low Stock" widget.
    -   *System Response*: Jumps to `Inventory` tab (`F2`), pre-filtered to "Low Stock".
