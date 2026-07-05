"""
The Factory v3 - entry point.
Exposes 6 data endpoints + bulk/subscription purchase endpoints + dashboard + health.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.endpoints import (
    fx, github_stats, meteo, news, stocks, transit,
)
from app.stats import router as stats_router
from app.store import store

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("the_factory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("The Factory v3 booting up...")
    log.info("Wallet: %s | chain: %s", settings.wallet_address, settings.chain)
    log.info("Endpoints: 6 (meteo, fx, transit, news, stocks, github-stats)")
    log.info("Dashboard: /dashboard (HTML) and /stats (JSON)")
    log.info("Bulk pack: %d calls for %s USD",
             settings.bulk_pack_size, settings.bulk_pack_price_usd)
    log.info("Subscription: %d calls for %s USD",
             settings.subscription_quota_calls, settings.subscription_price_usd)
    log.info("Monthly cap: %s USD", settings.monthly_cap_usd)
    log.info("Gemini keys: %d | Groq keys: %d",
             len(settings.gemini_keys), len(settings.groq_keys))
    await store.init()
    yield
    log.info("The Factory shutting down...")
    await store.close()


app = FastAPI(
    title="The Factory v3",
    description="x402 HTTP-402 micropayment agent for clean machine-readable data.",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(meteo.router, prefix="/api/v1", tags=["meteo"])
app.include_router(fx.router, prefix="/api/v1", tags=["fx"])
app.include_router(transit.router, prefix="/api/v1", tags=["transit"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(stocks.router, prefix="/api/v1", tags=["stocks"])
app.include_router(github_stats.router, prefix="/api/v1", tags=["github-stats"])

# Bulk/subscription purchase endpoints are at root level (not under /api/v1)
from app.endpoints.billing import router as billing_router  # noqa: E402
app.include_router(billing_router, tags=["billing"])

# Dashboard + stats endpoints
app.include_router(stats_router, tags=["stats"])


@app.get("/health")
async def health():
    earned = await store.get_earnings_30d()
    return {
        "status": "ok",
        "version": "3.0.0",
        "wallet": settings.wallet_address,
        "chain": settings.chain,
        "monthly_cap_usd": settings.monthly_cap_usd,
        "earned_last_30d_usd": round(earned, 4),
        "cap_active": earned < settings.monthly_cap_usd,
        "endpoints": [
            "/api/v1/meteo",
            "/api/v1/fx",
            "/api/v1/transit",
            "/api/v1/news",
            "/api/v1/stocks",
            "/api/v1/github-stats",
        ],
        "extras": ["/dashboard", "/stats", "/bulk/purchase", "/subscription/purchase"],
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
        "llm_keys": {
            "gemini": len(settings.gemini_keys),
            "groq": len(settings.groq_keys),
        },
    }


@app.get("/")
async def root():
    return {
        "name": "The Factory",
        "version": "3.0.0",
        "protocol": "x402 (HTTP 402 Payment Required)",
        "endpoints": [
            "/api/v1/meteo",
            "/api/v1/fx",
            "/api/v1/transit",
            "/api/v1/news",
            "/api/v1/stocks",
            "/api/v1/github-stats",
        ],
        "billing": [
            "/bulk/purchase",
            "/subscription/purchase",
        ],
        "dashboard": "/dashboard",
        "stats": "/stats",
        "pricing_usd": {
            "meteo": settings.price_meteo,
            "fx": settings.price_fx,
            "transit": settings.price_transit,
            "news": settings.price_news,
            "stocks": settings.price_stocks,
            "github_stats": settings.price_github_stats,
        },
        "accepted_asset": "USDC",
        "accepted_chain": settings.chain,
        "pay_to": settings.wallet_address,
        "monthly_cap_usd": settings.monthly_cap_usd,
        "docs": "/docs",
        "python_client": "pip install the-factory-client",
        "langchain_tool": "pip install langchain-the-factory",
    }
