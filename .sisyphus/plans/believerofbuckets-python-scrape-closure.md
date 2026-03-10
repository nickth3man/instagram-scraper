# Believerofbuckets Python Scrape Closure

## TL;DR

> **Quick Summary**: Close the Python-only `believerofbuckets` scrape by proving the lone failing shortcode remains unavailable in a bounded freshness check, then clean the output set so the final deliverable is internally consistent and defensibly reported as `99/100 complete with evidence`.
>
> **Deliverables**:
> - Final bounded evidence bundle for `DVsHusCjCTU`
> - Deduped authoritative CSV outputs and reconciled counts
> - Cleaned `data/believerofbuckets/` working set with stale artifacts removed or archived
> - Final closure report documenting `99 success + 1 platform-blocked`
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 5 -> Task 7 -> Final Verification

---

## Context

### Original Request
Complete the scrape for the last 100 posts from `believerofbuckets` using Python only, with no browser usage, no hanging commands, sub-3-minute bounded runs during testing/batching, and enough output to cover post metadata, comments, counts, and media downloads. If full `100/100` completion is impossible, prove the exact root cause with evidence.

### Interview Summary
**Key Discussions**:
- The user rejected Instaloader's default 30-minute retry/sleep behavior after `429` and required bounded, fail-fast execution.
- The final closure goal is not open-ended scraping; it is closure after one bounded freshness check plus cleanup/dedupe.
- The user explicitly chose `closure after freshness-check + cleanup/dedupe` over broader fallback work.

**Research Findings**:
- `scripts/failfast_instaloader_scrape.py` is the best current local execution path because it combines authenticated per-shortcode scraping, fail-fast `429` behavior, comment extraction, and optional media download.
- Built-in `profile`, `browser_dump`, and `video_downloads` workflows each cover only part of the user's ask and are not the chosen closure path.
- The current output set is close but not pristine: `posts.csv` is clean at 99 unique posts, while `comments.csv` contains 286 exact duplicate rows across 8 posts from an accidental concurrent append window.
- `DVsHusCjCTU` already has strong failure evidence: Instaloader lookup failure, GraphQL `xdt_shortcode_media: null`, and mobile media-info unavailable.

### Metis Review
**Identified Gaps** (addressed):
- Authoritative outputs were ambiguous; this plan explicitly treats `posts.csv`, `comments.csv`, `errors.csv`, `downloads/`, and a new closure evidence/report artifact as source-of-truth deliverables.
- Cleanup risk was ambiguous; this plan requires evidence preservation before removing stale artifacts.
- Dedupe semantics were under-specified; this plan requires deterministic duplicate detection plus before/after counts.
- Acceptance criteria were incomplete; this plan adds executable count, integrity, and evidence checks.

---

## Work Objectives

### Core Objective
Produce a final, defensible closure package for the `believerofbuckets` scrape that preserves the successful `99` posts, proves the remaining shortcode is still unavailable under bounded Python-only checks, and leaves the authoritative outputs internally consistent.

### Concrete Deliverables
- Authoritative final outputs under `data/believerofbuckets/`: `posts.csv`, `comments.csv`, `errors.csv`, `downloads/`
- Closure evidence artifact(s) for `DVsHusCjCTU` under `.sisyphus/evidence/`
- Final closure report under `data/believerofbuckets/` or another explicit authoritative location selected by implementation
- Updated/cleaned artifact set with stale browser-dump leftovers removed or archived

### Definition of Done
- [ ] `tool_dump.json` still contains 100 URLs and the final accounting is exactly `99 successful shortcodes + 1 failing shortcode`
- [ ] `posts.csv` contains 99 data rows and 99 unique shortcodes
- [ ] `comments.csv` contains zero exact duplicate rows after cleanup
- [ ] `errors.csv` contains exactly one failing shortcode row for `DVsHusCjCTU`
- [ ] Fresh bounded evidence exists on disk showing `DVsHusCjCTU` still fails through the selected Python-only checks
- [ ] `uv run ruff check .`, `uv run ty check`, and `uv run python -m pytest` all pass

### Must Have
- One final bounded freshness bundle for `DVsHusCjCTU`
- Deterministic comment dedupe with an explicit removed-row count
- Explicit stale-artifact policy: remove or archive, but do not leave ambiguity
- Final machine-readable or markdown closure summary tied to disk artifacts

### Must NOT Have (Guardrails)
- No browser automation, DevTools, or Playwright usage
- No unbounded retries, long sleeps, or commands over the runtime budget during network verification
- No full 100-post re-scrape unless a failing acceptance criterion makes it strictly necessary
- No refactor of unrelated scraper architectures or placeholder providers
- No deletion of evidence for the blocked shortcode before replacement evidence is captured

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — all verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after with targeted additions for closure logic
- **Framework**: `pytest`

### QA Policy
Every task includes agent-executed QA scenarios and evidence capture under `.sisyphus/evidence/`.

- **Filesystem/data validation**: Use `bash` with short Python snippets to count rows, compare keys, and inspect artifacts
- **Python closure checks**: Use `bash` to run bounded Python commands or scripts with explicit timeouts under 180000 ms
- **Repo quality gates**: Use `uv run ruff check .`, `uv run ty check`, and `uv run python -m pytest`

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately — closure foundations):
├── Task 1: Define authoritative artifact contract and stale-artifact policy [quick]
├── Task 2: Implement bounded freshness bundle for `DVsHusCjCTU` [unspecified-high]
├── Task 3: Build duplicate-comment audit and deterministic dedupe utility/tests [deep]
└── Task 4: Build media/post/error integrity audit and reconciliation checks [quick]

Wave 2 (After Wave 1 — cleanup + closure packaging):
├── Task 5: Apply stale-artifact cleanup/archive workflow [quick]
├── Task 6: Apply dedupe/reconciliation to authoritative outputs [deep]
└── Task 7: Generate final closure report and evidence manifest [writing]

Wave 3 (After Wave 2 — full validation):
├── Task 8: Run repo gates and artifact invariants [unspecified-high]
└── Task 9: Re-verify final `99 + 1` closure accounting from disk [quick]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real artifact QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 -> Task 2 -> Task 5 -> Task 7 -> Task 8 -> F1-F4
Parallel Speedup: ~55% faster than sequential
Max Concurrent: 4

### Dependency Matrix

- **1**: None -> 5, 7, 9
- **2**: None -> 7, 9
- **3**: None -> 6, 7, 9
- **4**: None -> 6, 7, 9
- **5**: 1 -> 8, 9
- **6**: 3, 4 -> 8, 9
- **7**: 1, 2, 3, 4 -> 8, 9
- **8**: 5, 6, 7 -> F1-F4
- **9**: 1, 2, 3, 4, 5, 6, 7 -> F1-F4

### Agent Dispatch Summary

- **1**: **4** — T1 -> `quick`, T2 -> `unspecified-high`, T3 -> `deep`, T4 -> `quick`
- **2**: **3** — T5 -> `quick`, T6 -> `deep`, T7 -> `writing`
- **3**: **2** — T8 -> `unspecified-high`, T9 -> `quick`
- **FINAL**: **4** — F1 -> `oracle`, F2 -> `unspecified-high`, F3 -> `unspecified-high`, F4 -> `deep`

---

## TODOs

- [ ] 1. Define the authoritative closure artifact set and stale-artifact policy

  **What to do**:
  - Identify the exact files/directories that count as final source-of-truth for this scrape: `tool_dump.json`, `posts.csv`, `comments.csv`, `errors.csv`, `downloads/`, and the new closure evidence/report artifacts.
  - Classify mixed leftovers in `data/believerofbuckets/` as either `archive`, `remove`, or `retain`.
  - Add targeted automated tests for artifact classification and final-accounting invariants before implementing helper code.

  **Must NOT do**:
  - Do not treat `summary.json`, `checkpoint.json`, `errors.ndjson`, or `extraction_errors.json` as authoritative completion sources.
  - Do not delete credential-bearing or evidence-bearing files until replacement evidence policy exists.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: focused closure scaffolding and test additions with limited file scope.
  - **Skills**: `typescript-best-practices`, `test-fixing`
    - `typescript-best-practices`: use the general discipline around exact contracts and deterministic output handling, even though the implementation is Python.
    - `test-fixing`: useful for tightening acceptance tests and avoiding brittle assertions.
  - **Skills Evaluated but Omitted**:
    - `code-refactoring`: no structural refactor should happen at this stage.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: 5, 7, 9
  - **Blocked By**: None

  **References**:
  - `scripts/failfast_instaloader_scrape.py` - current authoritative script shape and output filenames.
  - `data/believerofbuckets/tool_dump.json` - bounded 100-URL source set to preserve in final accounting.
  - `data/believerofbuckets/posts.csv` - canonical successful post export to validate.
  - `data/believerofbuckets/comments.csv` - canonical comment export that needs cleanup.
  - `data/believerofbuckets/errors.csv` - canonical failing-shortcode record.
  - `data/believerofbuckets/summary.json` - stale browser-dump artifact that must not be trusted.
  - `data/believerofbuckets/checkpoint.json` - stale browser-dump checkpoint to classify.
  - `tests/test_reporting.py` - examples of tolerant file-loading assertions for disk-backed outputs.

  **Acceptance Criteria**:
  - [ ] Targeted tests exist covering authoritative-artifact classification and `99 success + 1 failure` accounting.
  - [ ] Running the targeted tests passes.
  - [ ] A clear archive/remove/retain policy is encoded in code or test fixtures and can be executed without manual judgment.

  **QA Scenarios**:
  ```text
  Scenario: Artifact classification happy path
    Tool: Bash (python)
    Preconditions: Repository contains the current `data/believerofbuckets/` tree.
    Steps:
      1. Run the targeted classification test command for the new closure tests.
      2. Assert the test output marks `posts.csv`, `comments.csv`, `errors.csv`, `tool_dump.json`, and `downloads/` as retained.
      3. Assert stale browser-dump artifacts are classified explicitly, not left unhandled.
    Expected Result: Tests pass and output demonstrates all known artifacts are classified.
    Failure Indicators: Missing artifact classification, failing assertions, or unclassified leftovers.
    Evidence: .sisyphus/evidence/task-1-artifact-classification.txt

  Scenario: Authoritative accounting failure path
    Tool: Bash (python)
    Preconditions: A fixture or temporary copy with one authoritative file removed or misclassified.
    Steps:
      1. Run the targeted failing test/fixture for missing authoritative artifacts.
      2. Assert the command fails with an explicit message naming the missing or misclassified file.
    Expected Result: Failure is immediate and names the artifact contract violation.
    Failure Indicators: Silent success, vague errors, or a traceback without artifact context.
    Evidence: .sisyphus/evidence/task-1-artifact-classification-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Classification test output
  - [ ] Failing-path test output proving contract enforcement

  **Commit**: YES
  - Message: `test(closure): define authoritative scrape artifacts`
  - Files: `tests/...`, minimal helper module(s)
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 2. Implement the final bounded freshness bundle for `DVsHusCjCTU`

  **What to do**:
  - Add or extract a reusable bounded verification entrypoint that re-checks `DVsHusCjCTU` using the approved Python-only paths.
  - Capture a fresh evidence bundle for the shortcode, including at minimum the fail-fast Instaloader check and the already-approved Python-only fallback(s) chosen for closure.
  - Ensure each verification command has an explicit timeout under 180000 ms and fails fast on `429` or hangs.

  **Must NOT do**:
  - Do not broaden this into a new scraper architecture or re-run all 100 posts.
  - Do not use browser, Playwright, or DevTools.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: bounded network verification with evidence packaging and strict operational constraints.
  - **Skills**: `test-fixing`, `typescript-best-practices`
    - `test-fixing`: useful for structuring deterministic verification around failure behavior.
    - `typescript-best-practices`: use its general rigor around explicit contracts and error reporting.
  - **Skills Evaluated but Omitted**:
    - `playwright`: forbidden by scope.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: 7, 9
  - **Blocked By**: None

  **References**:
  - `scripts/failfast_instaloader_scrape.py` - fail-fast session setup and timeout posture to preserve.
  - `data/believerofbuckets/errors.csv` - existing error baseline for `DVsHusCjCTU`.
  - `.sisyphus/drafts/believerofbuckets-python-scrape.md` - current evidence narrative and closure decision.
  - `README.md` - project environment and `.env` cookie loading assumptions.

  **Acceptance Criteria**:
  - [ ] Fresh evidence files exist for the selected `DVsHusCjCTU` verification paths.
  - [ ] Every freshness-check command is bounded with an explicit runtime cap below 180000 ms.
  - [ ] If the shortcode still fails, the evidence bundle clearly records failure mode and timestamp.
  - [ ] If the shortcode unexpectedly succeeds, the workflow fails closed and hands off to a repair path instead of silently reporting `99/100`.

  **QA Scenarios**:
  ```text
  Scenario: Bounded freshness check reproduces blocked shortcode
    Tool: Bash (python)
    Preconditions: Valid `.env` session cookies are available and the workspace is unchanged.
    Steps:
      1. Run the new bounded freshness command for shortcode `DVsHusCjCTU` with timeout < 180000 ms.
      2. Assert an evidence file is written under `.sisyphus/evidence/` containing the shortcode and recorded failure mode.
      3. Assert the command exits without hanging or entering a long sleep.
    Expected Result: The check completes within the budget and writes a machine-readable or text evidence artifact.
    Failure Indicators: Timeout, hidden retry sleep, missing evidence file, or a command that silently swallows the failure.
    Evidence: .sisyphus/evidence/task-2-dvshuscjctu-freshness.txt

  Scenario: Unexpected success path is surfaced
    Tool: Bash (python)
    Preconditions: Use a test double or fixture that simulates a previously blocked shortcode now resolving.
    Steps:
      1. Run the targeted test for the unexpected-success branch.
      2. Assert the command or test reports that closure assumptions are invalidated and additional recovery is required.
    Expected Result: The workflow does not silently continue with `99/100` if the 100th post becomes available.
    Failure Indicators: Silent pass, overwritten evidence, or continued closure reporting despite success.
    Evidence: .sisyphus/evidence/task-2-dvshuscjctu-success-branch.txt
  ```

  **Evidence to Capture**:
  - [ ] Freshness-check stdout/stderr or structured output
  - [ ] Timestamped evidence artifact for the failing shortcode

  **Commit**: YES
  - Message: `feat(closure): add bounded blocked-shortcode verification`
  - Files: minimal closure verification code/tests/evidence helpers
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 3. Build duplicate-comment audit and deterministic dedupe rules

  **What to do**:
  - Add tests that codify the duplicate problem observed in `comments.csv`, including exact-row duplicates and before/after counts.
  - Implement a deterministic dedupe utility or workflow using a clearly defined key, and emit a summary of removed duplicate rows and affected shortcodes.
  - Preserve the original comment semantics while removing append-duplication artifacts only.

  **Must NOT do**:
  - Do not dedupe by a weak key that can collapse legitimate distinct comment rows.
  - Do not mutate `posts.csv` or media files here.

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: data-integrity repair with deterministic semantics and regression tests.
  - **Skills**: `test-fixing`, `code-refactoring`
    - `test-fixing`: needed to lock the observed duplicate behavior into repeatable tests.
    - `code-refactoring`: useful only for extracting small reusable helpers without broad redesign.
  - **Skills Evaluated but Omitted**:
    - `project-bootstrapper`: unnecessary for a bounded repair utility.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: 6, 7, 9
  - **Blocked By**: None

  **References**:
  - `data/believerofbuckets/comments.csv` - real duplicate problem to codify and repair.
  - `tests/test_video_download_comments_validation_media.py` - existing patterns for comment CSV loading and grouped validation.
  - `scripts/failfast_instaloader_scrape.py` - current comment row schema and append behavior.

  **Acceptance Criteria**:
  - [ ] Tests exist proving exact duplicate rows are detected and removed deterministically.
  - [ ] Running the dedupe process results in zero exact duplicate comment rows.
  - [ ] A summary artifact or structured output reports removed-row count and affected shortcodes.

  **QA Scenarios**:
  ```text
  Scenario: Dedupe removes only exact duplicate comment rows
    Tool: Bash (python)
    Preconditions: A fixture or copy of `comments.csv` contains the known duplicate rows.
    Steps:
      1. Run the targeted dedupe test or command on the fixture.
      2. Assert the output reports duplicate removal for the affected shortcodes.
      3. Assert a second duplicate scan returns zero exact duplicate rows.
    Expected Result: Duplicate rows are removed and the scan is clean afterward.
    Failure Indicators: Remaining duplicate keys, mismatched removed-row counts, or changed non-duplicate rows.
    Evidence: .sisyphus/evidence/task-3-comment-dedupe.txt

  Scenario: Non-duplicate rows remain intact
    Tool: Bash (python)
    Preconditions: A fixture containing both duplicate and unique comment rows.
    Steps:
      1. Run the targeted integrity test after dedupe.
      2. Assert unique rows retain their original field values.
      3. Assert the test fails if a non-duplicate row is removed or modified.
    Expected Result: Only exact duplicates are removed.
    Failure Indicators: Changed text, missing unique rows, or changed owner/comment IDs.
    Evidence: .sisyphus/evidence/task-3-comment-dedupe-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Dedupe summary output
  - [ ] Post-dedupe duplicate scan output

  **Commit**: YES
  - Message: `fix(closure): dedupe exact duplicate comments`
  - Files: closure utility/tests and updated comment output copy if part of the workflow
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 4. Build media/post/error integrity audit and reconciliation checks

  **What to do**:
  - Add or extract a verification command that recomputes final invariants from disk: URL count, post uniqueness, error count, download base count, and comment duplicate count.
  - Ensure the audit can prove `99 success + 1 failure` independently of stale summary/checkpoint files.
  - Add tests for malformed or partial CSV edge cases so the audit fails clearly.

  **Must NOT do**:
  - Do not trust stale checkpoint or summary artifacts.
  - Do not conflate media sidecar files with successful-post accounting unless explicitly defined.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: focused invariant checks and testable reporting logic.
  - **Skills**: `test-fixing`, `code-refactoring`
    - `test-fixing`: useful for executable invariants and failure modes.
    - `code-refactoring`: helpful for extracting a small audit helper from ad hoc scripts.
  - **Skills Evaluated but Omitted**:
    - `feature-planning`: this is implementation detail, not further planning.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: 6, 7, 9
  - **Blocked By**: None

  **References**:
  - `data/believerofbuckets/tool_dump.json` - source count baseline of 100 URLs.
  - `data/believerofbuckets/posts.csv` - final successful-post baseline.
  - `data/believerofbuckets/errors.csv` - expected single error baseline.
  - `data/believerofbuckets/downloads/` - on-disk media artifact set to audit.
  - `tests/test_reporting.py` - examples of loading on-disk datasets and asserting computed metrics.

  **Acceptance Criteria**:
  - [ ] Disk audit command or tests pass on the cleaned authoritative outputs.
  - [ ] The audit reports `100 input URLs`, `99 successful posts`, `1 failing shortcode`, and `0 duplicate post rows`.
  - [ ] Failure cases for malformed/partial CSV data are covered by tests.

  **QA Scenarios**:
  ```text
  Scenario: Final artifact audit happy path
    Tool: Bash (python)
    Preconditions: Authoritative outputs are present in `data/believerofbuckets/`.
    Steps:
      1. Run the audit command or targeted test suite.
      2. Assert the output reports 100 URLs, 99 successful posts, and 1 failing shortcode.
      3. Assert the audit reports zero duplicate post rows and the current duplicate-comment state accurately.
    Expected Result: Audit passes with exact numeric invariants.
    Failure Indicators: Mismatched counts, reliance on stale files, or missing artifact coverage.
    Evidence: .sisyphus/evidence/task-4-artifact-audit.txt

  Scenario: Partial CSV failure path
    Tool: Bash (python)
    Preconditions: A fixture with a truncated or malformed CSV row.
    Steps:
      1. Run the targeted audit test against the malformed fixture.
      2. Assert the failure names the problematic file and row-level issue.
    Expected Result: The audit fails clearly and refuses to certify incomplete data.
    Failure Indicators: Silent success, generic traceback, or no file-specific context.
    Evidence: .sisyphus/evidence/task-4-artifact-audit-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Audit output for the happy path
  - [ ] Failing-path audit output for malformed input fixture

  **Commit**: YES
  - Message: `test(closure): add final artifact invariants`
  - Files: closure audit tests/helpers
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 5. Apply stale-artifact cleanup or archive workflow

  **What to do**:
  - Execute the policy from Task 1 against stale browser-dump and exploratory artifacts.
  - Preserve the blocked-shortcode evidence bundle before removing any stale files that still contain historical clues.
  - Leave the final directory state unambiguous: authoritative outputs stay, stale leftovers are either gone or explicitly archived.

  **Must NOT do**:
  - Do not remove `.env` or secrets-management files.
  - Do not delete blocked-shortcode evidence without replacement evidence already saved.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: file classification and controlled cleanup.
  - **Skills**: `test-fixing`
    - `test-fixing`: keep cleanup behavior validated and deterministic.
  - **Skills Evaluated but Omitted**:
    - `git-master`: cleanup is local data hygiene, not history surgery.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Tasks 6, 7 logically adjacent but this task should complete first if it touches shared files)
  - **Blocks**: 8, 9
  - **Blocked By**: 1

  **References**:
  - `data/believerofbuckets/summary.json` - stale browser-dump summary to remove or archive.
  - `data/believerofbuckets/checkpoint.json` - stale browser-dump checkpoint.
  - `data/believerofbuckets/errors.ndjson` - stale browser-dump errors.
  - `data/believerofbuckets/extraction_errors.json` - stale exploratory extraction artifact.
  - `data/believerofbuckets/SCRAPING_STATUS.md` - stale browser-era narrative that conflicts with the final Python-only closure state.
  - `data/believerofbuckets/instagram_cookies.txt` - sensitive exploratory artifact to handle carefully.

  **Acceptance Criteria**:
  - [ ] Every stale artifact from the declared policy is either removed or archived exactly as specified.
  - [ ] Authoritative outputs remain intact after cleanup.
  - [ ] Evidence for `DVsHusCjCTU` still exists after cleanup.

  **QA Scenarios**:
  ```text
  Scenario: Cleanup preserves authoritative outputs
    Tool: Bash (python)
    Preconditions: Cleanup/archive workflow has been executed.
    Steps:
      1. Run the artifact classification or audit command after cleanup.
      2. Assert authoritative files still exist.
      3. Assert each stale artifact is either absent or present only in the declared archive location.
    Expected Result: Directory state matches the policy exactly.
    Failure Indicators: Missing authoritative files, leftover stale files in place, or missing evidence bundle.
    Evidence: .sisyphus/evidence/task-5-cleanup.txt

  Scenario: Evidence preservation failure path
    Tool: Bash (python)
    Preconditions: Use a test fixture or dry-run mode where evidence is missing before cleanup.
    Steps:
      1. Run the targeted test for cleanup without preserved evidence.
      2. Assert the workflow fails before deleting stale artifacts.
    Expected Result: Cleanup is blocked until replacement evidence exists.
    Failure Indicators: Cleanup proceeds anyway or failure message lacks the evidence-path requirement.
    Evidence: .sisyphus/evidence/task-5-cleanup-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Post-cleanup artifact inventory output
  - [ ] Cleanup failure-path output

  **Commit**: YES
  - Message: `chore(closure): clean stale scrape artifacts`
  - Files: cleaned/archived artifacts plus any helper code/tests
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 6. Apply dedupe and reconciliation to the authoritative outputs

  **What to do**:
  - Run the approved dedupe workflow against the authoritative comment data.
  - Reconcile per-post comment totals and record any remaining divergence explicitly in the closure report instead of leaving silent inconsistencies.
  - Re-run the disk audit after mutation so the final CSVs are certifiable.

  **Must NOT do**:
  - Do not silently rewrite counts without recording before/after deltas.
  - Do not touch downloads unless a failing audit proves a specific repair is necessary.

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: this is the core data-repair step and must preserve semantics.
  - **Skills**: `test-fixing`, `code-refactoring`
    - `test-fixing`: validates before/after behavior rigorously.
    - `code-refactoring`: only to keep repair helpers small and reusable.
  - **Skills Evaluated but Omitted**:
    - `code-auditor`: overkill for a targeted dedupe/reconciliation pass.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: 8, 9
  - **Blocked By**: 3, 4

  **References**:
  - `data/believerofbuckets/comments.csv` - input and output target for dedupe.
  - `data/believerofbuckets/posts.csv` - comment-count comparison baseline.
  - `tests/test_video_download_comments_validation_media.py` - comment grouping patterns and expected CSV field discipline.

  **Acceptance Criteria**:
  - [ ] Running the duplicate scan after reconciliation reports zero exact duplicate rows.
  - [ ] Before/after row counts and affected shortcodes are recorded.
  - [ ] Any remaining post-level comment-count mismatches are explicitly surfaced in the final closure report.

  **QA Scenarios**:
  ```text
  Scenario: Reconciliation produces clean comment output
    Tool: Bash (python)
    Preconditions: Dedupe utility and audit utility are implemented.
    Steps:
      1. Run the dedupe/reconciliation command on the authoritative outputs.
      2. Run the duplicate scan again.
      3. Assert the scan reports zero exact duplicate comment rows.
    Expected Result: `comments.csv` is deduped and the summary records the removed-row count.
    Failure Indicators: Residual duplicates, missing summary, or mutated non-duplicate rows.
    Evidence: .sisyphus/evidence/task-6-reconciliation.txt

  Scenario: Remaining mismatches are surfaced, not hidden
    Tool: Bash (python)
    Preconditions: Fixture or real data contains a known post-level mismatch after dedupe.
    Steps:
      1. Run the targeted reconciliation test or report generation.
      2. Assert the mismatch is recorded explicitly.
    Expected Result: Any unresolved count divergence is documented rather than silently ignored.
    Failure Indicators: Report claims perfect consistency when mismatches still exist.
    Evidence: .sisyphus/evidence/task-6-reconciliation-mismatch.txt
  ```

  **Evidence to Capture**:
  - [ ] Post-dedupe row counts and affected-shortcode summary
  - [ ] Mismatch-report output if any mismatches remain

  **Commit**: YES
  - Message: `fix(closure): reconcile final comment exports`
  - Files: authoritative CSVs, repair utility/tests, summary artifacts
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 7. Generate the final closure report and evidence manifest

  **What to do**:
  - Produce the final machine-readable or markdown closure summary that states the final accounting, the blocked-shortcode evidence outcome, and any residual caveats such as remaining comment-count mismatches.
  - Include explicit references to the authoritative outputs and the evidence files created in earlier tasks.
  - Ensure the report language says `Instagram-side unavailable/restricted for this account/context` rather than overclaiming deletion or permanent removal.

  **Must NOT do**:
  - Do not describe the scrape as `100/100 complete` unless Task 2 unexpectedly succeeds and the plan branches accordingly.
  - Do not cite stale browser-era artifacts as final evidence.

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: precise closure narrative, evidence manifesting, and defensible stakeholder-facing language.
  - **Skills**: `code-documentation`
    - `code-documentation`: useful for writing a compact but precise final report grounded in files and evidence.
  - **Skills Evaluated but Omitted**:
    - `technical-doc-creator`: overkill for a small closure report.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (after foundational tasks are done)
  - **Blocks**: 8, 9
  - **Blocked By**: 1, 2, 3, 4

  **References**:
  - `.sisyphus/evidence/` - final evidence inputs for the report.
  - `data/believerofbuckets/posts.csv` - final successful-post reference.
  - `data/believerofbuckets/comments.csv` - final comment export reference.
  - `data/believerofbuckets/errors.csv` - blocked-shortcode reference.
  - `.sisyphus/drafts/believerofbuckets-python-scrape.md` - prior reasoning and closure wording baseline.

  **Acceptance Criteria**:
  - [ ] Final report exists on disk and names the authoritative outputs.
  - [ ] Final report states `99 successful posts + 1 platform-blocked shortcode` unless Task 2 changes the outcome.
  - [ ] Final report links or points to the freshness evidence bundle and any dedupe/reconciliation summary.

  **QA Scenarios**:
  ```text
  Scenario: Final closure report matches disk state
    Tool: Bash (python)
    Preconditions: Tasks 1-6 have completed and generated final artifacts.
    Steps:
      1. Read the closure report and parse or inspect its declared counts.
      2. Run the disk audit command.
      3. Assert the report's counts and failure narrative match the audit output and evidence files.
    Expected Result: The report is consistent with the actual disk state.
    Failure Indicators: Count mismatch, stale evidence references, or unsupported root-cause language.
    Evidence: .sisyphus/evidence/task-7-closure-report.txt

  Scenario: Overclaim prevention path
    Tool: Bash (python)
    Preconditions: Use a fixture or test case where the report template claims `100/100` despite one error row.
    Steps:
      1. Run the targeted test validating closure-report wording.
      2. Assert the test fails on overclaiming completeness.
    Expected Result: Unsupported claims are blocked by test coverage.
    Failure Indicators: Report passes validation while overstating completion.
    Evidence: .sisyphus/evidence/task-7-closure-report-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Final report validation output
  - [ ] Overclaim-prevention test output

  **Commit**: YES
  - Message: `docs(closure): record believerofbuckets final scrape status`
  - Files: final closure report and any evidence manifest helpers/tests
  - Pre-commit: `uv run python -m pytest <targeted tests>`

- [ ] 8. Run repo quality gates and closure-specific verification

  **What to do**:
  - Run the full repository gates required by project policy: Ruff, Ty, and full pytest.
  - Run the closure-specific targeted audit commands after the repo-wide checks.
  - Address any failures before sign-off.

  **Must NOT do**:
  - Do not claim closure while any of the repo gates fail.
  - Do not skip full-test execution because only scripts/data changed.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: broad verification across repo and closure-specific state.
  - **Skills**: `test-fixing`
    - `test-fixing`: appropriate if any tests fail and require grouped repair.
  - **Skills Evaluated but Omitted**:
    - `verification-before-completion`: the plan itself already encodes explicit verification commands.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Final Verification Wave
  - **Blocked By**: 5, 6, 7

  **References**:
  - `AGENTS.md` - completion gate requiring Ruff, Ty, and full pytest before claiming success.
  - `.sisyphus/plans/believerofbuckets-python-scrape-closure.md` - this plan's final invariants.

  **Acceptance Criteria**:
  - [ ] `uv run ruff check .` passes.
  - [ ] `uv run ty check` passes.
  - [ ] `uv run python -m pytest` passes.
  - [ ] Closure-specific audit commands still pass after the full suite.

  **QA Scenarios**:
  ```text
  Scenario: Full repo gate happy path
    Tool: Bash
    Preconditions: All closure changes and artifact mutations are complete.
    Steps:
      1. Run `uv run ruff check .`.
      2. Run `uv run ty check`.
      3. Run `uv run python -m pytest`.
    Expected Result: All three commands exit successfully.
    Failure Indicators: Any non-zero exit code, warnings escalated to errors, or test failures.
    Evidence: .sisyphus/evidence/task-8-repo-gates.txt

  Scenario: Closure-specific audit after repo gates
    Tool: Bash (python)
    Preconditions: Repo-wide gates have passed.
    Steps:
      1. Run the final closure artifact audit command.
      2. Assert the `99 + 1` accounting still holds after all code/test execution.
    Expected Result: Final invariants remain intact.
    Failure Indicators: Audit drift after tests or stale artifacts reappearing.
    Evidence: .sisyphus/evidence/task-8-closure-audit.txt
  ```

  **Evidence to Capture**:
  - [ ] Ruff/Ty/pytest command output
  - [ ] Final closure audit output

  **Commit**: NO
  - Message: n/a
  - Files: none unless a failure requires a follow-up fix commit
  - Pre-commit: n/a

- [ ] 9. Re-verify final `99 + 1` closure accounting from disk

  **What to do**:
  - Run one final disk-only summary pass after cleanup, dedupe, report generation, and repo gates.
  - Confirm the final working set is coherent and resumability metadata is not being mistaken for completion metadata.
  - Record the final exact numbers used in stakeholder reporting.

  **Must NOT do**:
  - Do not use stale browser-dump metrics.
  - Do not infer completion from `checkpoint_instaloader.json`.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: final count reconciliation and disk summary.
  - **Skills**: `test-fixing`
    - `test-fixing`: useful if the final invariant summary diverges unexpectedly.
  - **Skills Evaluated but Omitted**:
    - `writing`: this task is verification, not documentation.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Final Verification Wave
  - **Blocked By**: 1, 2, 3, 4, 5, 6, 7

  **References**:
  - `data/believerofbuckets/tool_dump.json` - input count baseline.
  - `data/believerofbuckets/posts.csv` - successful-post baseline.
  - `data/believerofbuckets/comments.csv` - final comment baseline after cleanup.
  - `data/believerofbuckets/errors.csv` - final blocked-shortcode baseline.
  - `data/believerofbuckets/downloads/` - final download tree.

  **Acceptance Criteria**:
  - [ ] Final disk summary reports 100 URLs, 99 successful post rows, 1 error row, and zero duplicate post rows.
  - [ ] Final disk summary explicitly records whether any post-level comment-count mismatches remain.
  - [ ] Final disk summary is consistent with the closure report.

  **QA Scenarios**:
  ```text
  Scenario: Final disk summary happy path
    Tool: Bash (python)
    Preconditions: Tasks 1-8 have completed successfully.
    Steps:
      1. Run the final disk-summary command.
      2. Assert it reports 100 source URLs, 99 successful posts, and 1 blocked shortcode.
      3. Assert it records the final duplicate-comment state as zero exact duplicates.
    Expected Result: Disk-only counts match the closure report and artifact audit.
    Failure Indicators: Count mismatches, residual duplicates, or disagreement with the report.
    Evidence: .sisyphus/evidence/task-9-final-summary.txt

  Scenario: Non-authoritative metadata ignored
    Tool: Bash (python)
    Preconditions: `checkpoint_instaloader.json` and stale artifacts are still present or represented in a fixture.
    Steps:
      1. Run the targeted test or summary command.
      2. Assert the result does not use stale checkpoint/summary values for completion.
    Expected Result: Final accounting is derived only from authoritative outputs.
    Failure Indicators: Final counts mirror stale checkpoint or summary files.
    Evidence: .sisyphus/evidence/task-9-final-summary-error.txt
  ```

  **Evidence to Capture**:
  - [ ] Final disk-summary output
  - [ ] Non-authoritative-metadata guard output

  **Commit**: NO
  - Message: n/a
  - Files: none unless a final fix is required
  - Pre-commit: n/a

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. Verify the final deliverables exist on disk, verify stale-artifact policy was applied as specified, and reject if any required closure evidence or dedupe summary is missing.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check .`, `uv run ty check`, and `uv run python -m pytest`. Review changed helper code/tests for brittle assumptions, hard-coded usernames, broad deletions, or hidden retry/sleep behavior.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Artifact QA** — `unspecified-high`
  Execute every QA scenario from Tasks 1-9, validate evidence files under `.sisyphus/evidence/`, and confirm the final directory state contains only authoritative outputs plus any declared archive.
  Output: `Scenarios [N/N pass] | Artifacts [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Compare the final changes against this plan. Reject any browser-use paths, scraper redesign work, unrelated refactors, or claims beyond `99/100 complete with evidence` unless Task 2 changed the outcome.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `test(closure): define authoritative scrape artifacts` — tests/helper contract only
- **2**: `feat(closure): add bounded blocked-shortcode verification` — bounded freshness tooling
- **3**: `fix(closure): dedupe exact duplicate comments` — dedupe helper/tests
- **4**: `chore(closure): clean stale scrape artifacts` — archive/remove leftovers plus evidence preservation
- **5**: `fix(closure): reconcile final comment exports` — final authoritative CSV updates
- **6**: `docs(closure): record believerofbuckets final scrape status` — final closure report/evidence manifest

---

## Success Criteria

### Verification Commands
```bash
uv run ruff check .
uv run ty check
uv run python -m pytest
python -c "from pathlib import Path; import csv, json; base=Path('data/believerofbuckets'); urls=json.loads((base/'tool_dump.json').read_text(encoding='utf-8'))['urls']; posts=list(csv.DictReader((base/'posts.csv').open(encoding='utf-8', newline=''))); comments=list(csv.DictReader((base/'comments.csv').open(encoding='utf-8', newline=''))); errors=list(csv.DictReader((base/'errors.csv').open(encoding='utf-8', newline=''))); print({'urls':len(urls),'posts':len(posts),'errors':len(errors),'comments':len(comments)})"
```

### Final Checklist
- [ ] All authoritative outputs exist and are clearly identified
- [ ] Final accounting is exactly `99 successful shortcodes + 1 failing shortcode`
- [ ] `DVsHusCjCTU` freshness evidence exists and is bounded
- [ ] `comments.csv` has zero exact duplicate rows after reconciliation
- [ ] Stale browser-dump/exploratory artifacts are removed or archived per policy
- [ ] Final closure report matches the disk state
- [ ] Ruff, Ty, and the full test suite pass
