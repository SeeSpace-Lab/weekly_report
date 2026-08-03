from __future__ import annotations

import time
import urllib.error
from typing import Callable


def fetch_with_retry(
    fetcher: Callable[[str, dict[str, str], float], bytes],
    url: str,
    headers: dict[str, str],
    timeout: float,
    *,
    max_retries: int = 2,
    backoff_seconds: float = 2,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    """Retry transient HTTP, DNS, TLS and timeout failures with backoff."""
    retries = max(0, max_retries)
    for attempt in range(retries + 1):
        try:
            return fetcher(url, headers, timeout)
        except urllib.error.HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504}:
                raise
            if attempt >= retries:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = float(retry_after) if retry_after else backoff_seconds * (2**attempt)
            except ValueError:
                delay = backoff_seconds * (2**attempt)
            sleeper(max(0.0, delay))
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            sleeper(max(0.0, backoff_seconds * (2**attempt)))
    raise RuntimeError("unreachable retry loop")
