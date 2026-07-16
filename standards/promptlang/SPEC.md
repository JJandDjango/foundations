---
name: promptlang-spec
description: Canonical specification of the Prompt Programming Language (PromptLang) — the form standard for prompt files.
reference: true
---

# PromptLang — Specification (v1.0)

**Governs:** the *form* of prompt files — agent, validator, thread, and slash-command prompts, and skill entry points (`SKILL.md`). A conforming file is deterministic to parse, carries its own metadata, states its purpose and instructions in tagged blocks, and stays inside a token budget.

**Enforced by:** the `prompt_lang` validator in this repo (`python -m prompt_lang <path> [--config <yaml>]`). Zero-LLM, zero-network. Cross-file integrity (do referenced files exist, do names resolve) is explicitly out of scope — that belongs to a consumer's lint layer. The validator sees one file at a time.

## 1. File form

A conforming file is UTF-8 Markdown with two parts:

```markdown
---
name: my-agent
description: One line on what this prompt is for.
---

<purpose>
Why this prompt exists and what the agent is.
</purpose>

<instructions>
1. PARSE the input.
2. EXECUTE the task.
</instructions>
```

### 1.1 Frontmatter

YAML frontmatter is required: the file must begin with `---` and close the block with `---`, and the content must be a YAML mapping.

- **Required fields:** `name`, `description`.
- **Optional fields:** `model`, `argument-hint`, `tools`, `agent`, `color`, `reference`.

A missing block, an unclosed block, invalid YAML, a non-mapping, or a missing required field is an **error**. (A file rule may set `skip_frontmatter: true` for artifact classes that carry none.)

### 1.2 Body tags

The body is organized in XML-style tag blocks. Tag names match `[a-z][a-z0-9-]*` (matched case-insensitively; write them lowercase).

- **Required tags:** `<purpose>`, `<instructions>` — both must be present (configurable; file rules may add or skip).
- **Optional tags:** `<variables>`, `<context>`, `<constraints>`, `<examples>`, `<output>`, `<criteria>`, `<routing>`, `<directives>`.

Errors: an **unrecognized tag** (not in the required∪optional set), an **unclosed tag**, an **extra closing tag**, a **mismatched closing tag**, and **nesting** — recognized tags never nest; every block is top-level. A missing required tag is an error.

Tag *order* is not validated (deliberately: order is editorial, not behavioral).

### 1.3 Reference opt-out (default-deny)

A documentation-class file may skip body validation by declaring `reference: true` in frontmatter — but only if the file-rule matching its path sets `allow_reference: true`. Unauthorized use (no matching rule, or a rule without the flag) is an **error** naming the authorized patterns. Frontmatter requirements still apply to reference files; token counting still runs.

## 2. Semantic rules

### 2.1 Ambiguous language (on by default)

Inside `<instructions>`, these phrases are **errors** (word-boundary, case-insensitive, verbatim): `maybe`, `might`, `consider`, `optionally`, `try to`, `possibly`, `it would be good to`, `you could`, `perhaps`. Instructions state what to do; hedges push the decision onto the model at run time. Disable per run with `--no-semantic` or per repo via `validation.semantic_check: false`.

### 2.2 Action keywords (opt-in)

With `instructions.enforce_actions: true`, every numbered step (`1. …`) in `<instructions>` must begin with an allowed action keyword (default set: `ROUTE`, `LOAD`, `DELEGATE`, `VERIFY`, `EXECUTE`, `SYNTHESIZE`, `REPORT`, `PARSE`, `CHECK`). Off by default — strict orchestrator prompts opt in.

## 3. Token budget

The whole file is counted with tiktoken's `cl100k_base` encoding (a required dependency — no heuristic fallback, so counts are reproducible everywhere). Defaults: **warning** at ≥ 2000 tokens, **error** at ≥ 4000. A prompt near the fail line is doing a module's job; split it.

## 4. Directives grammar

A `<directives>` block, where a file class permits one, holds routing rules — one per line. Blank lines and `#` comments are skipped; non-directive lines are inert. Each directive must match its grammar:

| Directive | Pattern |
|---|---|
| `DELEGATE` | `^DELEGATE @[\w-]+ WHEN [\w, -]+$` |
| `DEFAULT` | `^DEFAULT @[\w-]+$` |
| `CHAIN` | `^CHAIN [\w-]+: @[\w-]+(\s*(?:->|→)\s*@[\w-]+)+$` (ASCII `->` and `→` both valid) |
| `REQUIRE` | `^REQUIRE (?:"[^"]+"|\S+) ON \w+$` (quoted paths may contain spaces) |

## 5. Scope: file rules and per-repo config

The default config ships inside the `prompt_lang` package; a repo overrides it with `--config <path.yaml>`. Rules are evaluated **first-match-wins** against the file's path, normalized to POSIX form (backslashes → `/`, leading `/` stripped; matching is case-insensitive on Windows, case-sensitive on Unix; `**` has gitignore-style semantics).

Default artifact classes:

| Pattern | Requirements |
|---|---|
| `**/README.md`, `docs/**/*.md` | `allow_reference: true` |
| `**/.agentic/agents/*.md` | requires `<purpose>` + `<instructions>`; **forbids** `<directives>` |
| `**/.agentic/validators/*.md` | requires `<purpose>` + `<instructions>` |
| `**/.agentic/threads/*.md` | requires `<purpose>` + `<instructions>` |
| `**/.claude/commands/*.md` | requires `<purpose>` + `<instructions>`; **forbids** `<directives>` |
| `**/skills/*/SKILL.md` | requires `<purpose>` + `<instructions>` (covers `.claude/skills/…` too — `**/` matches zero or more leading components) |

Per-rule fields: `pattern`, `required_tags`, `forbidden_tags`, `skip_frontmatter`, `skip_required_tags`, `allow_reference`.

## 6. Conformance

A file **conforms** when validation produces zero errors (warnings permitted). CLI contract: pass a file or a directory (directories recurse over `*.md`).

Exit codes: `0` all files pass · `1` validation errors · `2` config error · `3` path not found.

## 7. Versioning

This is spec v1.0, promoted verbatim from the validator's shipped behavior at extraction (the one addition: the `SKILL.md` artifact class in §5). Behavioral changes to the spec or the default config require an ADR in this repo's `decisions/`.
