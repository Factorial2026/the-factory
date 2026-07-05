"""
Esca #3 — Transit real-time (Wiener Linien Vienna by default).
Raw: https://www.wienerlinien.at/ogd_realtime/monitor?rbl=<stop_id>
Value-add: nested/mixed-language JSON -> flat GTFS-style schema.
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
log = logging.getLogger("the_factory.transit")

DEFAULT_FEED = "https://www.wienerlinien.at/ogd_realtime/monitor"
DEFAULT_STOP = "4205"


@router.get("/transit")
async def transit(request: Request, stop: str = DEFAULT_STOP, feed: str = ""):
    payment_resp = await require_payment(request, "/api/v1/transit")
    if payment_resp:
        return payment_resp

    base_url = feed or DEFAULT_FEED
    params = {"stop": stop, "feed": base_url}

    async def produce():
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(base_url, params={"rbl": stop})
            if r.status_code != 200:
                return error_response(502, "feed_fetch_failed",
                                      upstream_status=r.status_code)
            try:
                raw = r.json()
            except Exception as e:
                return error_response(502, "feed_invalid_json", detail=str(e))

        system = (
            "Sei un normalizzatore di dati di trasporto pubblico per bot aziendali. "
            "Ricevi JSON grezzo (Wiener Linien o simili). "
            "Restituisci SOLO un JSON valido con questo schema: "
            '{"stop_id": string, "stop_name": string, "server_time": string (ISO 8601), '
            '"arrivals": [{"line": string, "direction": string, "eta_minutes": int, '
            '"realtime": boolean, "vehicle_type": string}]}. '
            "I tempi di attesa vanno convertiti in minuti interi. "
            "I tipi veicolo vanno normalizzati a uno tra: tram|bus|subway|train. "
            "Non aggiungere testo fuori dal JSON. Se non ci sono arrivi, "
            'restituisci {"stop_id": "...", "stop_name": "...", "server_time": "...", "arrivals": []}.'
        )
        prompt = f"Stop requested: {stop}\nRaw data:\n{json.dumps(raw)}"
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=900)
            return safe_json(text)
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {"raw": raw, "error": "cleaning_failed", "detail": str(e)}

    # Transit data is real-time: short cache TTL override via fresh key prefix
    # but still use cache for 60s to dedupe bursts
    data, cached = await cache_get_or_set("transit", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/transit",
        cached=cached,
        amount_usd=settings.price_transit,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
