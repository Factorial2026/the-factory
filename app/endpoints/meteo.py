"""
Esca #1 — Meteo (Open-Meteo).
Raw: https://archive-api.open-meteo.com/v1/archive (forecast: api.open-meteo.com)
Value-add: LLM normalises 40+ WMO codes + parallel-array JSON into flat 5-field schema.
"""
import datetime
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
log = logging.getLogger("the_factory.meteo")

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@router.get("/meteo")
async def meteo(request: Request, q: str = "Roma", days: int = 7):
    payment_resp = await require_payment(request, "/api/v1/meteo")
    if payment_resp:
        return payment_resp

    days = max(1, min(days, 30))
    params = {"q": q, "days": days}

    async def produce():
        # 1. Geocode
        async with httpx.AsyncClient(timeout=15) as client:
            g = await client.get(GEO_URL, params={"name": q, "count": 1, "language": "it"})
            g.raise_for_status()
            gdata = g.json().get("results") or []
            if not gdata:
                return error_response(404, "city_not_found", city=q)
            place = gdata[0]
            lat, lon = place["latitude"], place["longitude"]

        # 2. Fetch weather
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days - 1)
        url = ARCHIVE_URL if days > 1 else FORECAST_URL
        wp = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join([
                "temperature_2m_max", "temperature_2m_min",
                "precipitation_sum", "wind_speed_10m_max", "weather_code",
            ]),
            "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params=wp)
            r.raise_for_status()
            raw = r.json()

        # 3. LLM normalisation
        system = (
            "Sei un servizio meteo per bot aziendali. Ricevi JSON grezzo da Open-Meteo. "
            "Restituisci SOLO un JSON valido con questo schema esatto: "
            '{"location": string, "period_days": int, "summary": string (una frase in italiano), '
            '"avg_temp_c": number, "total_precip_mm": number, "max_wind_kmh": number, '
            '"days": [{"date": string, "t_max_c": number, "t_min_c": number, '
            '"precip_mm": number, "description": string}]}. '
            "I weather_code WMO vanno tradotti in descrizione italiana breve. "
            "La velocità del vento è in km/h. Non aggiungere testo fuori dal JSON."
        )
        prompt = f"Location name: {q}\nRaw data:\n{json.dumps(raw)}"
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=900)
            return safe_json(text)
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {"raw": raw, "error": "cleaning_failed", "detail": str(e)}

    data, cached = await cache_get_or_set("meteo", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/meteo",
        cached=cached,
        amount_usd=settings.price_meteo,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
