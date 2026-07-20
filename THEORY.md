# Theory - foundations

> **Contract** - one question: *why does this exist, and what must stay true?*
> <=1 page - update when purpose or invariants change - hand-edited, rare.

## Intent
One home for the portable engineering standards - each with a spec and teeth - so every repo adopts them without drift.

## Invariants
<!-- What must stay true no matter what changes below. The load-bearing constraints. -->
- **Every member standard carries the four-part contract** (or is explicitly marked spec-only until its teeth arrive): **Spec** (canonical definition) · **Forcing function** (deterministic enforcement at a trigger) · **Scope** (per-repo config) · **Standing invariant** (one line in the consumer's always-loaded kernel). Teeth without presence is a linter; presence without teeth is a suggestion.
- **The sorting test governs membership:** remove the standard — does *how we engineer* survive intact? If yes, it is not a Foundation and does not live here.
- **Enforcement is deterministic and offline.** Validators run zero-LLM, zero-network; any consumer can run them in any CI.
- **Source of truth lives here; consumers adopt by dependency + per-repo config override, never by copy.** Copies are how drift starts — the extraction that created this repo was triggered by exactly that rot.
- **Dev-time tooling only, and honest about its deps** (PyYAML + tiktoken; the optional `[codestandard]` extra adds the pinned OSS checkers). Never a runtime import of any consumer's software.
- **Public-ready from birth:** package code, tests, and specs carry no knowledge of any particular consumer. Decision history (ADRs, STATE) may name consumers — that is provenance, not coupling.

## Success criteria
<!-- How you'll know it's working. -->
- A repo adopts a standard in three steps (install → optional repo config → run) without reading this repo's source.
- At least two real consumers validate green against the same installed standard.
- The standard's own artifacts pass its own validator (self-application, always).

## Non-goals
<!-- What this explicitly does NOT try to do - the anti-scope that stops drift. -->
- **Not a prompt library** — no agent/command/thread content ships from here; only the rules such content must obey.
- **Not a documentation system** — Cairn owns the docs spine; a consumer's `CONVENTIONS.md` *cites* these standards, it doesn't reproduce them.
- **Not a general code linter or CI framework** — members are named standards with specs, not a grab-bag of checks.
- **Not on PyPI** — git/plugin install only; consumers pin by ref.
- **Never load-bearing at runtime** for any consumer.
