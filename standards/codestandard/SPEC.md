---
name: codestandard-spec
description: Canonical specification of the codestandard member — every unit of code explainable in one bounded breath, mechanically gated.
reference: true
---

# codestandard — Specification (v1.0)

**Governs:** *code explainability*. The evaluative, code-side enforcement arm of [Theory](../theory/SPEC.md) — **not a third axiom**: PromptLang enforces *commit nothing you could not explain* for prompts; this enforces it for code.

Ratified in the origin harness, session #143 (2026-06-17); design history in its `designs/code_philosophy.md` (evaluative pillar; the constructive sibling is unadopted design).

## 1. Root principle

> **Every unit of code must be explainable, on its own, in one bounded breath — and a codebase is that bound applied recursively.**

*"Too complex"* = the explanation overflows the breath. A *module boundary* = where you'd naturally start a new sentence. Readability and bounded-complexity aren't separate goals; they're what explainability requires.

## 2. The hard-gated filter

Every rule must **name its gate**. Mechanically uncheckable → it is *rationale* (the why layer), not a *rule* (the what layer). This filter keeps the standard from rotting into platitudes. Gates carry **coverage tiers**, one honest admission deep:

| Tier | Meaning |
|---|---|
| **Certify** | pass = compliant (length, complexity, params) |
| **Tripwire** | fail = bad, pass ≠ good — review backstops (naming, responsibility) |

## 3. The five principles

All derived from *one unit, one bounded breath*:

| Principle | One breath | Tier | Gate |
|---|---|---|---|
| **Size** | fits in one view | certify | function / file length |
| **Branching** | one breath of control flow | certify | cognitive + cyclomatic + nesting |
| **Interface** | callable without explaining its inputs | certify | params / returns |
| **One responsibility** | name it without "and" — else split | tripwire | cohesion + complexity-as-symptom |
| **Names carry intent** | the names pre-write the explanation | tripwire | min-length + banned vague names |

Rationale-only (informs the tripwires, no gate of its own): *one abstraction level*. Out of scope: fan-out / coupling (architecture tier, unratified).

## 4. Mechanism

- **House standard = data**: `codestandard/code_standard.yaml` (package data — Tier-1 numbers + rule selection, one flat `rules:` map; `hard_max` keeps "hard-gated" honest under overrides).
- **Engine = conductor, not parser**: Python orchestrates each language's own native tooling as subprocesses (Python → `ruff` + `flake8-cognitive-complexity`; vendored OSS, offline, version-pinned via the `foundations[codestandard]` extra). The engine consumes verdicts; it never parses foreign source.
- **CLI is the load-bearing artifact**: `python -m codestandard <project_root> [--standard <path>]` → exit 0 clean / 1 findings, one `rule  file:line  measured/limit  message` line per breach. A hard gate must fire in CI with no agent in the loop.

## 5. Adoption — fix-then-gate

The gate activates with **zero baseline**. Every pre-existing breach is deliberately resolved first — most by refactoring, the legitimately-complex few by an explicit reasoned exception (an exception you can *explain*) — never wholesale grandfathered: a grandfathered baseline is committing debt you haven't explained.

## 6. The four-part contract (member status)

| Part | This member |
|---|---|
| Spec | this document |
| Forcing function | the `codestandard` engine CLI, gating in this repo's own CI (self-application) |
| Scope | per repo: project root(s) measured; `--standard` override for house-number deltas (never past `hard_max`) |
| Standing invariant | **covered by Theory's kernel line** — this member is Theory's code-side arm, not a separate axiom |

## 7. Versioning

Spec v1.0. The house numbers live in the data file and version independently (`code_standard.yaml` `version:`). Changes to either require an ADR in this repo's `decisions/`.
