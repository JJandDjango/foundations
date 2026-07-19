#!/usr/bin/env pwsh
# apply-branch-protection.ps1 — apply the `protect-main` ruleset to JJandDjango/foundations.
#
# This is the exact `gh api` call, captured so main's protection is reproducible and
# version-controlled instead of a one-off click in the web UI. Body: ruleset-protect-main.json.
#
# Rules applied (see the JSON): block force-pushes + block deletion of the default branch,
# and require a pull request before merging (0 approvals -> solo owner self-merges; the PR
# flow is still enforced for every change).
#
# PREREQUISITES
#   1. gh CLI installed + authenticated:  gh auth status
#   2. foundations must be PUBLIC first — rulesets are free on public repos; run this the
#      moment after you flip it public (on the Free plan they're gated to public repos —
#      even the GET returns 403 while private).
#   3. You must be the repo admin (owner).
#
# RUN ONCE. POST creates a new ruleset each call — running twice makes a duplicate.
#   Verify:  gh api /repos/JJandDjango/foundations/rulesets
#   Update:  edit in the UI, or DELETE the old one first:
#            gh api --method DELETE /repos/JJandDjango/foundations/rulesets/<id>
#   UI:      Settings -> Rules -> Rulesets -> protect-main
#
# OPTIONS (edit ruleset-protect-main.json)
#   - Dry-run first: set "enforcement" to "evaluate" — logs violations without blocking.
#   - Owner escape hatch (push directly to main in a pinch): add the Repository admin role
#     to the ruleset's Bypass list (Settings -> Rules -> Rulesets -> protect-main -> Bypass list).
#   - Require CI green before merge (the Actions workflow exists): add a
#     { "type": "required_status_checks", ... } rule to the JSON.

$ErrorActionPreference = 'Stop'
$body = Join-Path $PSScriptRoot 'ruleset-protect-main.json'
gh api --method POST -H "Accept: application/vnd.github+json" /repos/JJandDjango/foundations/rulesets --input "$body"
