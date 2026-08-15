# Plan 013: Reconcile docs/backlogs with reality; language decision; bandit wire-or-drop

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: the repo has uncommitted changes; the excerpts
> below reflect the working tree. Open each cited file and confirm the excerpt
> matches. On a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: none (do this before writing any new UI strings)
- **Category**: docs
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

The repo's own audit/backlog docs are the bootstrap for future AI sessions
("re-audit without re-litigating"), and they now contradict reality in four
ways — each of which costs a future session real work:

1. **Auth is reported missing everywhere, but implemented.** PIN login landed
   in commit `9ff8aee` (`main.py:181-187`, `ui/login_dialog.py`), yet
   `docs/audit/industry_grade_backlog.md:57-71` [IG-1.1] has no "completed"
   status and sits on the resumption list at `:219`;
   `docs/review/industry_grade_audit_2026-04-07.md:35,97` says auth "sigue
   faltando"; `docs/review/security_findings.md:13` says the app "lacks any
   login or authentication mechanism". A fresh session would re-implement
   existing functionality.
2. **Two backlog items are implemented but still pending.**
   `docs/audit/structural_quality_backlog.md:286-340` lists SQ-B.3 (extract
   UpdateSaleWorkflow) and SQ-B.4 (post-commit mutation coordinator) as P1
   pending, with "Suggested execution order" at `:573-581` telling the next
   session to "Implement Phase SQ-B" — both modules exist
   (`services/update_sale_workflow.py`, `services/mutation_coordinator.py`) and
   AGENTS.md codifies the coordinator as the standard.
3. **The language contract contradicts itself.** SPECIFICATIONS.md mandates
   "English-first" (`:83,126,133`) while AGENTS.md and every UI string are
   Spanish; the contradiction is even flagged in
   `docs/review/repo_ai_audit_prompt.md:24`.
4. **bandit + a security script are installed but never run**, while
   `docs/review/security_findings.md:35-39` claims they run in CI/CD.

## Current state

- `docs/audit/industry_grade_backlog.md:57-71` — [IG-1.1] PIN auth, no status;
  `:219` — on the resume list.
- `docs/audit/structural_quality_backlog.md:286-340` — SQ-B.3/SQ-B.4 pending;
  `:573-581` — execution order directing "Implement Phase SQ-B".
- `docs/review/industry_grade_audit_2026-04-07.md:35,97` — auth "sigue faltando".
- `docs/review/security_findings.md:11-15` — "lacks any login"; `:35-39` —
  bandit + `scripts/security_check.ps1` claimed in CI/CD.
- `docs/review/db_findings.md:13-21` — CHECK constraints / ON DELETE RESTRICT
  (resolved in `schema.sql`); `docs/review/perf.md:9-18` — indexes (resolved);
  `docs/review/ux_findings.md` — mostly resolved; the ONLY open item:
  "Return workflow MISSING" (`:23-24`).
- `SPECIFICATIONS.md:83,126,133` — English-first lines.
- `AGENTS.md` Repo Notes — "New or modified UI strings must be in Spanish".
- `requirements-dev.txt:11` — `bandit>=1.7.0`; `.github/workflows/ci.yml` — no
  bandit step; `scripts/security_check.ps1` — git-tracked PowerShell.
- `pyproject.toml:29` — `filterwarnings = ["ignore::DeprecationWarning:reportlab.*"]`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Docs-only plan: suite sanity | `.venv/bin/python -m pytest -q` | all pass (nothing should change) |
| bandit probe (decision data) | `.venv/bin/bandit -q -r database services utils --skip B101 2>&1 \| tail -20` | see Step 5; record the finding count |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `docs/audit/industry_grade_backlog.md`, `docs/audit/structural_quality_backlog.md`
- `docs/review/security_findings.md`, `docs/review/industry_grade_audit_2026-04-07.md`,
  `docs/review/db_findings.md`, `docs/review/perf.md`, `docs/review/ux_findings.md`,
  `docs/review/repo_ai_audit_prompt.md`
- `SPECIFICATIONS.md` — the three language lines
- `AGENTS.md` — one line acknowledging the language decision
- `requirements-dev.txt` + `.github/workflows/ci.yml` OR `scripts/security_check.ps1`
  (the bandit wire-or-drop decision, Step 5)

**Out of scope**:
- `docs/ux_revamp/*` — proposal-stage design docs, leave them
- Any code behavior change (this is a docs/decision plan; bandit wiring is the
  only CI-touching exception)
- Plan 003's config relocation / PIN rotation (related but separate)

## Git workflow

- Branch: `advisor/013-docs-reconciliation`
- Commit messages: `docs: mark implemented backlog items as completed`, `docs: resolve language contract (Spanish)`, `sec: wire bandit into CI` (or `chore: drop unused bandit dependency`)
- Do NOT push unless instructed.

## Steps

### Step 1: Mark implemented items completed

- `docs/audit/industry_grade_backlog.md` [IG-1.1]: add `- Estado: completado
  (evidencia: ui/login_dialog.py, main.py:181-187, commit 9ff8aee)`; remove it
  from the resumption list at `:219`.
- `docs/audit/structural_quality_backlog.md` SQ-B.3 and SQ-B.4: add
  `Status: completed` + evidence paths (`services/update_sale_workflow.py`,
  `services/mutation_coordinator.py`, AGENTS.md "Architecture Contracts");
  update "Suggested execution order" (`:573-581`) to skip Phase SQ-B.
- `docs/review/industry_grade_audit_2026-04-07.md:35,97` — mark resolved.
- `docs/review/security_findings.md:13` — rewrite the auth paragraph to state
  PIN auth exists (single-user desktop threat model) and reference the
  hardening in plan 003 once it lands.

**Verify**: `grep -n "Estado: completado" docs/audit/industry_grade_backlog.md` → match; `grep -n "SQ-B.3\|SQ-B.4" docs/audit/structural_quality_backlog.md | head` → the completion markers present.

### Step 2: Status index for the small review reports

Add a one-line status banner to each of `db_findings.md`, `perf.md`,
`ux_findings.md` (resolved, with evidence file:line) and record the single open
item — the returns/refunds workflow — in `docs/audit/backlog.md` (or the
structural backlog) with a status field. `repo_ai_audit_prompt.md:21,23,84` —
replace the two stale "baseline signals" (reportlab missing; pytest.ini
duplication) with current facts.

**Verify**: `grep -rn "Devoluciones\|returns" docs/audit/` → the open item is
tracked with a status.

### Step 3: Resolve the language contract

Edit `SPECIFICATIONS.md` `:83,126,133` to state: the UI is Spanish; new and
modified UI strings must be in Spanish; remove the "English migration" promise.
Add one line to `AGENTS.md` (Repo Notes): "SPECIFICATIONS.md language section
was reversed by decision on 2026-08-15; Spanish is the UI language."

**Verify**: `grep -n "English-first" SPECIFICATIONS.md` → no matches;
`grep -n "Spanish" SPECIFICATIONS.md` → matches the new statement.

### Step 4: Document the analytics read-only exemption (from the rejected ARCH-08)

Add 2-3 lines to `docs/analytics.md` or AGENTS.md: analytics reads via a
second `mode=ro` connection outside `DatabaseManager`'s lock model — by design,
read-only by contract; new metrics must be SELECT-only (guarded by the plan 009
read-only test).

**Verify**: the sentence exists in the doc.

### Step 5: bandit — wire or drop (decision with data)

Run the probe command. Then apply ONE of:

- **If findings are ≤ 15 and most are medium/low**: wire `bandit -q -r
  database services utils --skip B101` (B101 = assert; asserts are used
  intentionally, e.g. `database/database_manager.py`) as a CI step and document
  it in AGENTS.md. Record the initial finding count in the report; add
  `# nosec` comments ONLY where a finding is a false positive and justified.
- **Otherwise** (noisy, high false-positive rate): remove `bandit` from
  `requirements-dev.txt`, delete `scripts/security_check.ps1`, and correct
  `security_findings.md:35-39`. Say which choice you made and why.

Do not do both (dead toolchain is the current bug).

**Verify** (wire path): `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0 with the recorded count. (drop path): `grep -n bandit requirements-dev.txt` → no match; `git status` shows `scripts/security_check.ps1` deleted.

## Test plan

- Docs-only plan: no new tests. Full suite must remain green (it should — no
  production code changes; the bandit step may fail CI only if wired with
  findings — keep the recorded count in check).

## Done criteria

- [ ] IG-1.1 marked completed and removed from the resumption list
- [ ] SQ-B.3/SQ-B.4 marked completed; execution order updated
- [ ] `security_findings.md` no longer claims auth is missing or bandit runs in CI
- [ ] `db_findings.md`/`perf.md`/`ux_findings.md` carry resolved banners; the returns workflow is the tracked open item
- [ ] `repo_ai_audit_prompt.md` has no stale reportlab/pytest.ini signals
- [ ] `SPECIFICATIONS.md` has no "English-first" lines; the Spanish decision is recorded in AGENTS.md
- [ ] Analytics read-only exemption documented
- [ ] bandit is EITHER wired in CI with a recorded baseline OR removed with the script and doc claims corrected — not both, not neither
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] `plans/README.md` status row updated

## STOP conditions

- The bandit probe produces findings you cannot classify as true/false positive
  within a few minutes (e.g., hundreds) — choose the DROP path and say so; do
  not wire a noisy gate into CI.
- Any doc edit implies a code behavior that does not exist (e.g., the language
  section mentions a setting that is not read — the `language` config key is a
  no-op; note that explicitly rather than claiming i18n exists).
- If plan 003's PIN changes land first, reference them in the auth paragraph
  instead of describing current state as final.

## Maintenance notes

- The "returns/refunds missing" entry is now the single tracked open item from
  the April audits — it is direction candidate 1 in plans/README.md.
- The `language` config key (`config.py:142,180`) is dead config: no reader
  exists. Deleting it is a tiny follow-up; note it, don't do it here.
- Reviewer: this PR should be docs + (optionally) one bandit CI line; any
  production code diff is out of scope.
