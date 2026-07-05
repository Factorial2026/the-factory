"""
LangChain Tool wrappers for The Factory endpoints.

Each endpoint becomes a structured Tool with:
- Auto-generated docstring (used by the LLM to decide when to call it)
- Pydantic input schema (enforces parameter types)
- Payment handling via the-factory-client
- Cost-per-call transparent to the agent
"""
import logging
from typing import List, Optional, Type

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field

log = logging.getLogger("langchain_the_factory")


# ----------------------------------------------------------------------
# Input schemas (one per endpoint)
# ----------------------------------------------------------------------

class WeatherInput(BaseModel):
    city: str = Field(description="City name, e.g. 'Milano', 'New York', 'Tokyo'")
    days: int = Field(default=7, ge=1, le=30,
                      description="Number of days to fetch (1-30, default 7)")


class FxInput(BaseModel):
    base: str = Field(default="EUR", description="Base currency ISO code, e.g. 'EUR'")
    target: str = Field(default="USD", description="Target currency ISO code, e.g. 'USD'")
    days: int = Field(default=1, ge=1, le=90,
                      description="Number of days of history (1-90, default 1)")


class TransitInput(BaseModel):
    stop: str = Field(default="4205",
                      description="Stop ID (RBL number). Default 4205 = Karlsplatz Vienna")
    feed: Optional[str] = Field(default=None,
                                description="Custom transit feed URL (optional)")


class NewsInput(BaseModel):
    n: int = Field(default=10, ge=1, le=30,
                   description="Number of stories to fetch (1-30, default 10)")
    theme: str = Field(default="",
                       description="Optional theme filter, e.g. 'AI', 'crypto', 'rust'")


class StocksInput(BaseModel):
    symbol: str = Field(default="AAPL",
                        description="Stock ticker symbol, e.g. 'AAPL', 'TSLA', 'MSFT'")
    range: str = Field(default="5d",
                       description="Time range: one of '1d','5d','1mo','3mo','6mo','1y'")


class GithubStatsInput(BaseModel):
    owner: str = Field(default="facebook",
                       description="GitHub repo owner, e.g. 'facebook', 'microsoft'")
    repo: str = Field(default="react",
                      description="GitHub repo name, e.g. 'react', 'vscode'")


# ----------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------

class FactoryTool(BaseTool):
    """Generic Factory tool — instantiated with endpoint + schema + price."""

    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel] = WeatherInput
    # Non-pydantic private attrs (declared via ClassVar or PrivateAttr)
    _client: any = None
    _endpoint: str = ""
    _price_usd: float = 0.01

    def __init__(self, client, endpoint: str, name: str, description: str,
                 args_schema: Type[BaseModel], price_usd: float):
        super().__init__(
            name=name,
            description=description,
            args_schema=args_schema,
        )
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_endpoint", endpoint)
        object.__setattr__(self, "_price_usd", price_usd)

    def _run(self, **kwargs) -> dict:
        """Synchronous execution."""
        try:
            result = self._client.get(self._endpoint, params=kwargs)
            return {
                "endpoint": self._endpoint,
                "price_paid_usd": self._price_usd,
                "data": result,
            }
        except Exception as e:
            return {"error": str(e), "endpoint": self._endpoint}

    async def _arun(self, **kwargs) -> dict:
        """Async execution — currently delegates to sync (the-factory-client is sync)."""
        return self._run(**kwargs)


# ----------------------------------------------------------------------
# Toolkit
# ----------------------------------------------------------------------

class FactoryToolkit(BaseToolkit):
    """Toolkit that exposes all 6 Factory endpoints as LangChain Tools.

    Usage:
        toolkit = FactoryToolkit(private_key_base58="...", token="bulk_...")
        tools = toolkit.get_tools()
    """

    # Pydantic v2 model fields (so we can pass them in __init__)
    private_key_base58: Optional[str] = None
    token: Optional[str] = None
    base_url: str = "https://the-factory-9ja4.onrender.com"

    def __init__(self, private_key_base58: Optional[str] = None,
                 token: Optional[str] = None,
                 base_url: str = "https://the-factory-9ja4.onrender.com"):
        super().__init__(
            private_key_base58=private_key_base58,
            token=token,
            base_url=base_url,
        )
        # Lazy import to avoid hard dep at module load
        from the_factory_client import Factory
        self._factory = Factory(
            private_key_base58=private_key_base58,
            token=token,
            base_url=base_url,
        )

    def get_tools(self) -> List[BaseTool]:
        """Return all 6 endpoint tools."""

        return [
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/meteo",
                name="get_weather",
                description=(
                    "Get clean weather forecast for a city. Returns JSON with "
                    "location, summary, avg_temp_c, days array. "
                    "Cost: $0.01 per call. Use this when the user asks about "
                    "weather, temperature, forecast, or climate conditions for "
                    "a specific city."
                ),
                args_schema=WeatherInput,
                price_usd=0.01,
            ),
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/fx",
                name="get_fx_rate",
                description=(
                    "Get foreign exchange rate between two currencies. Returns "
                    "JSON with latest rate, trend summary, and history array. "
                    "Cost: $0.02 per call. Use this when the user asks about "
                    "exchange rates, currency conversion, or FX trends."
                ),
                args_schema=FxInput,
                price_usd=0.02,
            ),
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/transit",
                name="get_transit_arrivals",
                description=(
                    "Get real-time public transit arrivals for a stop. Returns "
                    "JSON with stop_name, server_time, arrivals array (line, "
                    "direction, eta_minutes, vehicle_type). "
                    "Cost: $0.02 per call. Use this when the user asks about "
                    "transit, bus, tram, subway arrivals at a specific stop."
                ),
                args_schema=TransitInput,
                price_usd=0.02,
            ),
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/news",
                name="get_tech_news",
                description=(
                    "Get aggregated tech news headlines from Hacker News. Returns "
                    "JSON with stories array (title, url, score, category, summary). "
                    "Cost: $0.02 per call. Use this when the user asks about "
                    "tech news, recent launches, or trending stories."
                ),
                args_schema=NewsInput,
                price_usd=0.02,
            ),
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/stocks",
                name="get_stock_price",
                description=(
                    "Get stock price and movement summary. Returns JSON with "
                    "symbol, latest_price, open_price, delta_pct, summary, closes. "
                    "Cost: $0.05 per call. Use this when the user asks about "
                    "stock prices, share price, or market performance."
                ),
                args_schema=StocksInput,
                price_usd=0.05,
            ),
            FactoryTool(
                client=self._factory,
                endpoint="/api/v1/github-stats",
                name="get_github_stats",
                description=(
                    "Get health snapshot for a GitHub repository. Returns JSON "
                    "with stars, forks, activity_level, health_summary, "
                    "top_language, recent_commits. "
                    "Cost: $0.02 per call. Use this when the user asks about "
                    "a GitHub repo's popularity, activity, or health."
                ),
                args_schema=GithubStatsInput,
                price_usd=0.02,
            ),
        ]

    def close(self):
        """Close the underlying Factory client."""
        if hasattr(self, "_factory") and self._factory:
            self._factory.close()
