# Inventory and Billing System
![CI](https://github.com/cortega26/billing_inventory_system_new/actions/workflows/ci.yml/badge.svg)

An inventory and billing management system designed specifically for Chilean minimarket operations.

## Overview

This system manages:

- Product inventory with barcode support
- Customer management with department associations
- Sales and purchase tracking
- Basic analytics and reporting

## Key Features

- Barcode scanning support
- Weight-based product sales support
- Customer department tracking
- Chilean Peso (CLP) monetary operations
- Weekly automated backups
- Simple and efficient UI designed for retail operations

## Technical Details

For complete technical specifications, business rules, and implementation details, please see [SPECIFICATIONS.md](SPECIFICATIONS.md).

## Dependencies

See `requirements.txt` for Python package dependencies.

## Setup

1. **Install Dependencies**:
   ```bash
   uv pip install -r requirements.lock
   ```

2. **Configuration**:
   - The system uses `app_config.json` for application settings.
   - Database is auto-initialized on first run at `billing_inventory.db`.

3. **Run the Application**:
   ```bash
   python main.py
   ```

## Development

1. **Install Development Dependencies**:
   ```bash
   uv pip install -r requirements.lock
   ```

2. **Run Tests**:
   ```bash
   pytest
   ```

3. **Linting & Formatting**:
   ```bash
   ruff check .
   black --check .
   pyright
   ```

4. **Schema Drift Check**:
   ```bash
   python scripts/check_schema_drift.py
   ```

After changing `requirements.txt` or `requirements-dev.txt`, regenerate the lockfile:
```bash
uv pip compile requirements.txt requirements-dev.txt --python-version 3.13 -o requirements.lock
```

## License

[License information goes here]
