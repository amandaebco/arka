"""Retrying the failures that are worth retrying — and only those.

Publication runs on a budget of three correction rounds. That budget exists to
stop the designer from redrawing forever, and it is spent on real defects: text
the finding does not authorise, a page with two focal points. A round lost to a
provider answering HTTP 520, or to a connection dropped mid-read, buys nothing —
it consumes the budget without ever examining the page.

So transient failures are absorbed here, below the loop, and never reach it. The
`LoopAgent` counts iterations itself; we do not hold that counter and must not
pretend to. What we can do is not hand it a round that carries no information.

What this must never do is turn a failure into a success. A call that still fails
after its retries raises exactly as before, and the caller still reports GAGAL
PERIKSA. Retrying widens the window for a call to succeed; it does not lower the
bar for what counts as one.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Failure types that describe the transport or the provider's own health rather
# than anything about the request. Matched by name because they arrive from three
# different libraries — the OpenAI client, google-genai, and httpx underneath both
# — and importing all three here to catch them by class would tie this module to
# every provider ARKA might use.
TRANSIENT_NAMES = frozenset(
    {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "ServiceUnavailable",
        "ServerError",
        "Unavailable",
        "ResourceExhausted",
        "DeadlineExceeded",
        "RemoteProtocolError",
        "ReadTimeout",
        "WriteTimeout",
        "ConnectTimeout",
        "ConnectError",
        "ReadError",
        "PoolTimeout",
    }
)

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524})


# A rate limit clears on its own; an exhausted quota does not. Both arrive as
# RateLimitError with status 429, so the type alone cannot tell them apart, and
# retrying the second one waits out three backoffs to be told the same thing.
PERMANENT_MARKERS = ("insufficient_quota", "credit_balance_exhausted", "billing")


def is_transient(exc: BaseException) -> bool:
    """Whether the failure is about reaching the provider, not about the request.

    A wrong prompt fails the same way every time; retrying it only spends money.
    """
    if any(m in str(exc) for m in PERMANENT_MARKERS):
        return False

    if type(exc).__name__ in TRANSIENT_NAMES:
        return True

    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return isinstance(status, int) and status in RETRYABLE_STATUS


def with_retry[T](
    call: Callable[[], T],
    *,
    what: str,
    attempts: int = 3,
    delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `call`, retrying only transient failures, with a widening pause.

    `sleep` is injected so tests can exercise the retry path without spending the
    wall-clock time the pauses would otherwise cost.
    """
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — re-raised unless transient
            if not is_transient(exc) or attempt == attempts:
                raise
            pause = delay * attempt
            logger.warning(
                "%s gagal sementara (%s: %s); mencoba lagi %d/%d dalam %.1f detik",
                what, type(exc).__name__, exc, attempt + 1, attempts, pause,
            )
            sleep(pause)

    raise AssertionError(f"tak terjangkau: {what} habis percobaan tanpa hasil")
