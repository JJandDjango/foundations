# Map - foundations

> **Contract** - one question: *what are the pieces, and how do they connect?*
> <=2 pages - update on add / remove / rewire of a Component - hand-edited.

## Diagram
```mermaid
flowchart TD
    SPEC["standards/&lt;member&gt;/SPEC.md<br/>(canonical specs)"] -->|define| PKGS["prompt_lang/ · theory/ · codestandard/<br/>(form validator · commit checker · code gate)"]
    PKGS --> CLIS["CLIs: python -m prompt_lang ·<br/>python -m theory · python -m codestandard"]
    SKILL["skills/refactor<br/>(migration skill)"] -->|invokes| CLIS
    HOOK["hooks/validate_prompt.py<br/>(PostToolUse, plugin-shipped)"] -->|imports| PKGS
    GITHOOK["theory/hooks/commit-msg<br/>(installable git hook)"] -->|invokes| CLIS
    CLIS -->|dev-time dep| CONSUMER["consumer repo<br/>(CI / session)"]
    HOOK -->|author-side feedback| CONSUMER
```
<!-- The ONE diagram in this project, at ~C4 container zoom. Anything deeper
     rots faster than you can maintain it - use the table below for detail. -->

## Components
<!-- One row per piece - one-line responsibility - link the deep doc once it exists (else "no doc yet"). -->

| Component | Responsibility (one line) | Status | Deep doc |
|---|---|---|---|
| `standards/promptlang/SPEC.md` | canonical PromptLang spec — the form standard for prompt files | stable (v1.0) | standards/promptlang/SPEC.md |
| `standards/theory/SPEC.md` | canonical Theory spec — commit nothing you could not explain | stable (v1.1) | standards/theory/SPEC.md |
| `standards/codestandard/SPEC.md` | canonical codestandard spec — every unit explainable in one bounded breath, mechanically gated | stable (v1.0) | standards/codestandard/SPEC.md |
| `prompt_lang/` | the PromptLang validator package (parser · validator · config · directives · CLI); ships the default config | stable | no doc yet |
| `theory/` | the Theory forcing function (checker · config · CLI · warn-only judge · installable commit-msg hook); generic defaults, repos narrow via `theory.config.yaml` | stable | no doc yet |
| `codestandard/` | the evaluative engine — measures source against the packaged house standard via pinned OSS checkers (`[codestandard]` extra) | stable | no doc yet |
| `theory.config.yaml` | repo-local Theory scope — self-application of the second member (advisory) | live | no doc yet |
| `skills/refactor/` | migration + validation skill invoking the CLI (plugin-distributable) | stable | no doc yet |
| `hooks/` | author-side PostToolUse hook — validates prompt-artifact writes; silent no-op without `prompt_lang` | stable | no doc yet |
| `.claude-plugin/` | plugin + marketplace manifests (version mirrors `pyproject.toml`) | stable | no doc yet |
| `.github/workflows/` | self-CI — the suite plus gating `codestandard` runs over every package, ubuntu+windows × py 3.11/3.12 | stable | no doc yet |
| `scripts/` | repo governance playbook — the versioned `protect-main` ruleset + its exact apply call | stable | no doc yet |
| `tests/` | validator/parser/config/directives suites + the migrated theory/codestandard suites + self-validation + hook contract | stable (438 green) | no doc yet |
| `decisions/` | append-only ADR trail (why-history) | live | no doc yet |
