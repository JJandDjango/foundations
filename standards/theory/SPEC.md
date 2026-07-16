---
name: theory-spec
description: Canonical specification of the Theory standard — commit nothing you could not explain.
reference: true
---

# Theory — Specification (v1.0, spec-only member)

**Governs:** *understanding*. A change is **done** only when its *why* is articulated and reconciles with the project's authored intent. Passing tests is necessary, not sufficient — generation is cheap; theory is scarce.

Named for Naur (*Programming as Theory Building*, 1985): a system's theory is the maintained model of *why it is the way it is* — held by people, not recoverable from code. This standard exists because AI-assisted work makes structure cheaper than understanding, and the gap between them is **drift**.

## 1. The bar

> **Commit nothing you could not explain.**

AI-authored structure with no theory behind it is incomplete, even if it runs.

## 2. The failure model

Drift runs in stages — the bar exists to stop the slide at stage 2:

1. You understand all of it.
2. The agent breaks a deliberate decision; you catch it.
3. You review faster, attend less — theory fogs.
4. Bad decisions slip in; the codebase pollutes.

The bar makes *"do I still understand this?"* a forced question at every commit, not a remembered one.

## 3. What counts as a rationale

- It states **why**, not a restatement of what the diff does.
- It **reconciles with authored intent**: where the repo carries an authored why-stratum (e.g. a Cairn `THEORY.md` + ADRs), the rationale must not contradict it — and if it *changes* intent, that stratum must change in the same body of work.
- It is **proportional**: a trivial claim ("typo", "rename") must actually match a trivial diff.
- It is **owned and terse**: a reviewer wants to see the contributor thinking; generated bulk is the thing this standard exists to prevent.

## 4. The four-part contract (member status)

| Part | This member |
|---|---|
| Spec | this document |
| Forcing function | commit-boundary rationale check: deterministic trivial-claim × diff-size cross-check, plus an optional local-LLM substance judge (warn-only, config-gated). **Resident in the origin harness today; migration here is planned — until then this member is spec-only.** |
| Scope | per repo: what the rationale reconciles against — the repo's authored why-stratum when present, else "is there a rationale at all?" |
| Standing invariant | one line in the consumer's always-loaded kernel: *commit nothing you could not explain.* |

## 5. Versioning

Spec v1.0, distilled from the origin harness's `THEORY.md` / `FOUNDATIONS.md` at extraction. Changes require an ADR in this repo's `decisions/`.
