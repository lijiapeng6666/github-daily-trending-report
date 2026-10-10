"""Bounded retries and same-origin redirects; credentials never leave the API."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


def retry_delay(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("Retry-After")
    if value is None:
        return 2**attempt
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError):
            return 2**attempt


def request(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    original = httpx.URL(url)
    for attempt in range(3):
        try:
            target = original
            for _ in range(4):
                response = client.get(target, headers=headers, follow_redirects=False)
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                target = response.url.join(response.headers.get("Location", ""))
                if (target.scheme, target.host, target.port) != (
                    original.scheme,
                    original.host,
                    original.port,
                ):
                    raise ValueError("cross-origin redirect rejected")
            else:
                raise ValueError("too many redirects")
            transient = response.status_code in (429, 500, 502, 503, 504) or (
                response.status_code == 403 and "Retry-After" in response.headers
            )
            if transient and attempt < 2:
                delay = retry_delay(response, attempt)
                if delay <= 30:
                    sleep(delay)
                    continue
            response.raise_for_status()
            return response
        except httpx.TransportError:
            if attempt == 2:
                raise
            sleep(2**attempt)
    raise RuntimeError("HTTP retry exhausted")
