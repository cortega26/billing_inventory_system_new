# Friction Points & Risk Analysis

## 1. Critical Friction (Efficiency Killers)
| Severity | Issue | Impact | Fix Strategy |
| :--- | :--- | :--- | :--- |
| **High** | **Modal Dialog on Scan** | Stops flow for every single item. Makes 10-item sale take 10x longer. | **Default to Quick Scan**. Only show dialog if product has missing price/info or explicit "Manual Entry" mode. |
| **High** | **No "Return" Mode** | Cashiers cannot process refunds. Must calculate math manually or fake a negative sale (if allowed). | Add "Refund Mode" toggle. Scans add as negative quantity. |
| **High** | **Mouse Dependency** | "Remove Item" requires clicking a small button. | Add `Del` key support for selected row. Add `Ctrl+Z` for "Undo last scan". |

## 2. Operational Risks (Minimarket Context)
| Risk | Scenario | Consequence | Mitigation |
| :--- | :--- | :--- | :--- |
| **Lost Sale** | System crashes or "Clear" hit by accident. | Customer waits, Cashier flustered. | **Hold Cart**: Auto-save draft sale locally every change. |
| **Blind Scanning** | User scans 5 items but cursor wasn't in focus. | Items not added. Cashier notices too late. | **Global Listener**: Catch barcode scanner input even if focus is lost (RFID/HID mode), or aggressively refocus input after every UI event. |
| **Price Error** | Scanning an item with outdated price. | Loss of margin. | **Price Check Mode**: Easy way to scan just to see price (big popup) without adding to cart. |

## 3. Implementation Blockers
-   **Touch vs Keyboard**: Current UI mixes dense tables (Mouse) with some inputs. Hard to hit targets on touch screens if deployed on tablets.
-   **Screen Real Estate**: Tables often hide columns on smaller screens (1366x768 is common in old POS).
