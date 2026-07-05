"""
Esca #4 — News headlines (Hacker News public API).
Raw: https://hacker-news.firebaseio.com/v0/topstories.json (+ item fetch)
Value-add: aggregates top N stories, LLM produces a clean JSON summary
with title, url, score, theme tags - ready for bot consumption.
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
from .helpers import cache_get_or_set, receipt_headers, safe_json

router = APIRouter()
log = logging.getLogger("the_factory.news")

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


@router.get("/news")
async def news(request: Request, n: int = 10, theme: str = ""):
    payment_resp = await require_payment(request, "/api/v1/news")
    if payment_resp:
        return payment_resp

    n = max(1, min(n, 30))
    params = {"n": n, "theme": theme}

    async def produce():
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(HN_TOP)
            r.raise_for_status()
            ids = r.json()[:n]
            items = []
            for i in ids[:n]:
                ir = await client.get(HN_ITEM.format(i))
                if ir.status_code == 200:
                    d = ir.json()
                    if d:
                        items.append({
                            "id": d.get("id"),
                            "title": d.get("title", ""),
                            "url": d.get("url", ""),
                            "score": d.get("score", 0),
                            "by": d.get("by", ""),
                            "time": d.get("time", 0),
                            "descendants": d.get("descendants", 0),
                        })

        system = (
            "Sei un servizio di news per bot aziendali. Ricevi una lista di storie da "
            "Hacker News. Restituisci SOLO un JSON valido con questo schema: "
            '{"count": int, "theme_filter": string (vuoto se non specificato), '
            '"stories": [{"id": int, "title": string, "url": string, "score": int, '
            '"category": string (una tra: tech, business, science, politics, culture), '
            '"summary": string (una frase in italiano sul tema)}]}. '
            "Filtra le storie in base a 'theme_filter' se non vuoto (case insensitive, "
            "match sul titolo). Non aggiungere testo fuori dal JSON."
        )
        prompt = (
            f"Theme filter: '{theme or '(none)'}'\n"
            f"Stories:\n{json.dumps(items)}"
        )
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=1200)
            return safe_json(text)
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {"count": len(items), "theme_filter": theme, "stories": items,
                    "warning": "llm_unavailable"}

    data, cached = await cache_get_or_set("news", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/news",
        cached=cached,
        amount_usd=settings.price_news,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
