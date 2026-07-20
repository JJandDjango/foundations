"""Unit tests for theory.local_runner.

All tests use injected FakeTransport — no live sockets, no LM Studio,
no Anthropic SDK.
"""

from __future__ import annotations

import json

import pytest

from theory.local_runner import (
    LocalBackendError,
    LocalBackendProtocolError,
    LocalBackendUnavailable,
    LocalCompletion,
    LocalModelRunner,
)


# ── FakeTransport helper ──────────────────────────────────────────────────────

class FakeTransport:
    """Callable fake that records calls and returns a pre-configured response."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        raise_oserror: str | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.raise_oserror = raise_oserror
        self.calls: list[tuple[str, bytes | None, dict[str, str], float]] = []

    def __call__(
        self,
        url: str,
        body: bytes | None,
        headers: dict[str, str],
        timeout_s: float,
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers, timeout_s))
        if self.raise_oserror is not None:
            raise OSError(self.raise_oserror)
        return self.status, self.body


def _make_ok_response(
    text: str = "Hello!",
    model: str = "gemma-4b",
    prompt_tokens: int | None = 5,
    completion_tokens: int | None = 10,
    include_usage: bool = True,
) -> bytes:
    """Build a minimal valid chat/completions response."""
    resp: dict = {
        "model": model,
        "choices": [
            {"message": {"role": "assistant", "content": text}}
        ],
    }
    if include_usage and (prompt_tokens is not None or completion_tokens is not None):
        resp["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    return json.dumps(resp).encode("utf-8")


def _make_runner(transport: FakeTransport, base_url: str = "http://localhost:1234/v1") -> LocalModelRunner:
    return LocalModelRunner(
        base_url=base_url,
        model="gemma-4b",
        transport=transport,
    )


# ── TestLocalModelRunnerComplete ──────────────────────────────────────────────

class TestLocalModelRunnerComplete:
    def test_happy_path(self):
        transport = FakeTransport(200, _make_ok_response(text="Hello!"))
        runner = _make_runner(transport)
        result = runner.complete("hi")
        assert isinstance(result, LocalCompletion)
        assert result.text == "Hello!"
        assert result.cost_usd == 0.0

    def test_system_message_included_in_body(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = _make_runner(transport)
        runner.complete("hi", system="be helpful")
        assert len(transport.calls) == 1
        url, body_bytes, headers, _ = transport.calls[0]
        assert body_bytes is not None
        payload = json.loads(body_bytes)
        messages = payload["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "be helpful"}
        assert messages[1]["role"] == "user"

    def test_no_system_omits_system_turn(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = _make_runner(transport)
        runner.complete("hi")
        payload = json.loads(transport.calls[0][1])
        messages = payload["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_cost_usd_always_zero(self):
        transport = FakeTransport(
            200,
            _make_ok_response(prompt_tokens=9999, completion_tokens=9999),
        )
        runner = _make_runner(transport)
        result = runner.complete("hi")
        assert result.cost_usd == 0.0

    def test_token_counts_from_usage(self):
        transport = FakeTransport(200, _make_ok_response(prompt_tokens=5, completion_tokens=10))
        runner = _make_runner(transport)
        result = runner.complete("hi")
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 10

    def test_absent_usage_gives_none_tokens(self):
        transport = FakeTransport(200, _make_ok_response(include_usage=False))
        runner = _make_runner(transport)
        result = runner.complete("hi")
        assert result.prompt_tokens is None
        assert result.completion_tokens is None

    def test_oserror_raises_unavailable(self):
        transport = FakeTransport(raise_oserror="connection refused")
        runner = _make_runner(transport)
        with pytest.raises(LocalBackendUnavailable):
            runner.complete("hi")

    def test_http_500_raises_protocol_error(self):
        transport = FakeTransport(500, b"Internal Server Error")
        runner = _make_runner(transport)
        with pytest.raises(LocalBackendProtocolError):
            runner.complete("hi")

    def test_malformed_json_raises_protocol_error(self):
        transport = FakeTransport(200, b"not-json")
        runner = _make_runner(transport)
        with pytest.raises(LocalBackendProtocolError):
            runner.complete("hi")

    def test_missing_choices_raises_protocol_error(self):
        transport = FakeTransport(200, b"{}")
        runner = _make_runner(transport)
        with pytest.raises(LocalBackendProtocolError):
            runner.complete("hi")

    def test_empty_text_is_valid(self):
        transport = FakeTransport(200, _make_ok_response(text=""))
        runner = _make_runner(transport)
        result = runner.complete("hi")
        assert result.text == ""

    def test_post_url_is_chat_completions(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = _make_runner(transport, base_url="http://localhost:1234/v1")
        runner.complete("hi")
        url = transport.calls[0][0]
        assert url == "http://localhost:1234/v1/chat/completions"

    def test_content_type_header(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = _make_runner(transport)
        runner.complete("hi")
        headers = transport.calls[0][2]
        assert headers.get("Content-Type") == "application/json"


# ── TestLocalModelRunnerIsAvailable ──────────────────────────────────────────

class TestLocalModelRunnerIsAvailable:
    def test_available_on_200_json(self):
        transport = FakeTransport(200, b'{"object":"list"}')
        runner = _make_runner(transport)
        assert runner.is_available() is True

    def test_unavailable_on_503(self):
        transport = FakeTransport(503, b"")
        runner = _make_runner(transport)
        assert runner.is_available() is False

    def test_unavailable_on_oserror(self):
        transport = FakeTransport(raise_oserror="connection refused")
        runner = _make_runner(transport)
        # Must not raise
        result = runner.is_available()
        assert result is False

    def test_unavailable_on_malformed_json(self):
        transport = FakeTransport(200, b"bad")
        runner = _make_runner(transport)
        assert runner.is_available() is False

    def test_get_url_is_models(self):
        transport = FakeTransport(200, b'{"object":"list"}')
        runner = _make_runner(transport, base_url="http://localhost:1234/v1")
        runner.is_available()
        url = transport.calls[0][0]
        assert url == "http://localhost:1234/v1/models"


# ── TestLocalModelRunnerBaseUrlNormalization ──────────────────────────────────

class TestLocalModelRunnerBaseUrlNormalization:
    def test_trailing_slash_stripped(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = LocalModelRunner(
            base_url="http://localhost:1234/v1/",
            model="gemma-4b",
            transport=transport,
        )
        runner.complete("hi")
        url = transport.calls[0][0]
        assert url == "http://localhost:1234/v1/chat/completions"

    def test_no_trailing_slash_unchanged(self):
        transport = FakeTransport(200, _make_ok_response())
        runner = LocalModelRunner(
            base_url="http://localhost:1234/v1",
            model="gemma-4b",
            transport=transport,
        )
        runner.complete("hi")
        url = transport.calls[0][0]
        assert url == "http://localhost:1234/v1/chat/completions"


# ── TestLocalBackendErrors ────────────────────────────────────────────────────

class TestLocalBackendErrors:
    def test_unavailable_is_subclass_of_backend_error(self):
        assert issubclass(LocalBackendUnavailable, LocalBackendError)

    def test_protocol_error_is_subclass_of_backend_error(self):
        assert issubclass(LocalBackendProtocolError, LocalBackendError)

    def test_backend_error_is_exception(self):
        assert issubclass(LocalBackendError, Exception)
