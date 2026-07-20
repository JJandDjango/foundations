# 3. Adopt the Theory teeth and the codestandard member

Status: accepted
Date: 2026-07-19

## Context

0002 extracted the standards family with Theory as a spec-only member: its forcing function — the commit-boundary rationale checker — stayed resident in the origin harness, alongside the codestandard engine (the evaluative code-quality gate designed as Theory's code-side arm, origin session #143). The origin repo has since retired its autonomous loop (its decisions/0009) and kept both packages alive *solely* for this migration; leaving them there indefinitely would recreate the exact private-source / drift problem 0002 was written to end.

The engine's Phase 6 backlog also collapsed with that retirement: of the 128 calibrated breaches, all but 18 lived in deleted harness code. The remaining 18 (13 in the theory package itself, 4 in `prompt_lang/parser.py`, 1 in the hook) made fix-then-gate achievable in the migration arc itself.

## Decision

Both packages move here, becoming this repo's second and third installable members:

- **theory** — the Theory forcing function (CLI `python -m theory`, installable commit-msg hook, deterministic trailer/scope/trivial checks, optional warn-only local-LLM judge). The theory SPEC advances to v1.1: teeth resident, and the `Theory:` git trailer named as the deterministic anchor.
- **codestandard** — the evaluative engine (CLI `python -m codestandard`), with the house standard as package data and the pinned OSS checkers behind the optional `foundations[codestandard]` extra. New member SPEC at `standards/codestandard/SPEC.md`; its standing-invariant slot is covered by Theory's kernel line (it is Theory's code-side arm, not a third axiom).

Public-surface corrections applied in transit: package names are the member slugs (`theory`, `codestandard`); the ATLAS-era `atlas:` config block becomes `map:`; config discovery moves from `.agentic/theory.config.yaml` to a repo-root `theory.config.yaml`; the packaged default scope becomes the generic `["**"]` (the origin repo's globs were consumer knowledge in package defaults, violating the public-ready invariant); the smoke CLI no longer defaults to a consumer-machine model id.

Fix-then-gate executes to completion: the 18 remaining breaches are refactored to **zero** (no reasoned exceptions), and CI gains gating `python -m codestandard` steps over every package — self-application per the codestandard SPEC. This repo also installs its own theory hook with a repo-local config (advisory), eating the second member's cooking too.

## Consequences

- Provenance: the packages arrive as new files here; their build history stays in the origin harness (tag `old-loop-final` and onward). Both suites came along (~370 tests; repo total 438).
- The origin repo deletes `agentic/` entirely and repoints its commit-msg hook at `python -m theory` — it becomes a pure consumer, closing its last 0009 holdout (`.agentic/`).
- `theory` and `codestandard` are generic top-level import names; a consumer repo with a same-named cwd package would shadow them. Accepted for git-installed dev tooling (PyPI remains a non-goal).
- The judge remains config-gated and absent from defaults: enforcement stays deterministic-and-offline by default, per the repo invariant; a repo that opts in accepts the LLM dependency locally.
- Consumers narrow the `["**"]` default scope per repo; an unconfigured install advisory-warns on every commit without a trailer — the honest generic reading of the bar.
