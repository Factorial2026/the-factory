"""
Billing endpoints for bulk pack and subscription purchases.

Flow:
  1. Client requests /bulk/purchase or /subscription/purchase without X-Payment.
  2. Server returns 402 with challenge for the bulk/sub price.
  3. Client pays USDC, retries with X-Payment: signature.
  4. Server verifies payment, mints a token, returns it in JSON body and receipt header.
  5. Client uses token in subsequent X-Payment: {"token": "bulk_..."} on any data endpoint.
"""
import base64
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..payment import make_receipt_header, require_payment, verify_payment
from ..store import store

router = APIRouter()
log = logging.getLogger("the_factory.billing")


def _make_402(amount: float, resource: str) -> JSONResponse:
    challenge = {
        "version": "x402/0.1",
        "asset": "USDC",
        "chain": settings.chain,
        "pay_to": settings.wallet_address,
        "amount_usd": amount,
        "amount_atomic": int(amount * 1_000_000),
        "decimals": 6,
        "mint": settings.usdc_mint,
        "resource": resource,
        "network": "mainnet-beta",
        "expires_at_unix": int(time.time()) + 300,
    }
    challenge_b64 = base64.b64encode(json.dumps(challenge).encode()).decode()
    return JSONResponse(
        status_code=402,
        content={
            "error": "payment_required",
            "challenge": challenge,
            "instructions": (
                f"Pay {amount} USDC to {settings.wallet_address} on Solana mainnet, "
                f"then retry with header 'X-Payment: base64(JSON with 'signature' field)'. "
                f"On success, a token will be returned in the response body."
            ),
        },
        headers={
            "WWW-Authenticate": f'x402 challenge="{challenge_b64}"',
            "X-Price": f"{amount} USD",
            "X-Pay-To": settings.wallet_address,
            "X-Chain": settings.chain,
        },
    )


@router.get("/bulk/purchase")
async def bulk_purchase(request: Request):
    """Purchase a bulk pack of N calls at discounted price."""
    # First check cap
    earned = await store.get_earnings_30d()
    if earned >= settings.monthly_cap_usd:
        return JSONResponse(
            status_code=403,
            content={"error": "monthly_cap_reached",
                     "earned_30d": round(earned, 4),
                     "cap": settings.monthly_cap_usd},
        )

    # Parse X-Payment
    payment_header = request.headers.get("X-Payment")
    if not payment_header:
        return _make_402(settings.bulk_pack_price_usd, "/bulk/purchase")

    try:
        decoded = base64.b64decode(payment_header).decode()
        payload = json.loads(decoded)
        signature = payload.get("signature") or payload.get("tx_signature") or ""
        if not signature:
            return JSONResponse(status_code=400, content={"error": "missing_signature"})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_payment_header", "detail": str(e)},
        )

    ok, amount, reason = await verify_payment(signature, settings.bulk_pack_price_usd)
    if not ok:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_verification_failed",
                "reason": reason,
                "amount_paid_usd": round(amount, 6),
                "required_usd": settings.bulk_pack_price_usd,
            },
            headers={"WWW-Authenticate": "x402"},
        )

    # Mint bulk token
    token = await store.create_bulk_token(
        calls=settings.bulk_pack_size,
        ttl=settings.bulk_token_ttl_seconds,
    )
    receipt = {
        "mode": "bulk_purchase",
        "signature": signature,
        "amount_paid_usd": round(amount, 6),
        "token": token,
        "calls_remaining": settings.bulk_pack_size,
        "ttl_seconds": settings.bulk_token_ttl_seconds,
        "verified_at": int(time.time()),
        "usage": "Pass 'X-Payment: base64(JSON({\"token\": \"<token>\"}))' on any data endpoint.",
    }
    return JSONResponse(
        content=receipt,
        headers={"X-Payment-Response": make_receipt_header(receipt)},
    )


@router.get("/subscription/purchase")
async def subscription_purchase(request: Request):
    """Purchase a monthly subscription: N calls for 30 days."""
    earned = await store.get_earnings_30d()
    if earned >= settings.monthly_cap_usd:
        return JSONResponse(
            status_code=403,
            content={"error": "monthly_cap_reached",
                     "earned_30d": round(earned, 4),
                     "cap": settings.monthly_cap_usd},
        )

    payment_header = request.headers.get("X-Payment")
    if not payment_header:
        return _make_402(settings.subscription_price_usd, "/subscription/purchase")

    try:
        decoded = base64.b64decode(payment_header).decode()
        payload = json.loads(decoded)
        signature = payload.get("signature") or payload.get("tx_signature") or ""
        if not signature:
            return JSONResponse(status_code=400, content={"error": "missing_signature"})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_payment_header", "detail": str(e)},
        )

    ok, amount, reason = await verify_payment(signature, settings.subscription_price_usd)
    if not ok:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_verification_failed",
                "reason": reason,
                "amount_paid_usd": round(amount, 6),
                "required_usd": settings.subscription_price_usd,
            },
            headers={"WWW-Authenticate": "x402"},
        )

    token = await store.create_subscription_token(
        quota=settings.subscription_quota_calls,
        ttl=settings.subscription_token_ttl_seconds,
    )
    receipt = {
        "mode": "subscription_purchase",
        "signature": signature,
        "amount_paid_usd": round(amount, 6),
        "token": token,
        "calls_remaining": settings.subscription_quota_calls,
        "ttl_seconds": settings.subscription_token_ttl_seconds,
        "verified_at": int(time.time()),
        "usage": "Pass 'X-Payment: base64(JSON({\"token\": \"<token>\"}))' on any data endpoint.",
    }
    return JSONResponse(
        content=receipt,
        headers={"X-Payment-Response": make_receipt_header(receipt)},
    )
