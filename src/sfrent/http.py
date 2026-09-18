"""Shared HTTP client: polite delay, retry with backoff, and a hard stop on 403.

Every collector goes through ``Http`` so rate limiting and error handling live in one
place. A 403 raises ``Blocked`` immediately (never retried): the Craigslist plan requires
halting on the first block, and for APIs it means a bad key, which retrying will not fix.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping

import httpx

from sfrent.config import USER_AGENT

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class Blocked(RuntimeError):
    """The server refused us (HTTP 403). Callers must stop, not retry."""


class Http:
    def __init__(
        self,
        *,
        min_delay_s: float = 0.0,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        headers: Mapping[str, str] | None = None,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.min_delay_s = min_delay_s
        self.max_retries = max_retries
        self._last_request_at = 0.0
        base_headers = {"User-Agent": user_agent, "Accept": "application/json, text/html"}
        if headers:
            base_headers.update(headers)
        self._client = httpx.Client(timeout=timeout_s, headers=base_headers, follow_redirects=True)
        self.requests_made = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Http:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _wait_politely(self) -> None:
        if self.min_delay_s <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_delay_s:
            time.sleep(self.min_delay_s - elapsed)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        attempt = 0
        while True:
            self._wait_politely()
            self._last_request_at = time.monotonic()
            try:
                response = self._client.get(url, params=params, headers=headers)
                self.requests_made += 1
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise
                attempt += 1
                self._backoff(attempt, reason=f"transport error {exc!r}")
                continue

            if response.status_code == 403:
                raise Blocked(f"403 Forbidden from {url}")
            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                attempt += 1
                self._backoff(
                    attempt,
                    reason=f"HTTP {response.status_code}",
                    retry_after=response.headers.get("Retry-After"),
                )
                continue
            response.raise_for_status()
            return response

    @staticmethod
    def _backoff(attempt: int, *, reason: str, retry_after: str | None = None) -> None:
        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0**attempt
        log.warning("retry %d after %.1fs (%s)", attempt, delay, reason)
        time.sleep(delay)
