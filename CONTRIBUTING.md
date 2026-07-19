# Contributing to foundations

Thanks for helping sharpen the standards. This project is small, solo-maintained,
and governed by the standards it ships — so contributing has a little structure,
and this page is all of it.

## The one rule: `main` is protected — contribute by fork + PR

`main` carries a ruleset ([`scripts/ruleset-protect-main.json`](scripts/ruleset-protect-main.json))
that blocks force-pushes, blocks deletion, and **requires a pull request for every
change** — including from the maintainer. Only the maintainer has write access to
this repo; nobody pushes to `main` directly. That's the same discipline the
standards themselves preach, enforced on the standards repo.

So the flow for any outside change is **fork → branch → PR**:

1. **Fork** the repo and clone your fork.
2. **Branch:** `git checkout -b fix-short-description`
3. Make the change.
4. **Run the suite:** `pip install -e ".[dev]"` then `python -m pytest`.
   Green before you push.
5. **Self-conformance:** the prompt artifacts in this repo obey their own
   standard — `python -m prompt_lang skills` must PASS
   (`tests/test_self_validation.py` enforces it).
6. Keep the docs spine honest — see below.
7. **Push to your fork and open a PR against `main`.** Say *what* changed and *why*.

For anything non-trivial — especially a change to a `standards/<member>/SPEC.md` —
**open an issue first** so we agree on the shape before you build. A SPEC change
changes what every consumer repo enforces; it needs a why that survives review.
Typos and small fixes: just send the PR.

## Keep the spine honest (foundations dogfoods the Cairn spine)

A change isn't done until the right stratum is updated:

| You… | Update |
|---|---|
| add / remove / rewire a piece | that Component's row in [`MAP.md`](MAP.md) (hand-authored) |
| make a decision a future maintainer would question | a new ADR — copy [`decisions/ADR-template.md`](decisions/ADR-template.md) to `NNNN-title.md`. **Never edit an existing ADR; supersede it.** |
| change what a standard *is* | its `standards/<member>/SPEC.md` **and** an ADR recording the why |

Leave **`STATE.md`** alone — it's the maintainer's disposable session handoff,
regenerated at session end, not a contribution surface.

## Commits & license

- Focused commits, imperative subject line — and say *why*, not just what.
- By contributing, you agree your work is licensed under the **MIT License**
  ([`LICENSE`](LICENSE)) — inbound = outbound.

## What to expect

Solo-maintained, so review may take a few days. CI must be green (the suite runs
on Linux + Windows); external PRs are read before merge.
