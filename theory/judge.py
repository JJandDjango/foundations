"""LLM-judged rationale substance checker.

TheoryJudge asks a local model whether a commit's Theory: rationale actually
explains the change shown in the diff. Warn-only by design: every verdict
(unavailable, does_not_explain, unparseable) degrades to a WARN in check(),
never a FAIL.

All LLM interaction uses LocalModelRunner with an injectable transport so
tests can inject FakeTransport without any live sockets.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Verdict ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JudgeVerdict:
    """Verdict returned by TheoryJudge.evaluate()."""

    status: str  # "explains" | "does_not_explain" | "unavailable" | "unparseable"
    reason: "str | None" = None


# ── Protocol prompt ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a commit-quality judge. Your task is to assess whether a commit's "
    "Theory: rationale actually explains the change shown in the diff.\n\n"
    "Respond with exactly one of:\n"
    "  EXPLAINS <brief reason>\n"
    "  DOES_NOT_EXPLAIN <brief reason>\n\n"
    "The first non-empty line of your response must start with EXPLAINS or "
    "DOES_NOT_EXPLAIN (case-insensitive). The reason after the keyword is "
    "optional but recommended. Keep your response concise."
)

_MAX_REASON_CHARS = 200


# ── Judge ─────────────────────────────────────────────────────────────────────


class TheoryJudge:
    """Single-shot LLM rationale judge using a local model runner."""

    def __init__(self, *, runner: "LocalModelRunner") -> None:  # type: ignore[name-defined]
        self._runner = runner

    @classmethod
    def from_config(cls, cfg: "JudgeConfig") -> "TheoryJudge":  # type: ignore[name-defined]
        """Construct from JudgeConfig, building a LocalModelRunner internally."""
        from theory.local_runner import LocalModelRunner
        from theory.config import JudgeConfig  # noqa: F401 (type ref only)

        runner = LocalModelRunner(
            base_url=cfg.base_url,
            model=cfg.model,
            timeout_s=cfg.timeout_s,
            temperature=0.0,
            max_tokens=128,
        )
        return cls(runner=runner)

    def evaluate(
        self,
        rationale: str,
        changed_files: "list[str]",
        diff: "DiffInfo",  # type: ignore[name-defined]
    ) -> JudgeVerdict:
        """Ask the local model whether the rationale explains the change.

        Never retries. No is_available() preflight.
        LocalBackendUnavailable → unavailable verdict.
        LocalBackendProtocolError → unavailable verdict.
        """
        from theory.local_runner import (
            LocalBackendProtocolError,
            LocalBackendUnavailable,
        )
        from theory.checker import DiffInfo  # noqa: F401 (type ref only)

        files_str = (
            "\n".join(changed_files) if changed_files else "(none)"
        )
        diff_str = (
            diff.diff_text if diff.diff_text is not None else "(not available)"
        )
        user_msg = (
            f"Commit rationale: {rationale}\n\n"
            f"Changed files:\n{files_str}\n\n"
            f"Diff:\n{diff_str}"
        )

        try:
            result = self._runner.complete(user_msg, system=_SYSTEM_PROMPT)
            # LocalModelRunner returns LocalCompletion; FakeRunner may return str
            response_text = result.text if hasattr(result, "text") else str(result)
        except LocalBackendUnavailable as exc:
            return JudgeVerdict("unavailable", str(exc))
        except LocalBackendProtocolError as exc:
            return JudgeVerdict("unavailable", str(exc))
        except OSError as exc:
            # FakeRunner may raise OSError directly (real runner maps OSError to
            # LocalBackendUnavailable internally before raising, but FakeRunner may not)
            return JudgeVerdict("unavailable", str(exc))

        # Parse verdict from first non-empty line
        for raw_line in response_text.splitlines():
            first_line = raw_line.strip()
            if not first_line:
                continue
            upper = first_line.upper()
            if upper.startswith("EXPLAINS"):
                remainder = first_line[len("EXPLAINS"):].strip()
                reason: "str | None" = remainder[:_MAX_REASON_CHARS] if remainder else None
                return JudgeVerdict("explains", reason)
            elif upper.startswith("DOES_NOT_EXPLAIN"):
                remainder = first_line[len("DOES_NOT_EXPLAIN"):].strip()
                reason = remainder[:_MAX_REASON_CHARS] if remainder else None
                return JudgeVerdict("does_not_explain", reason)
            else:
                return JudgeVerdict("unparseable", None)

        # Empty response → unparseable
        return JudgeVerdict("unparseable", None)
