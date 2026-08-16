# Plan 016: Stop logging customer PII; make log files owner-only

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- services/customer_service.py services/receipt_service.py services/product_service.py utils/system/logger.py tests/test_system/test_logger.py tests/test_services/test_customer_service.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

The app deliberately protects its data: the SQLite DB is chmod 0600
(`database/database_manager.py:79`) and the config file is 0600. But
`inventory_system.log` is **0664 world-readable** (verified on disk), and the
services log Chilean customer identifiers (RUT-like `identifier_9`,
`identifier_3or4`) and name/ID search terms at INFO level, plus full SQL
statements with bound customer values at DEBUG. On the realistic deployment
(shared office PC), any local user can read customer identities and search
behavior from the logs without touching the protected DB. The DEBUG tier is
gated only by the constant `DEBUG_LEVEL = logging.INFO` (`config.py:78`) —
flipping one line dumps everything. This plan strips PII from log statements
and chmods log files to 0600 at creation.

## Current state

Files in scope and their roles:

- `services/customer_service.py` — the PII log sites (below).
- `services/receipt_service.py:99-102` — `send_via_whatsapp` logs `phone_number` (dead caller, but the line is live code).
- `services/product_service.py:299-300` — DEBUG lines dumping a raw DB row and `vars(product)` (prices).
- `utils/system/logger.py` — `setup_structured_logger` (lines 186-221) builds handlers; this is where permissions get fixed.
- `login_config.yaml:17-33` — defines the two `RotatingFileHandler`s.

PII log sites in `services/customer_service.py` (all verified):

```python
# :48  DEBUG — full identifier
logger.debug(f"Creating customer with identifier_9: {identifier_9}")

# :78-81  INFO — identifier in extra
logger.info("Customer created", extra={"customer_id": customer_id, "identifier_9": identifier_9})

# :85-88  ERROR — identifier in extra
logger.error("Failed to create customer", extra={"error": str(e), "identifier_9": identifier_9})

# :142-145  INFO — identifier_3or4 in extra
logger.info("Customer 3or4 identifier updated", extra={"customer_id": customer_id, "identifier_3or4": identifier_3or4})

# :256  DEBUG — kwargs contains name + identifiers
logger.debug(f"[update_customer] Starting with kwargs: {kwargs}")

# :306-307  DEBUG — full SQL + bound params (customer names + identifiers)
logger.debug(f"[update_customer] Executing SQL: {query}")
logger.debug(f"[update_customer] With parameters: {params}")

# :417-426  INFO + WARNING — identifier_9 in extra (get_customer_by_identifier_9)
logger.info("Customer retrieved by identifier_9", extra={"identifier_9": identifier_9})
logger.warning("Customer not found by identifier_9", extra={"identifier_9": identifier_9})

# :470-472  WARNING — identifier_9 embedded in the message text
logger.warning(f"Duplicate customer found with phone {customer.identifier_9} for department {identifier_3or4}")

# :559-562  INFO — raw search term (names / partial IDs)
logger.info("Customers searched", extra={"search_term": search_term, "count": len(customers)})
```

Also: `services/receipt_service.py:99-102` (`phone_number` in extra) and
`services/product_service.py:299-300`:

```python
logger.debug(f"Found product row: {row}")
logger.debug(f"Created product object: {vars(product)}")
```

Handler creation (no permission handling — files get the process umask,
typically 0664):

```python
# utils/system/logger.py:152-157 (inside setup_logger)
handler = logging.handlers.RotatingFileHandler(
    config.log_file, maxBytes=config.max_size, backupCount=config.backup_count,
    encoding="utf-8",
)
# setup_structured_logger (186-221) uses logging.config.dictConfig on login_config.yaml,
# plus a fallback logging.FileHandler(f"{LOGGER_NAME}.log") at line 215.
```

Test conventions that apply:

- `tests/test_system/test_logger.py` — `TestLogger` class with a
  `configured_logger` fixture and `tmp_path`-based `logger_test_dir`;
  `test_log_with_extra_fields` (line 158) shows the pattern for asserting on
  emitted records.
- `tests/test_services/test_customer_service.py` — real-DB service tests.
- IMPORTANT: the `StructuredLogger` sets `_logger.propagate = False`
  (logger.py:46), so pytest's `caplog` will NOT capture its records — capture
  tests must attach a handler directly to `structured_logger._logger`
  (the Step 5 test shows the shape).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_system/test_logger.py tests/test_services/test_customer_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |

## Scope

**In scope**:
- `services/customer_service.py` — the log statements listed above
- `services/receipt_service.py` — line 99-102 extra dict
- `services/product_service.py` — lines 299-300
- `utils/system/logger.py` — `setup_structured_logger` and `setup_logger`: chmod log files (and rotated backups) to 0600
- `tests/test_system/test_logger.py` — permission test
- `tests/test_services/test_customer_service.py` — no-PII-in-logs assertions
- `login_config.yaml` — no change needed (paths only); do not edit unless a test proves otherwise

**Out of scope** (do NOT touch):
- `utils/system/event_system.py` — its DEBUG `extra={"args": args}` logs only
  IDs (customer_id/product_id), not PII; leave as-is.
- The audit-log table (`AuditService.log_operation`) — the audit trail
  legitimately stores identifiers by design; only *log files* are in scope.
- Changing `DEBUG_LEVEL`, log levels, or the `StructuredLogger` class itself
  beyond the chmod addition.
- Any other service's log lines not listed (inventory/sale/purchase log IDs
  only, which is fine).

## Git workflow

- Branch: `advisor/016-log-pii-permissions`
- Commit per step; message style follows the repo (`sec: ...`, `tests: ...` — see `git log --oneline -10`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Strip PII from customer_service log statements

Edit `services/customer_service.py` per the table. Rule: identifiers
(`identifier_9`, `identifier_3or4`) and raw search terms never appear in any
log call — message text or `extra`. Use `customer_id` where available.

| Location | Current | Change to |
|----------|---------|-----------|
| :48 | `logger.debug(f"Creating customer with identifier_9: {identifier_9}")` | Delete the line (id not yet known; the INFO below covers it) |
| :78-81 | INFO extra `{"customer_id", "identifier_9"}` | extra = `{"customer_id": customer_id}` only |
| :85-88 | ERROR extra `{"error", "identifier_9"}` | extra = `{"error": str(e)}` only (drop identifier) |
| :142-145 | INFO extra `{"customer_id", "identifier_3or4"}` | extra = `{"customer_id": customer_id}` only |
| :256 | `logger.debug(f"[update_customer] Starting with kwargs: {kwargs}")` | Delete the line |
| :264-284 | DEBUG lines logging `kwargs['name']` / identifier values | Delete the value-bearing DEBUG lines (keep structural debug lines that log no values, e.g. "Starting field validation" is fine to keep if it logs no data) |
| :306-307 | `logger.debug(... SQL: {query}")` + `params` | Delete both lines |
| :417-426 | INFO/WARNING extra `{"identifier_9"}` | extra = `{}` (or drop `extra` entirely); keep the message |
| :470-472 | `f"Duplicate customer found with phone {customer.identifier_9} for department {identifier_3or4}"` | Rebuild the message with IDs only, dropping both identifier values: `f"Duplicate customer found: customer_id {customer.id} matches multiple department identifiers"` — check the `customer` object has an `id` attribute; if not, restructure to include `customer_id` from the loop context |
| :559-562 | INFO extra `{"search_term": ...}` | extra = `{"count": len(customers)}` only |

There may be additional nearby DEBUG lines that echo input values in the same
functions (`update_customer` block ~256-330); remove any that print
`kwargs`, `name`, or identifier values.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_customer_service.py` → all pass (tests must not depend on identifiers appearing in logs; the new assertions in Step 3 pin the behavior).

### Step 2: Strip PII from receipt_service and product_service debug lines

- `services/receipt_service.py:99-102` — remove `"phone_number"` from the
  `extra` dict (keep `sale_id`).
- `services/product_service.py:299-300` — delete the two DEBUG lines
  (`Found product row: {row}` and `Created product object: {vars(product)}`).
  These are diagnostics for a single lookup and serve no load-bearing purpose.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py tests/test_services/test_product_service.py` → all pass.

### Step 3: chmod log files (and rotated backups) to 0600 at setup

In `utils/system/logger.py`, inside `setup_structured_logger` (after
`logging.config.dictConfig(config)` and also on the fallback path), add a
helper that chmods every log file the configuration touches:

```python
import os

def _harden_log_file_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # file may not exist yet; rotation creates it later
```

Apply it:
- After `dictConfig`, iterate `(config.get("handlers") or {}).values()`; for
  each handler with a `"filename"` key, chmod that file **and** its rotated
  siblings `f"{filename}.1"` ... `.N` up to `backupCount` (the handler entry
  may not carry `backupCount` for the console handler — guard with `.get`).
  Also chmod the configured file in the *fallback* path
  (`logging.FileHandler(f"{LOGGER_NAME}.log")`).
- Prefer a single shared helper called from both paths; do not introduce
  duplicated logic.

Note: rotated files (`inventory_system.log.1` ...) are created at rotation
time by `RotatingFileHandler` with the process umask, so harden them too (the
loop above covers existing ones; future rotations are re-covered every app
start since setup runs at startup).

**Verify**: write a small probe with the project venv:
`.venv/bin/python -c "import os, sys; sys.path.insert(0, '.'); from utils.system.logger import setup_structured_logger; setup_structured_logger(); print(oct(os.stat('inventory_system.log').st_mode & 0o777))"`
→ prints `0o600`. (Clean up: the probe recreates `inventory_system.log` at the repo root; that's expected.)

### Step 4: One-time cleanup of existing world-readable logs

On this machine the repo-root logs `inventory_system.log` and
`inventory_system_error.log` (+ rotated `.1`–`.5`) are currently 0664. After
Step 3's code lands, run once:
`chmod 600 inventory_system.log* inventory_system_error.log*`
and record the command in the commit message body (it is a one-time ops step,
not code). Do NOT add these files to git.

**Verify**: `ls -la inventory_system.log*` → `-rw-------`.

### Step 5: Add regression tests

In `tests/test_system/test_logger.py`, inside `TestLogger` (follow the
`configured_logger` fixture and `test_log_rotation` at line 140 for the
rotated-file pattern):

- `test_log_files_are_owner_only` — using the `configured_logger` fixture and
  its `logger_test_dir`, assert every `*.log*` file in the dir has mode 0600:
  `os.stat(f).st_mode & 0o777 == 0o600`.
- `test_rotated_log_files_are_owner_only` — force a rotation (follow
  `test_log_rotation`'s mechanism), then assert the `.1` backup is 0600.

In `tests/test_services/test_customer_service.py` (real-DB service tests):

- `test_customer_logs_contain_no_identifiers` — create a customer (with an
  `identifier_3or4`), then search customers by name. Capture the log records
  by attaching a plain handler to the StructuredLogger's underlying logger
  (the `StructuredLogger` sets `propagate = False`, so pytest's `caplog`
  will NOT see these records — do not use caplog):

```python
def test_customer_logs_contain_no_identifiers(
    self, customer_service, sample_customer
):
    import logging
    from utils.system.logger import logger as structured_logger

    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    structured_logger._logger.addHandler(handler)
    try:
        customer_service.create_customer(
            identifier_9="912345678", identifier_3or4="123", name="Jane Doe"
        )
        customer_service.search_customers("Jane")
    finally:
        structured_logger._logger.removeHandler(handler)

    combined = "\n".join(r.getMessage() for r in records)
    assert "912345678" not in combined
    assert "123" not in combined
    assert "Jane Doe" not in combined
```

  Match the existing `test_customer_service.py` fixture names (check the file;
  `sample_customer` exists in `test_sale_service.py` — use whatever customer
  fixture/helper the customer test file defines; the pattern above is the
  shape, the fixtures are per-file). The record message is the JSON payload
  with `extra` merged in, so this catches both message-text and extra PII.

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_logger.py tests/test_services/test_customer_service.py` → all pass, including the new tests.

### Step 6: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0
- `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0

## Test plan

Covered in Step 5. New tests:

| Test | File | Case |
|------|------|------|
| test_log_files_are_owner_only | test_logger.py | fresh log files 0600 |
| test_rotated_log_files_are_owner_only | test_logger.py | rotated backups 0600 |
| test_customer_logs_contain_no_identifiers | test_customer_service.py | no identifier_9/3or4/search-term text in any log record during create + search |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg -n "identifier_9|identifier_3or4|search_term|vars\(product\)|Executing SQL" services/customer_service.py services/receipt_service.py services/product_service.py | rg -i "log|debug|info|warning|error|extra"` returns no log statements (allow the `AuditService.log_operation` calls, which legitimately store identifiers in the audit table)
- [ ] `utils/system/logger.py` contains the `0o600` chmod logic covering setup and fallback paths
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- You find that any **test** asserts on the PII log content (that would mean
  removing the PII breaks an intentional contract — report instead of
  rewriting the test).
- The fix appears to require touching an out-of-scope file.

## Maintenance notes

- Future code must not add customer identifiers or raw search terms to log
  messages — the audit table (`AuditService.log_operation`) is the sanctioned
  place for audit data; log files are not.
- `config.py:78` `DEBUG_LEVEL` flipping to DEBUG is now safe for customer PII,
  but the product/price debug lines were removed — debug workflows that relied
  on them must use the audit table instead.
- A reviewer should scrutinize: the two delete-lines changes in
  `product_service.py` (make sure nothing else reads those debug lines) and
  that the chmod helper doesn't crash when a log path is a directory or a
  symlink (the `except OSError` guard covers it).
