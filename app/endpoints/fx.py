"""
Esca #2 — FX rates (European Central Bank).
Raw: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml (and -hist-90d.xml)
Value-add: parses GESMES XML, computes cross-rates & trend, LLM writes summary.
"""
import json
import logging
from xml.etree import ElementTree as ET

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..llm import llm
from ..payment import require_payment
from ..stats import record_call
from .helpers import cache_get_or_set, error_response, receipt_headers, safe_json

router = APIRouter()
log = logging.getLogger("the_factory.fx")

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_HIST = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
NS = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "eurofx": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
}


@router.get("/fx")
async def fx(request: Request, base: str = "EUR", target: str = "USD", days: int = 1):
    payment_resp = await require_payment(request, "/api/v1/fx")
    if payment_resp:
        return payment_resp

    days = max(1, min(days, 90))
    base = base.upper()
    target = target.upper()
    params = {"base": base, "target": target, "days": days}

    async def produce():
        url = ECB_HIST if days > 1 else ECB_DAILY
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            xml_text = r.text

        try:
            tree = ET.fromstring(xml_text)
            root_cube = tree.find("eurofx:Cube", NS)
            if root_cube is None:
                return error_response(502, "ecb_parse_failed")
        except ET.ParseError as e:
            return error_response(502, "ecb_parse_failed", detail=str(e))

        series: dict[str, dict[str, float]] = {}
        for day_cube in root_cube.findall("eurofx:Cube", NS):
            date_str = day_cube.get("time")
            if not date_str:
                continue
            rates: dict[str, float] = {}
            for cur_cube in day_cube.findall("eurofx:Cube", NS):
                cur = cur_cube.get("currency")
                rate = cur_cube.get("rate")
                if cur and rate:
                    try:
                        rates[cur] = float(rate)
                    except ValueError:
                        pass
            series[date_str] = rates

        sorted_dates = sorted(series.keys(), reverse=True)[:days]
        history = []
        for d in sorted_dates:
            r = series[d]
            eur_to_target = r.get(target)
            eur_to_base = 1.0 if base == "EUR" else r.get(base)
            if not eur_to_target or not eur_to_base:
                continue
            pair_rate = eur_to_target / eur_to_base
            history.append({"date": d, "rate": round(pair_rate, 4)})

        if not history:
            return error_response(404, "pair_not_available", pair=f"{base}/{target}")

        latest = history[0]["rate"]
        oldest = history[-1]["rate"]
        delta_pct = ((latest - oldest) / oldest) * 100.0 if oldest else 0.0

        system = (
            "Sei un assistente finanziario per bot aziendali. Ricevi dati storici di tassi "
            "di cambio. Restituisci SOLO un JSON con questo schema: "
            '{"pair": string (es. "EUR/USD"), "latest_rate": number, '
            '"trend_summary": string (una frase in italiano che descrive il movimento: '
            "salito/disceso/stabile + percentuale approssimata)}. "
            "Non aggiungere testo fuori dal JSON."
        )
        prompt = (
            f"Base: {base}, Target: {target}, Days: {days}\n"
            f"Storico (più recente prima): {json.dumps(history)}\n"
            f"Variazione percentuale sul periodo: {delta_pct:.2f}%"
        )
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=300)
            cleaned = safe_json(text)
            cleaned["history"] = history
            return cleaned
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {
                "pair": f"{base}/{target}",
                "latest_rate": latest,
                "trend_summary": f"Variazione {delta_pct:+.2f}% nei {days} giorni.",
                "history": history,
                "warning": "llm_unavailable",
            }

    data, cached = await cache_get_or_set("fx", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/fx",
        cached=cached,
        amount_usd=settings.price_fx,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
