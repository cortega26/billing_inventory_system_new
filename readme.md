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
- Multi-business support (one database per business)
- Simple and efficient UI designed for retail operations

## Running a second business

The same install can serve multiple businesses (for example, a minimarket and
a separate entrepreneurship such as CasaBea). Each business gets its own SQLite
database file and its own backup folder, so products, inventory, sales,
purchases, customers, and reports stay isolated.

To add a business, add one entry to the `businesses` list in the application
config (`~/.config/billing-inventory/app_config.json`), for example:

```json
"businesses": [
  {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
  {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"}
]
```

The new business's database is created automatically (with the full schema and
migrations) the first time it is selected at startup. When more than one
business is configured, a selector dialog appears at startup before the PIN
login; switching business requires restarting the application. Single-business
installs keep working exactly as before with no configuration changes.

## Technical Details

For complete technical specifications, business rules, and implementation details, please see [SPECIFICATIONS.md](SPECIFICATIONS.md).

## Dependencies

See `requirements.txt` for Python package dependencies.

## Setup

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

1. **Create the virtual environment**:
   ```bash
   uv venv --python 3.13
   ```

2. **Install Dependencies**:
   ```bash
   uv pip install -r requirements.lock
   ```

3. **Configuration**:
   - The system uses `app_config.json` for application settings.
   - Runtime settings live in `~/.config/billing-inventory/app_config.json`
     (outside the repo); the repo copy of `app_config.json` is a default
     template only and is not tracked by git.
   - Database is auto-initialized on first run at `billing_inventory.db`.

4. **Run the Application**:
   ```bash
   .venv/bin/python main.py
   ```

## Seguridad

- On first launch the application asks to set an access PIN (4-6 digits).
- The PIN is stored as a PBKDF2-SHA256 hash with a random per-install salt in
  `~/.config/billing-inventory/app_config.json` (outside the repo).
- If the PIN is forgotten: delete the `pin_hash` key from that file (or delete
  the whole file) and relaunch to re-arm first-run setup.
- After upgrading from an older install that stored a legacy hash, set a new
  PIN as described above; the legacy hash is rejected on purpose.
- Change the PIN after installing on a new machine or if the config file may
  have been exposed.

## Development

1. **Install Development Dependencies**:
   ```bash
   uv pip install -r requirements.lock
   ```

2. **Install Pre-commit Hooks** (one-time, optional but recommended):
   ```bash
   uvx pre-commit install
   ```

   To run the hooks once without installing them:
   ```bash
   uvx pre-commit run --all-files
   ```

3. **Run Tests**:
   ```bash
   .venv/bin/python -m pytest
   ```

4. **Linting & Formatting**:
   ```bash
   .venv/bin/ruff check .
   .venv/bin/black --check .
   .venv/bin/pyright
   ```

5. **Schema Drift Check**:
   ```bash
   .venv/bin/python scripts/check_schema_drift.py
   ```

After changing `requirements.txt` or `requirements-dev.txt`, regenerate the lockfile:
```bash
uv pip compile requirements.txt requirements-dev.txt --python-version 3.13 -o requirements.lock
```

## License

[License information goes here]
