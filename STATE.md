# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-19._

## Now
- **Public flip executed** (orchestrator session #178): LICENSE (MIT) +
  CONTRIBUTING + `scripts/` protection playbook (ruleset JSON + apply call)
  + self-CI (`.github/workflows/ci.yml`, ubuntu+windows x py 3.11/3.12) +
  README stranger pass (ssh->https install, public Status). Repo flipped
  public and the `protect-main` ruleset applied immediately after this
  commit's push — from then on, main takes PRs only (`bypass_actors: []`
  binds the owner too). Anonymous `pip install git+https://` proven from a
  clean venv.
- **Consumer CI live**: Cairn's `tests/test_promptlang.py` importorskip gate
  now runs enforced in Cairn's CI (installs this repo anonymously) — the
  adoption chain from decisions/0002 is closed end to end.
- Consumer #1 (origin harness) consumes via local `pip install -e` + the
  user-scope plugin; the FOUNDATIONS_TOKEN blocker dissolved (the harness
  dropped its CI dependency at the old-loop retirement, and the repo is
  public now regardless).

## Blockers
- None.

## Next actions
1. **Hook live-fire smoke** — in a fresh session, Write a malformed prompt
   artifact and observe the PostToolUse feedback.
2. **Theory teeth migration** from the origin harness (its forward #2);
   codestandard member follows.
3. **Marketplace publish** + plugin-ignore for cache junk
   (`__pycache__`/egg-info snapshot into the plugin cache).
4. Optional: add `required_status_checks` (the new CI) to protect-main once
   a run history exists.

## Open questions
- None.
