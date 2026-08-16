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
