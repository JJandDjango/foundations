# 2. Extract the standards family from the agentic harness

Status: accepted
Date: 2026-07-16

## Context

The engineering standards (PromptLang foremost, Theory beside it) were born inside the agentic harness repo and lived there as `agentic/prompt_lang/` + `FOUNDATIONS.md`. Three forces broke that arrangement:

- **Visibility asymmetry.** The harness is private; its first external consumer (Cairn) is public. A public repo cannot cite, install, or CI-check a standard whose source it cannot see.
- **Observed drift.** Cairn's `SKILL.md` already *uses* PromptLang form without being able to name or enforce it, and the user-global `/refactor` skill — PromptLang's own migration tool — still pointed at a pre-rebuild module path that had been dead for months. The standard's home moved fast; its satellites rotted.
- **N consumers coming.** The maintainer wants the standards in every future repo. Hub-and-spoke (one source, many dependents) beats pairwise feeds from a private monolith.

Alternatives weighed: feeding consumers from the harness via the L2 bundle/emitter tier (rejected — bundles package *prompt assets*, not a language spec + validator; and the private-source problem remains); folding the standards into Cairn (rejected — violates Cairn's anti-scope; docs spine and standards enforcement are different concerns that *compose* via Cairn 1.2's planned `CONVENTIONS.md` citation slot).

Precedent: the ATLAS → Cairn extraction proved the playbook — extract, hold standalone invariants from birth, dogfood, publish deliberately.

## Decision

Create `foundations` as the umbrella home of the standards family, each member under the four-part contract (spec · forcing function · scope · standing invariant). PromptLang moves first with full teeth: the `prompt_lang` package (import name kept, minus the `agentic.` prefix), its default config, its tests, and the `/refactor` skill. Theory joins as spec-only (teeth follow later). The repo starts private and flips public on the Cairn playbook. The harness becomes consumer #1; Cairn consumer #2.

## Consequences

- One source of truth for each standard; consumers adopt by dev-time dependency + per-repo config override, never by copy.
- The harness loses ~7 files and gains a dependency — its L1 CI must install this repo (trivial after the public flip; a deploy-key wrinkle before it).
- The `SKILL.md` artifact class joins the default file rules — the first spec change born from a real second consumer.
- `_globs.py` (59-line glob matcher) is vendored into the package rather than shared — an accepted, documented duplication; the harness keeps its own copy for filesystem policy.
- Theory's forcing function stays harness-resident for now; this repo carries the spec so consumers can already cite it.
