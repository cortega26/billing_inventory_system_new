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

- Frequency: Weekly
- Retention: Last 2 weeks only
- Scope: All historical data
- Timing: No specific schedule required

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
- Language: English only

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
- Single language (English) UI

### Future Compatibility Notes

- Designed for CLP only
- No multi-currency expansion planned
- No additional theme support planned
- No multi-language support planned
  
