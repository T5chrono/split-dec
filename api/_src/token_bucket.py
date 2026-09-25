"""The per-process rate limit on the two routes a stranger can reach without a token.

`/api/csp-report` and `/api/unsubscribe` each hold one of these. They used to
hold hand-copied module globals, and the copies had already drifted: the CSP
route said once per episode that it was dropping reports, while the unsubscribe
route refused with a 429 and said nothing at all — so a flood, the one case its
bucket exists for, left no trace in the log.

**A floor, never a ceiling.** This is a serverless function with several warm
instances that cannot see each other's counters, so the effective limit is the
rate times however many instances the platform chose to run. The ceiling is at
the edge: one Vercel Firewall rule per route, described in reports.py and
routers/unsubscribe.py, and invisible to CI.

Mutated without a lock: `take` has no `await` in it, so within one event loop
it runs to completion.
"""

import logging
import time


class TokenBucket:
    def __init__(self, per_minute: int, logger: logging.Logger, notice: str) -> None:
        self.per_minute = per_minute
        self._logger = logger
        self._notice = notice
        self.refill()

    def refill(self, tokens: float | None = None) -> None:
        """Full (or holding `tokens`), and not in a drought.

        For tests: an instance lives at module scope, so without this one test
        emptying it would throttle the next.
        """
        self.tokens = float(self.per_minute if tokens is None else tokens)
        self.last_refill = time.monotonic()
        self.suppressing = False

    def take(self) -> bool:
        """One unit of budget, or `False` if the bucket is empty.

        The first refusal of a drought logs `notice` once, as a WARNING: rate
        limiting is back-pressure, not an alert, and ERROR here is a Sentry
        event (see monitoring.py). Once per drought rather than once per
        refusal, or the thing announcing the flood becomes the flood.
        """
        now = time.monotonic()
        self.tokens = min(
            float(self.per_minute),
            self.tokens + (now - self.last_refill) * (self.per_minute / 60.0),
        )
        self.last_refill = now
        if self.tokens < 1.0:
            if not self.suppressing:
                self.suppressing = True
                self._logger.warning(self._notice)
            return False
        self.tokens -= 1.0
        self.suppressing = False
        return True
