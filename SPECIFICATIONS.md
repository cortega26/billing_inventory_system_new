# El Rincón de Ébano - System Specifications

## Core Business Rules

### Currency and Monetary Operations

- Currency: Chilean Peso (CLP) only
- All prices must be integers (no decimals)
- Maximum price: 1.000.000 CLP (cost_price and sell_price)
- Display format: Use dots as thousand separators (e.g., 1.000.000)
- Calculations: Round each operation individually

### Product Quantities

- Standard products: Integer quantities
- Weight-based products:
  - Unit: Kilograms only
  - Precision: 3 decimal places
  - Minimum: 0.001 kg
  - Display: Show up to 3 decimal places

### Customer Management

#### Cell Phone Numbers (9-digit Identifier)

- Must start with digit '9'
- Exactly 9 digits long
- Examples: 912345678, 987654321
- Must be unique per customer
- One customer can only have one department

#### Department Numbers (3/4-digit Identifier)

- Length: 3 or 4 digits
- Must not start with 0
- Can be associated with multiple customers
- Associations can be updated anytime
- No historical tracking needed except in sales records

### Operations Volume

#### Sales

- Daily average: 10 sales
- Items per sale: 2-3 items
- Deletion: Allowed anytime
- No time restrictions on modifications
- All revenue, profit, statistics, turnover, and movement reports exclude
  cancelled (`status = 'cancelled'`) sales; the sales list retains them for
  audit.

#### Purchases

- Weekly average: 3 purchases
- Items per purchase: ~20 items
- No historical price tracking needed

### Barcode Operations

- Successful scans: Play sound
- Failed scans: Show message only
- Auto-clear input after successful scan
- Optimized for rapid minimarket operations

### Data Backup

- Frequency: Automatic daily backups
- Retention: Last 7 days
- Scope: All historical data
- Timing: Scheduler checks the configured interval and creates a backup when the last one is older than that interval
- Backups are stored per business under `backups/<business_id>/`

## Multi-business

The same app can serve multiple businesses (for example, the main minimarket
and CasaBea, a cinnamon-roll entrepreneurship). Each business owns a separate
SQLite database file, so products, inventory, sales, purchases, customers, and
reports are fully isolated between businesses.

- **One database file per business.** The schema is identical for every
  business and migrations run automatically when a new business's database is
  first used, so a new business starts with the full schema.
- **Selection at startup.** When more than one business is configured, the app
  shows a selector dialog before the PIN login. With a single business the
  selector is skipped and behavior is unchanged from a single-business install.
- **Restart to switch.** The active business is chosen at startup; changing it
  in-app requires restarting the application. There is no runtime
  re-initialization of the database connection.
- **In-app switch.** Cambio de negocio: en el arranque (selector) o desde
  Archivo → Cambiar de negocio; se aplica al reiniciar la aplicación.
- **Backups per business.** Backup files land in `backups/<business_id>/` and
  retention applies per business.
- **Customers are per-business.** There is no customer sync between businesses
  today; shared customer directories can be a future feature.
- **Adding a third business** only requires adding one entry to the `businesses`
  list in the application config; no code changes are needed.
- Existing installs without a `businesses` entry in config behave exactly as
  before: an implicit single "default" business using the current database
  file.

## Technical Implementation

### Database Requirements

- SQLite with WAL mode
- Enforce foreign key constraints
- Decimal storage: String format, 3 decimal places
- Price storage: Integer values

### User Interface

- Monetary display: Dot separators everywhere
- Supported themes: default, dark, light only
- Sound effects: Barcode scans only
- Language: Spanish. New or modified UI strings must be in Spanish (decision 2026-08-15).

### Data Validation Rules

#### Customer Names

- Allowed: Letters, Spanish accents, spaces
- Pattern: ^[A-Za-zÁÉÍÓÚÑáéíóúñ ]+$
- Maximum length: 50 characters

#### Cell Phone Numbers

- Must start with 9
- Exactly 9 digits
- Must be unique

#### Department Numbers

- 3 or 4 digits
- Cannot start with 0
- Can have multiple associated customers

### Performance Specifications

- Annual volume: ~5,000 sales, ~156 purchases
- No strict performance requirements
- Optimize common searches:
  - Customer lookups
  - Barcode scans
  - Product searches
  - Sales history

### Security Specifications

- No user roles required
- Basic input sanitization only
- No special security requirements

### System Requirements

- Self-contained system
- No external integrations
- No multi-currency support
- Spanish-first UI; no English migration is planned.

### Future Compatibility Notes

- Designed for CLP only
- No multi-currency expansion planned
- No additional theme support planned
- No full multi-language support planned; Spanish is the single UI language.
