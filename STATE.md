# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-16._

## Now
<!-- What's actively being worked. -->
- **Consumer #1 is live.** The origin harness deleted its in-tree copy and consumes this repo (its `6c63afd`: imports repointed, 3594-test suite green, kernel invariant repoints here, CI/Dockerfile install the dep, fresh-venv portability test models the two-step install). The **plugin is installed at user scope** (skills + PostToolUse hook; hook activates in new sessions — regression-tested here, live-fire smoke pending). The user-global `/refactor` skill was de-rotted and PASSes via `python -m prompt_lang`.
- Pass 1 recap: `prompt_lang/` extraction, **69 green**, SKILL.md artifact class added, self-validation caught its own author twice on day one.

## Blockers
<!-- What's stopping progress. -->
- Harness CI needs the one-time `FOUNDATIONS_TOKEN` secret (fine-grained PAT, contents:read on this repo) before its next PR/main push — dissolves at the public flip.

## Next actions
<!-- The ordered next steps. -->
1. **Hook live-fire smoke** — in a fresh session, Write a malformed prompt artifact and observe the PostToolUse feedback.
2. **Public flip** — gate to Cairn adoption (LICENSE, CONTRIBUTING, `protect-main` ruleset, stranger README pass; `.gitattributes` already in).
3. **Cairn adoption** (Cairn repo session) — repo-local config + `importorskip` conformance test + `CONVENTIONS.md` citation when Cairn 1.2 lands; fix Cairn ROADMAP's stale "remote exists — private" line.
4. Later: Theory teeth migration · codestandard member · marketplace publish · plugin-ignore for cache junk (`__pycache__`/egg-info snapshot into the plugin cache).

## Open questions
<!-- Unresolved decisions that need an answer. -->
- None open — extraction shape, naming, and visibility were ratified 2026-07-16 (see decisions/0002).
