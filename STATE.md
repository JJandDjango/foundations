# State - foundations

> **Contract** - one question: *what is in flight right now?*
> <=1 page - regenerate at every session end - disposable, always safe to overwrite.
> _Generated 2026-07-19._

## Now
- **Public flip executed** (orchestrator session #178): LICENSE (MIT) +
  CONTRIBUTING + `scripts/` protection playbook + self-CI workflow +
  README stranger pass. Repo PUBLIC, `protect-main` ruleset 19182309
  active (`bypass_actors: []` binds the owner; main takes PRs only).
  Anonymous `pip install git+https://` proven from a clean venv (resolved
  `4118e97`, wheel built, installed validator PASSes a real file).
- **Consumer CI live**: Cairn's `tests/test_promptlang.py` importorskip
  gate now runs enforced in Cairn's CI - its run log shows
  `test_claimed_prompt_artifacts_pass_validation PASSED`, 204 green -
  the decisions/0002 adoption chain is closed end to end.
- **Hook live-fire smoke DONE** (was next-action #1): PostToolUse fired on
  a non-conforming scratch SKILL.md Write (5 precise errors fed back to
  the agent) and stayed silent on the conforming rewrite - both branches
  proven in a live session.
- **Actions event runs are wedged platform-side** (flip day): every run -
  push, pull_request, even workflow_dispatch - dies at startup with
  GitHub's "unexpected error ... automatically notified ... sometimes
  temporary" page, zero jobs created; identical shapes ran green on two
  sibling repos in the same minutes, so the file is not the cause (it
  registers, attributes, and dispatch-accepts correctly). Likely bad
  service state from registering the workflow and flipping visibility
  within the same minutes. PR #1 (CI badge + `workflow_dispatch` trigger
  + the 3.12-only matrix simplification from triage) is HELD OPEN until
  runs flow.

## Blockers
- GitHub-side Actions startup errors on this repo (their own page calls
  it temporary and auto-reported). Nothing actionable in-repo; retry
  later.

## Next actions
1. **Re-dispatch CI** (`gh workflow run ci.yml -R JJandDjango/foundations
   --ref readme-ci-badge`); when green: merge PR #1, dispatch once on
   `main` so the README badge shows green, then restore the 3.11 floor
   (and optionally the pip cache block) dropped during triage.
2. **Theory teeth migration** from the origin harness (its forward #2);
   codestandard member follows.
3. **Marketplace publish** + plugin-ignore for cache junk
   (`__pycache__`/egg-info snapshot into the plugin cache).
4. Optional: `required_status_checks` on protect-main once a run history
   exists.

## Open questions
- None.
