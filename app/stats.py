"""
Stats endpoint for The Factory dashboard.

This file extends the existing main.py with a /stats endpoint that exposes
aggregated metrics for the public dashboard.

USAGE:
  1. Copy the code below into your existing app/main.py (or app/stats.py
     and import from main.py).
  2. The endpoint reads aggregated data from the store (Upstash or in-memory).
  3. The dashboard.html file (separate) fetches /stats every 30s and renders
     it with Chart.js.
"""
import logging
import time
from collections import Counter, deque
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .config import settings
from .store import store

log = logging.getLogger("the_factory.stats")

# In-memory rolling stats (last 1000 calls)
# If you want persistence across cold starts, move these to Upstash sorted sets.
_call_log: deque = deque(maxlen=1000)  # list of {ts, endpoint, cached, amount_usd, mode}
_started_at: float = time.time()

router = APIRouter()


def record_call(endpoint: str, cached: bool, amount_usd: float, mode: str = "single") -> None:
    """Called by each endpoint after a successful 200 response."""
    _call_log.append({
        "ts": time.time(),
        "endpoint": endpoint,
        "cached": cached,
        "amount_usd": amount_usd,
        "mode": mode,
    })


@router.get("/stats")
async def stats():
    """Public stats endpoint for the dashboard. No auth required."""
    now = time.time()
    cutoff_24h = now - 86400
    cutoff_7d = now - 7 * 86400

    calls_24h = [c for c in _call_log if c["ts"] > cutoff_24h]
    calls_7d = [c for c in _call_log if c["ts"] > cutoff_7d]

    revenue_24h = sum(c["amount_usd"] for c in calls_24h)
    revenue_7d = sum(c["amount_usd"] for c in calls_7d)

    endpoint_breakdown = Counter(c["endpoint"] for c in calls_7d)
    cache_hit_rate_24h = (
        sum(1 for c in calls_24h if c["cached"]) / len(calls_24h) * 100
        if calls_24h else 0
    )

    earned_30d = await store.get_earnings_30d()

    return {
        "service": "The Factory",
        "version": "2.0.0",
        "uptime_seconds": int(now - _started_at),
        "wallet": settings.wallet_address,
        "chain": settings.chain,
        "monthly_cap_usd": settings.monthly_cap_usd,
        "earned_last_30d_usd": round(earned_30d, 4),
        "cap_remaining_usd": round(max(0, settings.monthly_cap_usd - earned_30d), 4),
        "cap_pct": round(earned_30d / settings.monthly_cap_usd * 100, 2) if settings.monthly_cap_usd else 0,
        "calls_24h": len(calls_24h),
        "calls_7d": len(calls_7d),
        "revenue_24h_usd": round(revenue_24h, 4),
        "revenue_7d_usd": round(revenue_7d, 4),
        "cache_hit_rate_24h_pct": round(cache_hit_rate_24h, 2),
        "endpoint_breakdown_7d": dict(endpoint_breakdown),
        "pricing": {
            "meteo": settings.price_meteo,
            "fx": settings.price_fx,
            "transit": settings.price_transit,
            "news": settings.price_news,
            "stocks": settings.price_stocks,
            "github_stats": settings.price_github_stats,
        },
        "bulk": {
            "calls": settings.bulk_pack_size,
            "price_usd": settings.bulk_pack_price_usd,
        },
        "subscription": {
            "calls": settings.subscription_quota_calls,
            "price_usd": settings.subscription_price_usd,
        },
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML page (read from file)."""
    import pathlib
    dashboard_path = pathlib.Path(__file__).parent.parent / "static" / "dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse(
            "<h1>Dashboard not found</h1><p>Place dashboard.html in app/static/</p>",
            status_code=404,
        )
    return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))
