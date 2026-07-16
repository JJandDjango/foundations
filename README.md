# foundations

One home for the portable engineering standards — each with a **spec** and **teeth** — so every repo adopts them without drift.

A *standard* here is not a style suggestion. Each member carries a four-part contract:

1. **Spec** — the canonical definition (in `standards/<member>/SPEC.md`).
2. **Forcing function** — deterministic enforcement at a trigger (a validator, a hook). Zero-LLM, zero-network.
3. **Scope** — what it governs, parameterized per repo by config.
4. **Standing invariant** — one line in the consumer's always-loaded kernel (e.g. a global `CLAUDE.md`).

Membership is gated by the sorting test: remove the standard — does *how we engineer* survive intact? If yes, it doesn't belong here.

## Members

| Standard | Governs | Spec | Teeth | Status |
|---|---|---|---|---|
| **PromptLang** | *Form* — every agent / validator / thread / command / skill prompt | `standards/promptlang/SPEC.md` | `prompt_lang/` validator (CLI: `python -m prompt_lang`) + `/refactor` skill | spec + teeth |
| **Theory** | *Understanding* — a change is done only when its why is articulated | `standards/theory/SPEC.md` | commit-boundary check (resident in the origin harness; migration planned) | spec-only here |
| **codestandard** | *Evaluation* — hard gates over code quality | — | — | planned member |

## Adopt a standard (3 steps)

```bash
# 1. Install (dev-time dependency only — never a runtime import)
pip install -e path/to/foundations        # local checkout
#   or: pip install git+ssh://git@github.com/JJandDjango/foundations

# 2. (Optional) override scope per repo
#    copy + edit prompt-lang.config.yaml, commit it at your repo root

# 3. Validate (file or directory; recurses over *.md)
python -m prompt_lang path/to/prompts --config prompt-lang.config.yaml
```

Exit codes: `0` pass · `1` validation errors · `2` config error · `3` path not found. Wire step 3 into CI and the standard has teeth in your repo.

## Relationship to Cairn

[Cairn](https://github.com/JJandDjango/cairn) answers *"where does project knowledge live?"* (the docs spine). **foundations** answers *"what rules does our work obey, and what enforces them?"* They compose: a Cairn-scaffolded project's `CONVENTIONS.md` (Cairn 1.2) *cites* a foundations standard + ADR; the standard's validator supplies the enforcement. Content is never copied across.

## Layout

```
standards/<member>/SPEC.md   # canonical specs (slowest layer)
prompt_lang/                 # PromptLang validator package (CLI: python -m prompt_lang)
skills/refactor/             # migration/validation skill (plugin-distributable)
THEORY.md · MAP.md · STATE.md · decisions/ · docs/   # Cairn spine (this repo dogfoods it)
```

## Status

Private, pre-1.0. Extracted from the agentic harness (see `decisions/0002`); public flip follows the Cairn playbook once dogfooding across two consumers is green.
