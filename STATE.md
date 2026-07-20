# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-19._

## Now
- **Second and third members LANDED** (orchestrator session #179; ADR 0003,
  PR #2 rebase-merged to `7e4473e`, CI green on all 4 legs): `theory/`
  (commit-boundary checker, CLI + installable hook, `map:` reconcile,
  warn-only judge) and `codestandard/` (evaluative engine, house standard
  as package data, checkers via the `[codestandard]` extra). v0.2.0.
- **Fix-then-gate executed**: the inherited 18-finding backlog (incl.
  prompt_lang's parser pair) refactored to zero, no exceptions; CI now runs
  gating `python -m codestandard` over every package (self-application).
- **Self-application both ways**: this repo carries its own
  `theory.config.yaml` + installed commit-msg hook (advisory; live-probed
  both branches). Suite: 438 green.
- The #178 Actions wedge cleared service-side — PR #2's checks ran
  normally; PR #1 (badge + dispatch) can now be revisited.
- Origin harness cut over same-day: deleted its `agentic/` + repointed its
  hook (its decisions/0010); it and this repo both consume from here.

## Blockers
- None.

## Next actions
1. **Close PR #1** (badge + dispatch trigger) — the wedge that held it is
   gone; re-check its diff still applies, then merge.
2. **Marketplace publish** + plugin-ignore for cache junk
   (`__pycache__`/egg-info snapshot into the plugin cache).
3. Add `required_status_checks` (the CI) to protect-main — a run history
   exists now.
4. Optional: third consumer (Cairn) adopts the theory hook.

## Open questions
- None.
