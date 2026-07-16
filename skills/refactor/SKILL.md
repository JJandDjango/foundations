---
name: refactor
description: Migrates prompt files to the PromptLang specification. Validates files using the prompt_lang validator and converts non-compliant markdown to XML tag format.
tools: Bash, Read, Edit
---

# Refactor

<purpose>
Migrate prompt files to comply with the PromptLang specification (standards/promptlang/SPEC.md in the foundations repo). Run validation, identify issues, and convert markdown-headed sections to XML tags.
</purpose>

<variables>
| Variable | Description | Default |
|----------|-------------|---------|
| `$1` | Target file or directory to migrate | Required |
</variables>

<context>
PromptLang uses XML tags to distinguish execution from documentation.

**Required tags:** purpose, instructions

**Optional tags:** variables, context, constraints, examples, output, criteria, routing, directives

**Validation tool:** the `prompt_lang` package from the foundations repo (`pip install -e path/to/foundations`); CLI is `python -m prompt_lang`.

**Common migrations (markdown heading to XML tag):**

| Old Format | New Format |
|------------|------------|
| `## Purpose` | purpose tag |
| `## Instructions` | instructions tag |
| `## Variables` | variables tag |
| `## Context` or `## Structure` | context tag |
| `## Constraints` | constraints tag |
| `## Examples` | examples tag |
| `## Report` or `## Output` | output tag |
| `## Success Criteria` | criteria tag |

**Frontmatter requirements:**
- `name` (required)
- `description` (required)
- `model`, `tools`, `argument-hint`, `agent` (optional)

**Reference:** the canonical spec is `standards/promptlang/SPEC.md`; this file is itself a conforming example.
</context>

<instructions>
1. EXECUTE the validator on the target path
   ```bash
   python -m prompt_lang $1
   ```
2. REPORT success and stop if validation passes
3. CHECK validation results and read each failing file
4. EXECUTE the following fixes for each failing file:
   - Add YAML frontmatter if missing (name, description fields)
   - Convert markdown headings to their corresponding XML tags
   - Remove ambiguous/hedging language from instructions (see config for patterns)
   - Ensure no nested tags (all tags must be top-level)
5. VERIFY fixes by re-running validation
   ```bash
   python -m prompt_lang $1
   ```
6. REPORT results
</instructions>

<constraints>
- Do not delete content, only restructure it
- Do not modify files that already pass validation
- Do not add tags that have no corresponding content
- Do not nest XML tags inside each other
- Do not use ambiguous language in instructions
</constraints>

<output>
| Field | Value |
|-------|-------|
| **Target** | $1 |
| **Files checked** | [count] |
| **Already compliant** | [count] |
| **Migrated** | [count] |
| **Status** | [PASS / FAIL] |
</output>

<criteria>
- [ ] Validator run on target path
- [ ] All failing files identified
- [ ] Each file migrated to XML tag format
- [ ] Frontmatter present with name and description
- [ ] No ambiguous language in instructions
- [ ] No nested tags
- [ ] Re-validation passes
</criteria>
