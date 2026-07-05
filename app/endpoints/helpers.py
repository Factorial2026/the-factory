"""Shared helpers for all endpoints (cache + receipt headers)."""
import hashlib
import json
import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..payment import make_receipt_header
from ..store import store

log = logging.getLogger("the_factory.helpers")


async def cache_get_or_set(key_prefix: str, params: dict, factory):
    """Try cache first; on miss, call factory() (async), cache result, return it.
    Returns (data, cached: bool).
    """
    raw = json.dumps(params, sort_keys=True, default=str)
    key = key_prefix + ":" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    cached = await store.cache_get(key)
    if cached is not None:
        return cached, True

    data = await factory()
    if data is not None:
        await store.cache_set(key, data, settings.cache_ttl_seconds)
    return data, False


def receipt_headers(request: Request) -> dict:
    receipt = getattr(request.state, "payment_receipt", None)
    return {"X-Payment-Response": make_receipt_header(receipt)} if receipt else {}


def safe_json(text: str) -> dict:
    """Strip markdown fences if LLM added them, then parse JSON."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
        # In case the model produced ```json{...}```
        if t.startswith("```"):
            t = t[3:]
    return json.loads(t)


def error_response(status: int, error: str, **extra) -> JSONResponse:
    payload = {"error": error}
    payload.update(extra)
    return JSONResponse(status_code=status, content=payload)
