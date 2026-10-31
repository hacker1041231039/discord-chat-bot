"""
Rate limiting utilities for the Discord bot.
Implements per-user rate limiting to prevent abuse.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict

from loguru import logger

from config import settings


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    tokens: float = field(default_factory=lambda: float(settings.rate_limit_per_user))
    last_update: float = field(default_factory=time.time)

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limited
        """
        now = time.time()
        # Refill tokens based on time passed (tokens per minute)
        elapsed = now - self.last_update
        refill_rate = settings.rate_limit_per_user / 60.0  # tokens per second
        self.tokens = min(settings.rate_limit_per_user, self.tokens + elapsed * refill_rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def reset(self) -> None:
        """Reset the bucket to full."""
        self.tokens = float(settings.rate_limit_per_user)
        self.last_update = time.time()


class RateLimiter:
    """Per-user rate limiter using token bucket algorithm."""

    def __init__(self) -> None:
        self.buckets: Dict[int, RateLimitBucket] = defaultdict(RateLimitBucket)
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def is_allowed(self, user_id: int, tokens: int = 1) -> bool:
        """
        Check if a user is allowed to make a request.

        Args:
            user_id: Discord user ID
            tokens: Number of tokens to consume

        Returns:
            True if allowed, False if rate limited
        """
        self._maybe_cleanup()
        bucket = self.buckets[user_id]
        return bucket.consume(tokens)

    def get_remaining(self, user_id: int) -> int:
        """Get remaining tokens for a user."""
        bucket = self.buckets[user_id]
        now = time.time()
        elapsed = now - bucket.last_update
        refill_rate = settings.rate_limit_per_user / 60.0
        current_tokens = min(settings.rate_limit_per_user, bucket.tokens + elapsed * refill_rate)
        return int(current_tokens)

    def get_retry_after(self, user_id: int) -> float:
        """Get seconds until next token available."""
        bucket = self.buckets[user_id]
        now = time.time()
        elapsed = now - bucket.last_update
        refill_rate = settings.rate_limit_per_user / 60.0
        current_tokens = min(settings.rate_limit_per_user, bucket.tokens + elapsed * refill_rate)

        if current_tokens >= 1:
            return 0.0

        # Time needed for 1 token
        return (1 - current_tokens) / refill_rate

    def reset_user(self, user_id: int) -> None:
        """Reset rate limit for a specific user."""
        if user_id in self.buckets:
            self.buckets[user_id].reset()

    def _maybe_cleanup(self) -> None:
        """Clean up old buckets periodically."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            # Remove buckets that haven't been used in 10 minutes
            cutoff = now - 600
            to_remove = [
                uid for uid, bucket in self.buckets.items()
                if bucket.last_update < cutoff
            ]
            for uid in to_remove:
                del self.buckets[uid]
            self._last_cleanup = now
            if to_remove:
                logger.debug(f"Cleaned up {len(to_remove)} rate limit buckets")


# Global rate limiter instance
rate_limiter = RateLimiter()