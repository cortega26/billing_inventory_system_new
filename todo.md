# Execution To-Do — Plans 015–020

Consult before every change. Check off as work completes.

## Program state

- [x] spec.md written (execution spec for plans 015–020)
- [x] Plan 015 implemented + verified in worktree
- [x] Plan 015 reviewed (done criteria, scope, diff)
- [x] Plan 015 merged (094d15f), pushed, worktree cleaned, plans/README + archive updated
- [x] Plan 019 implemented + verified in worktree
- [x] Plan 019 reviewed
- [x] Plan 019 merged (8b34c81), pushed, cleaned, index updated
- [x] Plan 016 implemented + verified in worktree
- [x] Plan 016 reviewed
- [x] Plan 016 merged, pushed, cleaned, index updated
- [x] Plan 017 implemented + verified in worktree
- [x] Plan 017 reviewed
- [x] Plan 017 merged, pushed, cleaned, index updated
- [x] Plan 018 implemented + verified in worktree
- [x] Plan 018 reviewed
- [x] Plan 018 merged (950085b), pushed, cleaned, index updated
- [x] Plan 020 implemented + verified in worktree
- [x] Plan 020 reviewed
- [x] Plan 020 merged (c815fd4), pushed, cleaned, index updated
- [x] Midpoint gap review done 2026-08-15 (fresh agent): nothing blocks 017/018/020; found InventoryAgingMetric status gap -> follow-up micro-plan
- [x] Final full-suite integration run on main (349 passed, 1 skipped)
- [ ] All plans archived; todo.md complete; `git push origin main` final

## Plan 015 — cancelled sales excluded from reports

- [x] Executor worktree created (/tmp/opencode/bi-plan015, advisor/015-cancelled-sales-reports)
- [x] Executor implemented + committed (5b924e2 fix, 02234d1 tests)
- [x] Executor report received: COMPLETE; 7 UI-test failures claimed pre-existing
- [x] Orchestrator verified: worktree failures were missing-runtime-dirs artifact (9/9 pass in main)
- [x] Orchestrator re-ran done criteria + read diff (APPROVE)
- [x] Merged 094d15f, pushed, cleaned, archived, DONE

## Plan 019 — analytics index-usable

- [x] Worktree + executor dispatch
- [x] Implementation + verification in worktree
- [x] Orchestrator review
- [x] Merged 8b34c81, pushed, cleaned, archived, DONE

## Plan 016 — log PII + permissions

- [x] Worktree + executor dispatch
- [x] Implementation + verification in worktree
- [x] Orchestrator review
- [x] Merged ca087bf, pushed, cleaned, archived, DONE

## Plan 017 — validate_money fractional strings

- [ ] Worktree + executor dispatch
- [ ] Implementation + verification in worktree
- [ ] Orchestrator review
- [ ] Merge/push/clean/archive

## Plan 018 — UI inventory edits through ledger

- [ ] Worktree + executor dispatch
- [ ] Implementation + verification in worktree
- [ ] Orchestrator review
- [ ] Merge/push/clean/archive

## Plan 020 — workflow + coordinator sad-path tests

- [ ] Worktree + executor dispatch
- [ ] Implementation + verification in worktree
- [ ] Orchestrator review
- [ ] Merge/push/clean/archive

## Plan 022 (CasaBea) — multi-business support

- [x] Recon: bootstrap seams verified (init_db(db_path), DatabaseManager.initialize(path), backup_service.py:52, main.py flow)
- [x] Plan 022 written (plans/022-casabea-multi-business.md) + spec.md section
- [x] Phase A: business registry in config + tests
- [x] Phase B: startup selector dialog + wiring + UI tests
- [x] Phase C: per-business backups + tests
- [x] Phase D: docs + business-switch tests + full verification
- [x] Phase E: analytics engine active-business path + isolation test
- [x] Reviewed (APPROVE), merged 5bbed86, pushed, cleaned, archived, DONE

## Plan 023 (CasaBea customer seed) — copy_customers script

- [x] Recon: customer schema + scripts pattern verified (127 rows, identity-only copy decision)
- [x] Plan 023 written (plans/023-copy-customers-between-businesses.md) + spec.md section
- [x] Executor: implemented script + 6 tests (STOPPED once on schema drift → plan revised)
- [x] Reviewed (APPROVE), merged 4bfaa74, pushed, cleaned, archived, DONE
- [x] Dry-run + real seed executed 2026-08-16 (see session report)

## Plan 024 (schema drift reconciliation) — customer credit columns

- [x] Recon: live DDL vs repo sources verified (all rows at defaults; alembic stamped at head)
- [x] Plan 024 written (plans/024-customer-credit-columns.md) + spec.md section
- [x] Executor: model + schema.sql + migration + tests (no STOP)
- [x] Reviewed (APPROVE), merged 955e4c2, pushed, cleaned, archived, DONE
- [x] No-op verified against a COPY of the live DB (127 customers intact, head 652b05c0c11e)

## Plan 025 (in-app business switch + config self-healing)

- [x] Recon: main_window menu structure (create_menu list), config default-shape tests located
- [x] Plan 025 written + spec.md section
- [ ] Executor: menu action + config defaults + tests in worktree
- [x] Reviewed (APPROVE), merged, pushed, cleaned, archived, DONE
- [ ] Manual launch check: selector at startup + Archivo → Cambiar de negocio (user action)

## Plan 026 (config-nuking test bug) — isolate_config teardown must never save

- [x] Root cause: tests calling Config._reset_for_testing() bare leave _config_file=None; autouse teardown reset_to_defaults() writes the REAL config (nuked PIN + registry on the dev machine; also created stray repo-root nonexistent.json)
- [x] Plan 026 written + spec.md section
- [x] Executor: teardown state-only + fixed leaks + regression test (3 documented deviations, all correct)
- [x] Reviewed (APPROVE), merged, pushed, cleaned, archived, DONE
- [x] Full suite in main: 389 passed; real config mtime+content verified UNTOUCHED

## Plan 027 (per-business dashboard KPI profiles)

- [x] Recon: MetricWidget composition, dashboard date-range methods, no dashboard UI test yet, no units-total method
- [x] Plan 027 written + spec.md section
- [x] Executor: registry field + profiles + units method + tests (5 commits)
- [x] Reviewed (APPROVE), merged 4027e03, pushed, cleaned, archived, DONE
- [ ] User action: set dashboard profile for casabea in real config (instructions in final report)

## Plan 028 (Codacy SQLi warnings on scripts)

- [x] Analysis: all 6 sites interpolate internal constants (false positives); 4 convertible to bound pragma functions, 2 need documented nosec B608
- [x] Plan 028 written + spec.md section; casabea dashboard profile set to production in real config (backed up)
- [x] Executor: 4 bound pragma conversions + 2 nosec sites (4 commits)
- [x] Reviewed (APPROVE), merged a90e8fe, pushed, cleaned, archived, DONE

## Plan 029 (dead-code sweep — 33 symbols) / Plan 030 (duplication)

- [x] Audit complete: 33 fully-dead + 15 test-only (kept); 4 duplication blocks verified
- [x] Plans 029/030 written + spec.md section
- [x] Executor 029: deleted 33 symbols + orphaned imports (-420 lines, guard clean)
- [x] Reviewed (APPROVE), merged ceb9c16, pushed, cleaned, archived, DONE
- [x] Executor 030: 4 blocks consolidated + LogLevel deleted (6 commits)
- [x] Reviewed (APPROVE), merged 2ddeff1, pushed, cleaned, archived, DONE

## Backlog round: plans 031 (movements UTC), 032 (rotation hardening), 033 (analytics wrappers)

- [x] Plans 031/032/033 written + spec.md section; older backlog items closed with decisions
- [x] Executor 031 → reviewed (APPROVE), merged fe14573, archived
- [x] Executor 032 → STOP+amendment (dictConfig mid-import) → APPROVE, merged 2a8e034, archived
- [x] Executor 033 → review caught stale-cache regression → amendment → APPROVE, merged 7d9be9e, archived
- [ ] Propose next: returns/refunds workflow + CSV import (product decisions — pending)
