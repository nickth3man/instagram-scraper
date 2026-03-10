# Audit Remediation Plan

This document turns the March 10, 2026 code audit into an execution-ready plan.

## Goals

- Eliminate duplicated scrape-mode wiring across CLI, pipeline, capabilities, and GUI.
- Improve downloader scalability for larger scrape outputs.
- Replace suppression-based production code escapes with structural fixes.
- Improve auth hygiene and local configuration ergonomics.
- Add lightweight schema governance and larger-scale test coverage.
- Keep Ruff, Ty, and the full test suite green after each phase.

## Success criteria

A phase is complete only when all of the following are true:

- `uv run ruff check .` passes
- `uv run ty check` passes
- `c:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.venv/Scripts/python.exe -m pytest` passes
- Relevant docs and tests are updated
- No new inline production suppressions are introduced

## Workstreams

### 1. Auth hygiene and local configuration

**Outcome:** safer auth entrypoints and a smoother local setup.

#### Auth and env tasks

1. Load project-local environment variables from `.env` before CLI and HTTP client setup.
   - Target files:
     - `src/instagram_scraper/cli.py`
     - `src/instagram_scraper/infrastructure/instagram_http.py`
     - `src/instagram_scraper/infrastructure/async_http.py`
     - `src/instagram_scraper/workflows/video_downloads.py`
   - Add a small helper module, e.g. `src/instagram_scraper/infrastructure/env.py`.

2. Prefer environment-based cookie configuration.
   - Make `--cookie-header` read from `IG_COOKIE_HEADER` by default.
   - Update help text to explicitly recommend env or `.env` usage.

3. Update docs to recommend env-based auth before CLI-arg auth.
   - Target files:
     - `README.md`
     - optionally command help text in `src/instagram_scraper/cli.py`

4. Ensure `.env` is ignored by git.
   - Target file:
     - `.gitignore`

#### Auth and env test updates

- CLI tests for env-backed cookie defaults in `tests/test_cli.py`
- HTTP/env loading tests if a dedicated env helper is introduced

**Effort:** small

### 2. Central scrape-mode registry

**Outcome:** one source of truth for scrape mode metadata and behavior.

#### Registry tasks

1. Introduce a central registry module.
   - Proposed file:
     - `src/instagram_scraper/core/mode_registry.py`
   - Registry fields should include:
     - mode name
     - support tier
     - auth requirement
     - target resolver
     - runner
     - GUI argument builder metadata or callback

2. Refactor capabilities to derive support and auth metadata from the registry.
   - Target file:
     - `src/instagram_scraper/core/capabilities.py`

3. Refactor pipeline target resolution and mode dispatch to use the registry.
   - Target file:
     - `src/instagram_scraper/core/pipeline.py`

4. Refactor GUI scrape-kwargs building to use the same registry.
   - Target file:
     - `src/instagram_scraper/ui/gui.py`

5. Reduce duplicated mode lists in layout and GUI helpers.
   - Target files:
     - `src/instagram_scraper/ui/layout.py`
     - `src/instagram_scraper/ui/gui.py`

6. Evaluate sync-mode treatment.
   - Keep sync modes either:
     - in the same registry with explicit sync runners, or
     - in a small dedicated sync registry with the same shape
   - Avoid leaving sync half-inside and half-outside the abstraction.

#### Registry test updates

- `tests/test_capabilities.py`
- `tests/test_pipeline.py`
- `tests/test_gui.py`
- `tests/test_cli.py`

**Effort:** medium

### 3. Video downloader scalability and structure

**Outcome:** smaller, safer downloader logic that handles larger datasets.

#### Downloader tasks

1. Split `video_downloads.py` into smaller responsibilities.
   - Keep the CLI and top-level orchestration in:
     - `src/instagram_scraper/workflows/video_downloads.py`
   - Extract supporting pieces to helper modules, e.g.:
     - `src/instagram_scraper/workflows/video_download_support.py`
     - optional follow-up modules for checkpointing or metadata writing

2. Replace eager `comments.csv` loading with a bounded-memory lookup.
   - Options:
     - streaming iterator with grouped access assumptions, or
     - temporary SQLite-backed index for shortcode lookup
   - Avoid keeping all comments in memory for large runs.

3. Stop materializing the entire `posts.csv` into memory before processing.
   - Stream rows in two passes or use a temporary categorized index.
   - Preserve current ordering preference: videos before carousels.

4. Stop sharing a single `requests.Session` across download worker threads.
   - Replace with thread-local or per-worker sessions.
   - Ensure proper cleanup at the end of a run.

5. Improve checkpoint and summary responsibilities.
   - Keep checkpoint save and load helpers together.
   - Clarify when checkpoints are written and finalized.

6. Add logging around checkpoint load, save, and resume decisions.

#### Downloader test updates

- `tests/test_download_instagram_videos.py`
- Regression coverage for:
  - resume behavior
  - streaming row iteration
  - thread-local session pooling
  - large comment lookup behavior

**Effort:** medium

### 4. Database schema versioning and integrity guidance

**Outcome:** controlled schema evolution instead of implicit one-shot initialization.

#### Database tasks

1. Add a schema-version mechanism.
   - Target file:
     - `src/instagram_scraper/storage/database.py`
   - Options:
     - metadata table inside SQLite, or
     - adjacent version file
   - Prefer the metadata table for self-containment.

2. Introduce explicit initialization steps:
   - bootstrap schema
   - detect current version
   - migrate if required

3. Document current relational constraints and whether `SyncState.target_key` should be enforced against targets.

4. If foreign keys are adopted, make the migration explicit and testable.

#### Database test updates

- `tests/test_storage_db.py`
- `tests/test_sync.py`

**Effort:** small to medium

### 5. Remove production suppressions by fixing structure

**Outcome:** production code respects repo lint and type guardrails without `# noqa` or `# type: ignore` escapes.

#### Suppression cleanup tasks

1. Replace importer suppressions in exporter selection.
   - Target files:
     - `src/instagram_scraper/exporters/base.py`
     - `src/instagram_scraper/export_filters.py`
   - Prefer lazy imports via `import_module()` or a registry of module and class paths.

2. Remove logging stream typing suppression.
   - Target file:
     - `src/instagram_scraper/infrastructure/logging.py`
   - Use explicit variable typing rather than ignoring type mismatches.

3. Remove GUI output and widget-typing suppressions.
   - Target file:
     - `src/instagram_scraper/ui/gui.py`
   - Use helper wrappers or narrower interfaces instead of inline ignores.

4. Remove catch-all suppression markers by tightening exception handling where practical.
   - Particularly review the worker thread error boundary in `ui/gui.py`.

#### Suppression cleanup test updates

- `tests/test_exporters.py`
- `tests/test_gui.py`
- `tests/test_logging_config.py`

**Effort:** small to medium

### 6. Stabilize GUI tests

**Outcome:** deterministic GUI tests without timing sleeps.

#### GUI test stabilization tasks

1. Replace `time.sleep()` calls in GUI tests with deterministic synchronization.
   - Target file:
     - `tests/test_gui.py`
   - Preferred mechanisms:
     - `thread.join(timeout=...)`
     - polling helper with deadline
     - event-based synchronization

2. Add reusable test helper(s) for background worker completion.

3. Keep tests fast and platform-stable.

**Effort:** small

### 7. Scale-oriented tests

**Outcome:** confidence that larger input sizes do not break core workflows.

#### Scale-test tasks

1. Add larger synthetic CSV and comment fixtures for downloader tests.
   - Target file:
     - `tests/test_download_instagram_videos.py`

2. Add tests for bounded-memory row processing behavior.

3. Add tests for disk-backed comment lookup behavior if introduced.

4. Add at least one regression test covering many rows with a low limit to verify early termination remains correct.

**Effort:** small to medium

## Proposed execution order

### Phase 1: Quick wins

1. Auth hygiene and `.env` support
2. `.gitignore` update
3. README auth guidance
4. Remove easiest production suppressions
5. Stabilize GUI tests

### Phase 2: Core maintainability

1. Introduce mode registry
2. Refactor capabilities, pipeline, and GUI to use it
3. Add and update registry-related tests

### Phase 3: Downloader refactor

1. Extract helper module(s)
2. Replace eager CSV and comment loading
3. Introduce per-thread sessions
4. Improve checkpoint and logging structure
5. Add and update downloader tests

### Phase 4: Storage governance

1. Add schema versioning
2. Add migration and bootstrap tests
3. Document schema behavior

### Phase 5: Scale and polish

1. Add larger synthetic tests
2. Re-run full quality gates
3. Clean up naming, docs, and comments where needed

## Validation strategy

After each phase:

1. Run targeted tests for touched modules.
2. Run `uv run ruff check .`.
3. Run `uv run ty check`.
4. Run the full pytest suite before moving to the next phase.

## Risks and notes

- Sync modes should not be forgotten during the registry refactor.
- FreeSimpleGUI typing may require small adapter helpers rather than direct widget-method calls.
- A temporary SQLite comment index is likely the cleanest path for large downloader inputs.
- Schema versioning should be minimal and explicit; avoid introducing heavy migration tooling unless necessary.

## Definition of done

The remediation effort is done when:

- the audit recommendations have concrete code or doc changes in place
- the prioritized action plan items are completed
- no production suppression comments remain
- auth setup is safer and documented
- downloader memory and threading concerns are addressed
- schema versioning exists
- GUI tests are deterministic
- scale-oriented tests exist
- and the repository passes Ruff, Ty, and the full test suite
