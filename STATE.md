# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-16._

## Now
<!-- What's actively being worked. -->
- **Pass 1 (extraction) done** — `prompt_lang/` package landed (imports rewritten, `_globs.py` vendored, origin-doc references repointed to the SPEC), 4 test suites ported + self-validation + hook three-branch contract = **69 green**. Default config gained the `**/skills/*/SKILL.md` artifact class. `/refactor` skill ported + de-rotted (its own stray `</output>` and a tag-shaped placeholder were caught by self-validation — the teeth bit their author on day one). Author-side hook (`hooks/validate_prompt.py`) + plugin/marketplace manifests shipped. `pip install -e` verified.

## Blockers
<!-- What's stopping progress. -->
- None.

## Next actions
<!-- The ordered next steps. -->
1. **Pass 2** (harness repo) — harness becomes consumer #1: delete `agentic/prompt_lang/`, repoint imports/docs/kernel, install the plugin (hook live-fire), full suite green.
2. **Pass 3** — de-rot the user-global `/refactor` skill pointers.
3. **Public flip** — gate to Cairn adoption (LICENSE, CONTRIBUTING, ruleset, stranger README pass).
4. **Cairn adoption** (Cairn repo session) — repo-local config + `importorskip` conformance test + `CONVENTIONS.md` citation when Cairn 1.2 lands.
5. Later: Theory teeth migration · codestandard member · marketplace publish.

## Open questions
<!-- Unresolved decisions that need an answer. -->
- None open — extraction shape, naming, and visibility were ratified 2026-07-16 (see decisions/0002).
