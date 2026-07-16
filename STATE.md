# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-16._

## Now
<!-- What's actively being worked. -->
- **Pass 0 (charter) authored** — THEORY / README / both member SPECs (PromptLang v1.0 full, Theory v1.0 spec-only) / ADR-0002 (extraction decision) / this spine. No code yet; the `prompt_lang` package arrives in Pass 1.

## Blockers
<!-- What's stopping progress. -->
- None. Charter awaits maintainer review before Pass 1.

## Next actions
<!-- The ordered next steps. -->
1. **Pass 1** — extract `prompt_lang` package + 4 test files from the harness; vendor `_globs.py`; add the `SKILL.md` file rule to the default config; port `/refactor` skill; `pyproject.toml` + plugin manifest; self-validation green.
2. **Pass 2** (harness repo) — harness becomes consumer #1: delete `agentic/prompt_lang/`, repoint imports/docs/kernel, full suite green.
3. **Pass 3** — de-rot the user-global `/refactor` skill pointers.
4. **Cairn adoption** (Cairn repo session) — repo-local config + validate check + `CONVENTIONS.md` citation when Cairn 1.2 lands.
5. Later: Theory teeth migration · codestandard member · public flip (Cairn playbook gates).

## Open questions
<!-- Unresolved decisions that need an answer. -->
- None open — extraction shape, naming, and visibility were ratified 2026-07-16 (see decisions/0002).
