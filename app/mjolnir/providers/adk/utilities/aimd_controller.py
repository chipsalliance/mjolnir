# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Optional
from utilities.logger import logger

DEFAULT_INITIAL_CONCURRENCY = 4.0
CONCURRENCY_INCREMENT = 0.25
CONCURRENCY_DECREASE_FACTOR = 0.5
MIN_CONCURRENCY_LIMIT = 1.0


class AIMDConcurrencyController:
    """Additive Increase / Multiplicative Decrease (AIMD) Concurrency Controller.

    Shrinks active connections automatically when Vertex quotas hit.
    """

    def __init__(self, initial_limit: float = DEFAULT_INITIAL_CONCURRENCY):
        self.current_limit = initial_limit
        self.active_requests = 0
        self._cond: Optional[asyncio.Condition] = None

    @property
    def cond(self) -> asyncio.Condition:
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    async def acquire(self, max_concurrency: float):
        async with self.cond:
            effective_limit = min(max_concurrency, self.current_limit)
            while self.active_requests >= int(effective_limit):
                await self.cond.wait()
            self.active_requests += 1

    async def release(self, is_quota_hit: bool, max_concurrency: float):
        async with self.cond:
            self.active_requests -= 1

            if not is_quota_hit:
                # Additive Increase (slow, careful growth to probe capacity)
                if self.current_limit < max_concurrency:
                    self.current_limit = min(
                        max_concurrency, self.current_limit + CONCURRENCY_INCREMENT
                    )
            else:
                # Multiplicative Decrease (rapid shrinking on quota rejection)
                new_limit = max(
                    MIN_CONCURRENCY_LIMIT,
                    self.current_limit * CONCURRENCY_DECREASE_FACTOR,
                )
                if int(new_limit) < int(self.current_limit):
                    logger.write(
                        f"AIMD Controller: Fast-shrinking concurrency from {int(self.current_limit)} down to {int(new_limit)} due to 429 constraint.",
                        stdout=True,
                    )
                self.current_limit = new_limit

            self.cond.notify_all()
