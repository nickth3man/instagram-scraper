# Ty Guardrails

- Never relax Ty strictness. Keep `[tool.ty.rules] all = "error"` and `[tool.ty.terminal] error-on-warning = true`.
- Never add Ty rule overrides that downgrade any check to `"warn"` or `"ignore"`.
- Never enable suppression-based type checking escapes, including `# type: ignore`, `# ty: ignore`, or `@no_type_check`.
- Keep `[tool.ty.analysis] respect-type-ignore-comments = false`.

# Ruff Guardrails

- Keep production Ruff checks at maximum strictness. Do not reduce rule coverage for `src/`, do not disable preview lint rules, and do not add global `lint.ignore` or `lint.extend-ignore` settings.
- Test-only Ruff relaxations are allowed under `tests/` when they are narrowly scoped to common test ergonomics and do not weaken production code rules.
- Never add inline Ruff suppression comments such as `# noqa`, `# noqa: ...`, or file-level Ruff disables.
- Never change Ruff settings to make the codebase easier to pass. Fix the code instead.

# Completion Gate

- Keep Ty strict for production code. Test-only exclusions are allowed if they do not weaken `src/` checking.
- Before completing any task, run Ruff, Ty, and the full test suite, then keep iterating until all three pass.
- Do not claim success, completion, or readiness unless the latest `ruff check .`, `ty check`, and full test run have all passed in the current workspace state.
