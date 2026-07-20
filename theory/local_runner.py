"""Single-shot no-tool local model runner (openai_compatible; e.g. LM Studio).

stdlib-only. No streaming, retries, auth headers, or tool use. Every test
injects a fake Transport; no live sockets in tests. The smoke CLI
(python -m theory.local_runner) is the only live path and is never invoked
by pytest. The Theory judge is its consumer.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


# Transport: (url, body_bytes_or_None, headers, timeout_s) -> (http_status, body_bytes)
# Raises OSError (or any IOError subclass) for network-level failures.
# Must NOT raise for HTTP-level error statuses (e.g. 500); those are (500, <body>).
Transport = Callable[[str, "bytes | None", "dict[str, str]", float], "tuple[int, bytes]"]


# ── Errors ────────────────────────────────────────────────────────────────────

class LocalBackendError(Exception):
    """Base class for all local-backend errors."""


class LocalBackendUnavailable(LocalBackendError):
    """Server absent, refused connection, DNS failure, or timeout."""


class LocalBackendProtocolError(LocalBackendError):
    """Server responded: non-200 status, malformed JSON, or missing fields."""


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LocalCompletion:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float = 0.0  # always 0.0; local inference has no API cost


# ── Default transport ─────────────────────────────────────────────────────────

def _urllib_transport(
    url: str,
    body: bytes | None,
    headers: dict[str, str],
    timeout_s: float,
) -> tuple[int, bytes]:
    """Default urllib-based transport.

    Converts urllib.error.HTTPError (non-2xx HTTP responses) to (code, body)
    tuples. Lets urllib.error.URLError and plain OSError propagate to the caller
    so the runner can map them to LocalBackendUnavailable.
    """
    method = "POST" if body is not None else "GET"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        # HTTPError is an HTTP response with a non-2xx code — return it, don't raise.
        return exc.code, exc.read()
    # urllib.error.URLError (network failure) and plain OSError propagate to caller.


# ── Runner ────────────────────────────────────────────────────────────────────

class LocalModelRunner:
    """Single-shot no-tool local model runner using the openai_compatible API."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_s: float = 30.0,
        temperature: float = 0.0,
        max_tokens: int = 512,
        transport: Transport | None = None,
    ) -> None:
        """Initialise the runner.

        Args:
            base_url: Base URL of the local backend; trailing '/' is stripped.
            model: Model identifier string passed to the backend.
            timeout_s: Request timeout in seconds.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            transport: Optional injected transport callable. None uses the
                default urllib-based transport (never called in tests).
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._transport: Transport = transport if transport is not None else _urllib_transport

    def complete(self, prompt: str, *, system: str | None = None) -> LocalCompletion:
        """POST one completion request. Never streams. Never retries.

        Messages layout:
            system is not None → [{"role": "system", "content": system},
                                   {"role": "user",   "content": prompt}]
            system is None     → [{"role": "user",   "content": prompt}]

        POST body: {"model": ..., "messages": ..., "temperature": ...,
                    "max_tokens": ..., "stream": false}
        URL: {base_url}/chat/completions
        Headers: {"Content-Type": "application/json"}

        Raises:
            LocalBackendUnavailable: transport raises OSError.
            LocalBackendProtocolError: non-200 status, malformed JSON, or
                missing choices[0].message.content.
        """
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        url = f"{self._base_url}/chat/completions"

        try:
            status, resp_body = self._transport(url, body_bytes, headers, self._timeout_s)
        except OSError as exc:
            raise LocalBackendUnavailable(str(exc)) from exc

        if status != 200:
            snippet = resp_body[:200].decode("utf-8", errors="replace")
            raise LocalBackendProtocolError(f"HTTP {status}: {snippet}")

        try:
            data = json.loads(resp_body)
        except json.JSONDecodeError as exc:
            raise LocalBackendProtocolError(f"malformed JSON: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalBackendProtocolError(
                f"response missing choices[0].message.content: {exc}"
            ) from exc

        # usage fields — optional
        usage = data.get("usage") or {}
        prompt_tokens: int | None = usage.get("prompt_tokens")
        completion_tokens: int | None = usage.get("completion_tokens")
        model_used: str = data.get("model") or self._model

        return LocalCompletion(
            text=content,
            model=model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,
        )

    def is_available(self) -> bool:
        """GET {base_url}/models. Returns True iff HTTP 200 + parseable JSON.

        All failure paths (transport OSError, non-200, JSON parse error) → False.
        Never raises.
        """
        url = f"{self._base_url}/models"
        try:
            status, resp_body = self._transport(url, None, {}, self._timeout_s)
        except OSError:
            return False

        if status != 200:
            return False

        try:
            json.loads(resp_body)
        except json.JSONDecodeError:
            return False

        return True


# ── Smoke CLI ─────────────────────────────────────────────────────────────────

def _main() -> None:
    """Entry point for the smoke CLI.

    Usage:
        python -m theory.local_runner \\
            --prompt TEXT \\
            --model MODEL \\
            [--system TEXT] \\
            [--base-url URL] \\
            [--timeout-s FLOAT] \\
            [--max-tokens INT]
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Single-shot local model runner smoke CLI"
    )
    parser.add_argument("--prompt", required=True, help="User prompt text")
    parser.add_argument("--system", default=None, help="Optional system prompt")
    parser.add_argument(
        "--base-url",
        default="http://localhost:1234/v1",
        help="Base URL of the local backend (default: http://localhost:1234/v1)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model identifier served by the local backend",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum tokens to generate (default: 512)",
    )

    args = parser.parse_args()

    runner = LocalModelRunner(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout_s,
        max_tokens=args.max_tokens,
    )

    try:
        completion = runner.complete(args.prompt, system=args.system)
    except LocalBackendError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(completion.text)
    print(
        f"model={completion.model} "
        f"prompt_tokens={completion.prompt_tokens} "
        f"completion_tokens={completion.completion_tokens}",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    _main()
