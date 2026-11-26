# Switchyard (`app/`)

The workspace root `AGENTS.md` applies here; this file only adds what is local.

- The `AGENTS.md`, `CLAUDE.md` and `README.md` shipped in this directory described release
  2.0 and contradict the contracts on the delivery guarantee, who assigns ids, retry timing,
  lease length and the bus version. The first two are now in `_deprecated/` as
  `old-*.txt`. Treat `README.md` and the service READMEs the same way: leads, not rules.
- `contracts/` is what the system must do. Where it is silent, the code decides.
- `docs/adr/`: a record's status line says whether a later one replaced it.
- Tests per service: see `services/<name>/AGENTS.md`. Everything at once: `kit/check.sh`
  from the workspace root.
