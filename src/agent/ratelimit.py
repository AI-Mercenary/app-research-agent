"""Client-side token-budget rate limiter for Groq's per-model quotas.

Groq's free tier enforces tokens-per-minute (TPM) and tokens-per-day (TPD), and
measurement showed both are scoped **per model**, while keys on the same
organisation share them: with one model's remaining TPM down to 1243, two other
models still reported ~7984. So a second API key on the same org buys nothing,
but spreading work across models multiplies available throughput.

Hence one limiter instance per model (see `get_limiter`), and callers pick the
model with the most free capacity instead of queueing on a saturated one.

Algorithm: a rolling-window token bucket.
  - Keep a deque of (timestamp, tokens_charged) for the last WINDOW seconds.
  - Before a call, evict entries older than the window, then check whether
    `used + estimate` fits under the effective budget. If not, sleep exactly
    until the oldest entry expires (the earliest moment capacity frees up)
    and re-check.
  - After a call, replace the reserved estimate with the provider-reported
    actual usage, so the window self-corrects instead of drifting.

This is O(1) amortised per call and never sleeps longer than necessary, which
matters because the alternative (blind exponential backoff) either wastes
minutes or retries straight back into an exhausted window.
"""
from __future__ import annotations

import threading
import time
from collections import deque

WINDOW_SECONDS = 60.0


class TokenRateLimiter:
    def __init__(self, tokens_per_minute: int = 8000, safety_margin: float = 0.85):
        self.budget = int(tokens_per_minute * safety_margin)
        self._events: deque[list[float]] = deque()
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "waits": 0, "total_wait_s": 0.0, "tokens": 0}

    def _evict(self, now: float) -> None:
        while self._events and now - self._events[0][0] > WINDOW_SECONDS:
            self._events.popleft()

    def _used(self) -> int:
        return int(sum(e[1] for e in self._events))

    def acquire(self, estimated_tokens: int) -> list[float]:
        """Block until `estimated_tokens` fit in the rolling window. Returns the
        reservation, which the caller should settle via `settle()`."""
        while True:
            with self._lock:
                now = time.monotonic()
                self._evict(now)
                if self._used() + estimated_tokens <= self.budget or not self._events:
                    reservation = [now, float(estimated_tokens)]
                    self._events.append(reservation)
                    self.stats["calls"] += 1
                    return reservation
                sleep_for = WINDOW_SECONDS - (now - self._events[0][0]) + 0.25
            # Re-check often rather than sleeping the whole way to the oldest
            # entry's expiry: reservations are estimates, and `settle()` usually
            # frees capacity back (actual usage runs ~25% under estimate). A
            # thread that sleeps the full window would miss that and idle while
            # budget sits unused.
            nap = min(max(sleep_for, 0.25), 2.0)
            self.stats["waits"] += 1
            self.stats["total_wait_s"] += nap
            time.sleep(nap)

    def settle(self, reservation: list[float], actual_tokens: int | None) -> None:
        """Replace the reserved estimate with the provider's reported usage."""
        if actual_tokens is None:
            return
        with self._lock:
            reservation[1] = float(actual_tokens)
            self.stats["tokens"] += int(actual_tokens)

    def observe_headers(self, headers) -> None:
        """Adopt the provider's own view of the limit when it tells us."""
        try:
            limit = headers.get("x-ratelimit-limit-tokens")
            if limit:
                observed = int(int(limit) * 0.85)
                if observed != self.budget:
                    self.budget = observed
        except (TypeError, ValueError):
            pass

    def penalise(self, seconds: float) -> None:
        """After a 429, charge the whole window so nothing else fires until it clears."""
        with self._lock:
            self._events.append([time.monotonic() + max(seconds - WINDOW_SECONDS, 0), float(self.budget)])


    def free_capacity(self) -> int:
        """Tokens available right now, without blocking. Used to pick the
        least-loaded model rather than queueing on an arbitrary one."""
        with self._lock:
            self._evict(time.monotonic())
            return max(self.budget - self._used(), 0)


# Both TPM and TPD are enforced PER MODEL, so each model needs its own window.
# (Measured: with one model's remaining budget down to 1243, two others still
# reported ~7984 — so a single global limiter serialises the whole run onto one
# model's quota while the rest sit idle.)
_limiters: dict[str, TokenRateLimiter] = {}
_registry_lock = threading.Lock()


def get_limiter(model: str) -> TokenRateLimiter:
    with _registry_lock:
        if model not in _limiters:
            _limiters[model] = TokenRateLimiter()
        return _limiters[model]


def all_stats() -> dict[str, dict]:
    return {m: dict(l.stats) for m, l in _limiters.items()}


def estimate_tokens(text: str) -> int:
    """Calibrated against observed usage: a 5392-char prompt cost 1750 total
    tokens including the tool-call reply, i.e. ~3.1 chars/token end to end.
    Estimating too high wastes budget (threads queue for capacity that is never
    used); too low invites 429s, which cost far more than a short wait."""
    return int(len(text) / 3.9) + 450
