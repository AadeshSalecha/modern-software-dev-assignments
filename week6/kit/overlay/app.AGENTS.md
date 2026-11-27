# Switchyard (`app/`)

The workspace root `AGENTS.md` applies here; this file only adds what is local.

- The `AGENTS.md` and `CLAUDE.md` shipped in this directory were moved to `_deprecated/` as
  `old-*.txt` before you started. Like `README.md` and the service READMEs they may describe
  an earlier release: read them as leads and check each claim against `contracts/` and the
  code before relying on it.
- `contracts/` is what the system must do. Where it is silent, the code decides.
- `docs/adr/`: a record's status line says whether a later one replaced it.
- Tests per service: see `services/<name>/AGENTS.md`. Everything at once: `bash kit/check.sh`
  from the workspace root.
