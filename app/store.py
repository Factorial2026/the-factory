"""
Persistent / in-memory store for:
  - verified payment signatures (dedup, replay protection)
  - rolling 30-day earnings (for the ethical cap)
  - bulk tokens (pre-paid packs)
  - subscription tokens (monthly prepay)
  - LLM response cache (cut cost & latency for identical queries)

If UPSTASH_REDIS_REST_URL is set, uses Upstash Redis REST (free tier, no card).
Otherwise falls back to in-memory (resets on cold start).
"""
import asyncio
import json
import logging
import time
from typing import Any, Optional

import httpx

from .config import settings

log = logging.getLogger("the_factory.store")


# ============================================================================
# IN-MEMORY STORE (fallback)
# ============================================================================

class InMemoryStore:
    """Fallback store. Loses state on restart."""

    def __init__(self):
        self._seen_sigs: dict[str, float] = {}
        self._earnings: list[tuple[float, float]] = []
        self._bulk_tokens: dict[str, dict] = {}       # token -> {remaining, created_at}
        self._sub_tokens: dict[str, dict] = {}         # token -> {remaining, expires_at}
        self._cache: dict[str, tuple[float, Any]] = {} # key -> (expires_at, value)
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        log.warning("Using InMemoryStore. State resets on cold-start. "
                    "Set UPSTASH_REDIS_REST_URL/TOKEN for persistence.")

    async def close(self) -> None:
        pass

    # ---- signature dedup ----
    async def is_signature_seen(self, sig: str) -> bool:
        async with self._lock:
            return sig in self._seen_sigs

    async def mark_signature(self, sig: str, ttl: int = 3600) -> None:
        async with self._lock:
            self._seen_sigs[sig] = time.time()
            cutoff = time.time() - ttl
            self._seen_sigs = {k: v for k, v in self._seen_sigs.items() if v > cutoff}

    # ---- earnings (cap) ----
    async def add_earning(self, usd: float) -> None:
        async with self._lock:
            self._earnings.append((time.time(), usd))
            cutoff = time.time() - 30 * 86400
            self._earnings = [(t, a) for t, a in self._earnings if t > cutoff]

    async def get_earnings_30d(self) -> float:
        async with self._lock:
            cutoff = time.time() - 30 * 86400
            return sum(a for t, a in self._earnings if t > cutoff)

    # ---- bulk tokens ----
    async def create_bulk_token(self, calls: int, ttl: int) -> str:
        import secrets
        token = "bulk_" + secrets.token_urlsafe(24)
        async with self._lock:
            self._bulk_tokens[token] = {"remaining": calls, "created_at": time.time()}
        return token

    async def consume_bulk_token(self, token: str) -> bool:
        async with self._lock:
            t = self._bulk_tokens.get(token)
            if not t or t["remaining"] <= 0:
                return False
            t["remaining"] -= 1
            return True

    async def bulk_token_remaining(self, token: str) -> int:
        async with self._lock:
            t = self._bulk_tokens.get(token)
            return t["remaining"] if t else 0

    # ---- subscription tokens ----
    async def create_subscription_token(self, quota: int, ttl: int) -> str:
        import secrets
        token = "sub_" + secrets.token_urlsafe(24)
        async with self._lock:
            self._sub_tokens[token] = {
                "remaining": quota,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
            }
        return token

    async def consume_subscription_token(self, token: str) -> bool:
        async with self._lock:
            t = self._sub_tokens.get(token)
            if not t:
                return False
            if time.time() > t["expires_at"]:
                return False
            if t["remaining"] <= 0:
                return False
            t["remaining"] -= 1
            return True

    async def subscription_token_remaining(self, token: str) -> int:
        async with self._lock:
            t = self._sub_tokens.get(token)
            if not t or time.time() > t["expires_at"]:
                return 0
            return t["remaining"]

    # ---- response cache ----
    async def cache_get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                self._cache.pop(key, None)
                return None
            return value

    async def cache_set(self, key: str, value: Any, ttl: int) -> None:
        async with self._lock:
            self._cache[key] = (time.time() + ttl, value)
            # eviction: lazy
            now = time.time()
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}


# ============================================================================
# UPSTASH STORE (production)
# ============================================================================

class UpstashStore:
    """Production store using Upstash Redis REST API (free tier, no card)."""

    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def init(self) -> None:
        self._client = httpx.AsyncClient(timeout=10)
        log.info("UpstashStore connected to %s", self._url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def _cmd(self, *args: Any) -> Any:
        if not self._client:
            await self.init()
        assert self._client is not None
        try:
            r = await self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                json=args,
            )
            r.raise_for_status()
            return r.json().get("result")
        except Exception as e:
            log.error("Upstash command failed (%s): %s", args[0], e)
            return None

    # ---- signature dedup ----
    async def is_signature_seen(self, sig: str) -> bool:
        v = await self._cmd("GET", f"sig:{sig}")
        return v is not None and v != "0"

    async def mark_signature(self, sig: str, ttl: int = 3600) -> None:
        await self._cmd("SET", f"sig:{sig}", "1", "EX", str(ttl))

    # ---- earnings (cap) ----
    async def add_earning(self, usd: float) -> None:
        now = time.time()
        await self._cmd("ZADD", "earnings", str(now), f"{now}:{usd}")
        cutoff = now - 30 * 86400
        await self._cmd("ZREMRANGEBYSCORE", "earnings", "-inf", str(cutoff))

    async def get_earnings_30d(self) -> float:
        now = time.time()
        cutoff = now - 30 * 86400
        items = await self._cmd("ZRANGE", "earnings", str(cutoff), str(now), "BYSCORE")
        if not items:
            return 0.0
        total = 0.0
        for item in items:
            try:
                _, usd = item.split(":")
                total += float(usd)
            except Exception:
                pass
        return total

    # ---- bulk tokens ----
    async def create_bulk_token(self, calls: int, ttl: int) -> str:
        import secrets
        token = "bulk_" + secrets.token_urlsafe(24)
        await self._cmd("SET", f"bulk:{token}", str(calls), "EX", str(ttl))
        return token

    async def consume_bulk_token(self, token: str) -> bool:
        # atomic DECR, return false if <0
        remaining = await self._cmd("DECR", f"bulk:{token}")
        if remaining is None:
            return False
        if int(remaining) < 0:
            # restore and reject
            await self._cmd("INCR", f"bulk:{token}")
            return False
        return True

    async def bulk_token_remaining(self, token: str) -> int:
        v = await self._cmd("GET", f"bulk:{token}")
        return int(v) if v and v != "0" else 0

    # ---- subscription tokens ----
    async def create_subscription_token(self, quota: int, ttl: int) -> str:
        import secrets
        token = "sub_" + secrets.token_urlsafe(24)
        await self._cmd("SET", f"sub:{token}", str(quota), "EX", str(ttl))
        return token

    async def consume_subscription_token(self, token: str) -> bool:
        remaining = await self._cmd("DECR", f"sub:{token}")
        if remaining is None:
            return False
        if int(remaining) < 0:
            await self._cmd("INCR", f"sub:{token}")
            return False
        return True

    async def subscription_token_remaining(self, token: str) -> int:
        v = await self._cmd("GET", f"sub:{token}")
        return int(v) if v and v != "0" else 0

    # ---- response cache ----
    async def cache_get(self, key: str) -> Optional[Any]:
        v = await self._cmd("GET", f"cache:{key}")
        if not v:
            return None
        try:
            return json.loads(v)
        except Exception:
            return None

    async def cache_set(self, key: str, value: Any, ttl: int) -> None:
        await self._cmd("SET", f"cache:{key}", json.dumps(value), "EX", str(ttl))


# ============================================================================
# SINGLETON
# ============================================================================

if settings.has_persistent_store:
    store: Any = UpstashStore(settings.upstash_redis_rest_url, settings.upstash_redis_rest_token)
else:
    store = InMemoryStore()
