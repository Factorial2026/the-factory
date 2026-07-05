"""
Centralised settings. All secrets come from environment variables.
"""
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- LLM keys (CSV) ----
    gemini_api_keys: str = Field(default="")
    groq_api_keys: str = Field(default="")

    # ---- Wallet / chain ----
    chain: str = Field(default="solana")
    wallet_address: str = Field(default="")

    # ---- Per-endpoint pricing ----
    price_meteo: float = Field(default=0.01)
    price_fx: float = Field(default=0.02)
    price_transit: float = Field(default=0.02)
    price_news: float = Field(default=0.02)
    price_stocks: float = Field(default=0.05)
    price_github_stats: float = Field(default=0.02)

    # ---- Bulk pricing ----
    bulk_pack_size: int = Field(default=10)
    bulk_pack_price_usd: float = Field(default=0.08)
    bulk_token_ttl_seconds: int = Field(default=86400)

    # ---- Subscription ----
    subscription_price_usd: float = Field(default=50.0)
    subscription_quota_calls: int = Field(default=10000)
    subscription_token_ttl_seconds: int = Field(default=30 * 86400)

    # ---- Ethical cap ----
    monthly_cap_usd: float = Field(default=120.0)

    # ---- Solana RPCs ----
    solana_rpc_urls: str = Field(
        default=(
            "https://api.mainnet-beta.solana.com,"
            "https://solana-rpc.publicnode.com,"
            "https://rpc.ankr.com/solana"
        )
    )
    usdc_mint: str = Field(default="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

    # ---- Cache (Upstash Redis REST) ----
    upstash_redis_rest_url: str = Field(default="")
    upstash_redis_rest_token: str = Field(default="")
    cache_ttl_seconds: int = Field(default=3600)

    # ---- Misc ----
    log_level: str = Field(default="INFO")
    request_timeout_seconds: int = Field(default=20)
    payment_window_seconds: int = Field(default=300)

    @property
    def gemini_keys(self) -> List[str]:
        return _split_csv(self.gemini_api_keys)

    @property
    def groq_keys(self) -> List[str]:
        return _split_csv(self.groq_api_keys)

    @property
    def rpc_list(self) -> List[str]:
        return _split_csv(self.solana_rpc_urls)

    @property
    def has_persistent_store(self) -> bool:
        return bool(self.upstash_redis_rest_url and self.upstash_redis_rest_token)

    def price_for(self, endpoint: str) -> float:
        """Return the unit price for a given endpoint path."""
        mapping = {
            "/api/v1/meteo": self.price_meteo,
            "/api/v1/fx": self.price_fx,
            "/api/v1/transit": self.price_transit,
            "/api/v1/news": self.price_news,
            "/api/v1/stocks": self.price_stocks,
            "/api/v1/github-stats": self.price_github_stats,
        }
        return mapping.get(endpoint, self.price_meteo)


settings = Settings()
