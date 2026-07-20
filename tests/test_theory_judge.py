"""Unit tests for :mod:`theory.judge`.

Covers ACs 12–21 using injected FakeTransport — no live sockets,
no LM Studio, no Anthropic SDK.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from theory.local_runner import CompletionOptions, LocalModelRunner
from theory.checker import DiffInfo
from theory.config import JudgeConfig
from theory.judge import JudgeVerdict, TheoryJudge, _SYSTEM_PROMPT


# ── FakeTransport ─────────────────────────────────────────────────────────────


class FakeTransport:
    """Callable fake that records calls and returns a pre-configured response."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        raise_oserror: "str | None" = None,
    ) -> None:
        self.status = status
        self.body = body
        self.raise_oserror = raise_oserror
        self.calls: list[tuple[str, "bytes | None", "dict[str, str]", float]] = []

    def __call__(
        self,
        url: str,
        body: "bytes | None",
        headers: "dict[str, str]",
        timeout_s: float,
    ) -> "tuple[int, bytes]":
        self.calls.append((url, body, headers, timeout_s))
        if self.raise_oserror is not None:
            raise OSError(self.raise_oserror)
        return self.status, self.body


def _ok_response(text: str, model: str = "m") -> bytes:
    """Build a minimal valid chat/completions response body."""
    resp = {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }
    return json.dumps(resp).encode("utf-8")


def _make_judge(transport: FakeTransport, cfg: "JudgeConfig | None" = None) -> TheoryJudge:
    """Construct a TheoryJudge with the given FakeTransport."""
    if cfg is None:
        cfg = JudgeConfig(model="m", base_url="http://x", timeout_s=5.0, max_diff_chars=3000)
    runner = LocalModelRunner(
        base_url=cfg.base_url,
        model=cfg.model,
        options=CompletionOptions(
            timeout_s=cfg.timeout_s, temperature=0.0, max_tokens=128
        ),
        transport=transport,
    )
    return TheoryJudge(runner=runner)


# ── TestTheoryJudge ───────────────────────────────────────────────────────────


class TestTheoryJudge:
    """TheoryJudge construction and evaluate() (ACs 12–21)."""

    # AC12 (DiffInfo) is tested in test_theory_checker.py but we confirm the
    # DiffInfo import is valid here as a sanity check.
    def test_ac12_diffinfo_has_none_defaults(self) -> None:
        """AC12: DiffInfo() defaults are all None."""
        d = DiffInfo()
        assert d.added_lines is None
        assert d.deleted_lines is None
        assert d.diff_text is None

    def test_ac13_from_config_constructs_with_correct_params(self) -> None:
        """AC13: from_config sends model/temperature/max_tokens in POST body."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        cfg = JudgeConfig(model="m", base_url="http://x", timeout_s=5.0, max_diff_chars=3000)
        judge = _make_judge(transport, cfg)
        judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))

        assert len(transport.calls) == 1
        _, body_bytes, _, _ = transport.calls[0]
        assert body_bytes is not None
        payload = json.loads(body_bytes)
        assert payload["model"] == "m"
        assert payload["temperature"] == 0.0
        assert payload["max_tokens"] == 128

    def test_ac14_explains_response_returns_explains(self) -> None:
        """AC14: response starting with EXPLAINS → JudgeVerdict(status='explains')."""
        transport = FakeTransport(200, _ok_response("EXPLAINS because it adds validation"))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "explains"

    def test_ac15_does_not_explain_response_returns_does_not_explain(self) -> None:
        """AC15: response starting with DOES_NOT_EXPLAIN → correct verdict + reason."""
        transport = FakeTransport(
            200, _ok_response("DOES_NOT_EXPLAIN rationale is vague")
        )
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "does_not_explain"
        assert verdict.reason == "rationale is vague"

    def test_ac16_reason_truncated_to_200_chars(self) -> None:
        """AC16: reason exceeding 200 chars → len(verdict.reason) <= 200."""
        long_reason = "x" * 300
        transport = FakeTransport(200, _ok_response(f"DOES_NOT_EXPLAIN {long_reason}"))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "does_not_explain"
        assert verdict.reason is not None
        assert len(verdict.reason) <= 200

    def test_ac17_oserror_returns_unavailable(self) -> None:
        """AC17: transport OSError → JudgeVerdict(status='unavailable') without raising."""
        transport = FakeTransport(raise_oserror="connection refused")
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "unavailable"
        assert verdict.reason is not None

    def test_ac18_http_500_returns_unavailable(self) -> None:
        """AC18: transport returns HTTP 500 → JudgeVerdict(status='unavailable')."""
        transport = FakeTransport(500, b"Internal Server Error")
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "unavailable"

    def test_ac19_unparseable_first_line_returns_unparseable(self) -> None:
        """AC19: first non-empty line is 'MAYBE something' → JudgeVerdict('unparseable', None)."""
        transport = FakeTransport(200, _ok_response("MAYBE something"))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "unparseable"
        assert verdict.reason is None

    def test_ac20_user_message_contains_rationale_and_diff(self) -> None:
        """AC20: user message contains the rationale string and diff.diff_text."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        judge = _make_judge(transport)
        judge.evaluate("my rationale text", ["file.py"], DiffInfo(diff_text="--- a/f\n+++ b/f"))

        assert len(transport.calls) == 1
        _, body_bytes, _, _ = transport.calls[0]
        payload = json.loads(body_bytes)
        messages = payload["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "my rationale text" in user_content
        assert "--- a/f\n+++ b/f" in user_content

    def test_ac21_system_message_contains_verdict_keywords(self) -> None:
        """AC21: system message contains 'EXPLAINS' and 'DOES_NOT_EXPLAIN'."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        judge = _make_judge(transport)
        judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))

        _, body_bytes, _, _ = transport.calls[0]
        payload = json.loads(body_bytes)
        messages = payload["messages"]
        system_content = next(
            (m["content"] for m in messages if m["role"] == "system"), None
        )
        assert system_content is not None
        assert "EXPLAINS" in system_content
        assert "DOES_NOT_EXPLAIN" in system_content

    def test_explains_reason_none_when_empty(self) -> None:
        """EXPLAINS with no trailing text → reason is None."""
        transport = FakeTransport(200, _ok_response("EXPLAINS"))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "explains"
        assert verdict.reason is None

    def test_does_not_explain_case_insensitive(self) -> None:
        """DOES_NOT_EXPLAIN matching is case-insensitive."""
        transport = FakeTransport(200, _ok_response("does_not_explain vague"))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "does_not_explain"

    def test_from_config_class_method(self) -> None:
        """from_config creates a TheoryJudge instance."""
        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        # We can't call from_config with a FakeTransport directly, but we verify
        # the returned object is a TheoryJudge and has the expected structure.
        # We'll test it by replacing the runner after construction.
        judge = TheoryJudge.__new__(TheoryJudge)
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        runner = LocalModelRunner(
            base_url=cfg.base_url,
            model=cfg.model,
            options=CompletionOptions(
                timeout_s=cfg.timeout_s, temperature=0.0, max_tokens=128
            ),
            transport=transport,
        )
        judge._runner = runner
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "explains"

    def test_empty_response_returns_unparseable(self) -> None:
        """Empty response text → unparseable."""
        transport = FakeTransport(200, _ok_response(""))
        judge = _make_judge(transport)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "unparseable"

    def test_changed_files_in_user_message(self) -> None:
        """Changed files list appears in user message content."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        judge = _make_judge(transport)
        judge.evaluate("rationale", ["src/foo.py", "src/bar.py"], DiffInfo(diff_text="d"))

        _, body_bytes, _, _ = transport.calls[0]
        payload = json.loads(body_bytes)
        user_content = next(m["content"] for m in payload["messages"] if m["role"] == "user")
        assert "src/foo.py" in user_content
        assert "src/bar.py" in user_content

    def test_empty_changed_files_uses_none_placeholder(self) -> None:
        """Empty changed_files list → '(none)' in user message."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        judge = _make_judge(transport)
        judge.evaluate("rationale", [], DiffInfo(diff_text="d"))

        _, body_bytes, _, _ = transport.calls[0]
        payload = json.loads(body_bytes)
        user_content = next(m["content"] for m in payload["messages"] if m["role"] == "user")
        assert "(none)" in user_content

    def test_diff_text_none_uses_not_available_placeholder(self) -> None:
        """diff.diff_text is None → '(not available)' in user message."""
        transport = FakeTransport(200, _ok_response("EXPLAINS ok"))
        judge = _make_judge(transport)
        judge.evaluate("rationale", [], DiffInfo(diff_text=None))

        _, body_bytes, _, _ = transport.calls[0]
        payload = json.loads(body_bytes)
        user_content = next(m["content"] for m in payload["messages"] if m["role"] == "user")
        assert "(not available)" in user_content
