"""
Esca #5 — Stocks (Yahoo Finance public, no auth, no API key).
Raw: https://query1.finance.yahoo.com/v8/finance/chart/<symbol>
Value-add: parses verbose Yahoo JSON, LLM produces clean schema with
current price, change, volume, and short natural-language summary.
"""
import json
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..llm import llm
from ..payment import require_payment
from ..stats import record_call
from .helpers import cache_get_or_set, error_response, receipt_headers, safe_json

router = APIRouter()
log = logging.getLogger("the_factory.stocks")

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@router.get("/stocks")
async def stocks(request: Request, symbol: str = "AAPL", range: str = "5d"):
    payment_resp = await require_payment(request, "/api/v1/stocks")
    if payment_resp:
        return payment_resp

    symbol = symbol.upper()
    valid_ranges = {"1d", "5d", "1mo", "3mo", "6mo", "1y"}
    if range not in valid_ranges:
        range = "5d"
    params = {"symbol": symbol, "range": range}

    async def produce():
        url = YAHOO_URL.format(symbol=symbol)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params={"range": range, "interval": "1d"})
            if r.status_code != 200:
                return error_response(502, "yahoo_fetch_failed",
                                      upstream_status=r.status_code, symbol=symbol)
            try:
                raw = r.json()
            except Exception as e:
                return error_response(502, "yahoo_invalid_json", detail=str(e))

        result = (raw or {}).get("chart", {}).get("result") or []
        if not result:
            return error_response(404, "symbol_not_found", symbol=symbol)
        meta = result[0].get("meta", {})
        indicators = result[0].get("indicators", {})
        closes = (indicators.get("quote", [{}])[0].get("close") or [])
        closes_clean = [c for c in closes if c is not None]

        latest = closes_clean[-1] if closes_clean else meta.get("regularMarketPrice")
        first = closes_clean[0] if closes_clean else latest
        delta_pct = ((latest - first) / first * 100.0) if first and latest else 0.0

        compact = {
            "symbol": meta.get("symbol", symbol),
            "currency": meta.get("currency", "USD"),
            "exchange": meta.get("exchangeName", ""),
            "range": range,
            "latest_price": latest,
            "open_price": first,
            "delta_pct": round(delta_pct, 2),
            "volume": (meta.get("regularMarketVolume") or 0),
            "closes": closes_clean,
        }

        system = (
            "Sei un assistente finanziario per bot aziendali. Ricevi dati compattati da "
            "Yahoo Finance. Restituisci SOLO un JSON con questo schema: "
            '{"symbol": string, "currency": string, "latest_price": number, '
            '"open_price": number, "delta_pct": number, "summary": string '
            "(una frase in italiano che descrive il movimento di prezzo nel range)}. "
            "Non aggiungere testo fuori dal JSON."
        )
        prompt = (
            f"Symbol: {symbol}\nRange: {range}\nData:\n{json.dumps(compact)}"
        )
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=300)
            cleaned = safe_json(text)
            cleaned["closes"] = closes_clean
            return cleaned
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {**compact, "warning": "llm_unavailable"}

    data, cached = await cache_get_or_set("stocks", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/stocks",
        cached=cached,
        amount_usd=settings.price_stocks,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
