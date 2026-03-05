# Ty Guardrails

- Never relax Ty strictness. Keep `[tool.ty.rules] all = "error"` and `[tool.ty.terminal] error-on-warning = true`.
- Never add Ty rule overrides that downgrade any check to `"warn"` or `"ignore"`.
- Never enable suppression-based type checking escapes, including `# type: ignore`, `# ty: ignore`, or `@no_type_check`.
- Keep `[tool.ty.analysis] respect-type-ignore-comments = false`.
