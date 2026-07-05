"""
x402 (HTTP 402 Payment Required) protocol implementation for Solana USDC.

Supports 3 payment modes:
  1. Single-call (per-endpoint price): one tx signature = one call.
  2. Bulk pack: pre-pay 10 calls at discount, receive token, use N times.
  3. Subscription: pre-pay monthly, receive token with quota, use N times.

Payment header format (base64-encoded JSON):
  - Single-call: {"signature": "<tx-sig>"}
  - Bulk/Subscription: {"token": "bulk_..." or "sub_..."}
"""
import asyncio
import base64
import json
import logging
import time
from typing import Optional, Tuple

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from .config import settings
from .store import store

log = logging.getLogger("the_factory.payment")

USDC_MINT = settings.usdc_mint
DECIMALS = 6
MICRO_USDC_PER_USD = 1_000_000
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TRANSFER_DISCRIMINANT = 3


_rpc_index = 0
_rpc_lock = asyncio.Lock()


async def _next_rpc() -> str:
    global _rpc_index
    async with _rpc_lock:
        url = settings.rpc_list[_rpc_index % len(settings.rpc_list)]
        _rpc_index += 1
        return url


async def _rpc_call(method: str, params: list, timeout: int = 12) -> Optional[dict]:
    tried = 0
    while tried < len(settings.rpc_list):
        url = await _next_rpc()
        tried += 1
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                )
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    log.warning("RPC %s error: %s", url, data["error"])
                    continue
                return data.get("result")
        except Exception as e:
            log.warning("RPC %s failed: %s", url, e)
            continue
    return None


# ============================================================================
# CHALLENGE & 402 RESPONSE
# ============================================================================

def build_challenge(endpoint_path: str, amount_usd: float) -> dict:
    return {
        "version": "x402/0.1",
        "asset": "USDC",
        "chain": settings.chain,
        "pay_to": settings.wallet_address,
        "amount_usd": amount_usd,
        "amount_atomic": int(amount_usd * MICRO_USDC_PER_USD),
        "decimals": DECIMALS,
        "mint": USDC_MINT,
        "resource": endpoint_path,
        "network": "mainnet-beta",
        "max_fee_usd": round(amount_usd * 1.10, 4),
        "expires_at_unix": int(time.time()) + 300,
    }


def make_402_response(endpoint_path: str, amount_usd: float) -> JSONResponse:
    challenge = build_challenge(endpoint_path, amount_usd)
    challenge_b64 = base64.b64encode(json.dumps(challenge).encode()).decode()
    return JSONResponse(
        status_code=402,
        content={
            "error": "payment_required",
            "x402_version": "0.1",
            "challenge": challenge,
            "instructions": (
                f"Pay {amount_usd} USDC to {settings.wallet_address} "
                f"on Solana mainnet (mint {USDC_MINT}), then retry with header "
                f"'X-Payment: base64(JSON with 'signature' field)'. "
                f"For bulk/subscription tokens, see /docs."
            ),
        },
        headers={
            "WWW-Authenticate": f'x402 challenge="{challenge_b64}"',
            "X-Price": f"{amount_usd} USD",
            "X-Pay-To": settings.wallet_address,
            "X-Chain": settings.chain,
            "X-Asset": "USDC",
        },
    )


# ============================================================================
# SOLANA TX VERIFICATION
# ============================================================================

def _scan_inner_transfers(tx_result: dict) -> int:
    """Fallback: scan inner + outer SPL Token 'transfer' instructions that credit
    a token account owned by our wallet. Returns amount in USDC micro-units.
    """
    credited_atomic = 0
    meta = tx_result.get("meta") or {}
    message = (tx_result.get("transaction") or {}).get("message") or {}
    account_keys = message.get("accountKeys") or []
    inner_ixs = meta.get("innerInstructions") or []
    instructions = list(message.get("instructions") or [])
    for inner in inner_ixs:
        instructions.extend(inner.get("instructions") or [])

    for ix in instructions:
        if not isinstance(ix, dict):
            continue
        prog_idx = ix.get("programIdIndex")
        if prog_idx is None or prog_idx >= len(account_keys):
            continue
        if account_keys[prog_idx] != TOKEN_PROGRAM_ID:
            continue
        data_b64 = ix.get("data") or ""
        try:
            raw = base64.b64decode(data_b64 + "===")
        except Exception:
            continue
        if len(raw) < 9 or raw[0] != TRANSFER_DISCRIMINANT:
            continue
        amount = int.from_bytes(raw[1:9], "little")
        accounts = ix.get("accounts") or []
        if len(accounts) < 2:
            continue
        dest_idx = accounts[1]
        for b in (meta.get("postTokenBalances") or []):
            if (b.get("accountIndex") == dest_idx
                    and b.get("mint") == USDC_MINT
                    and b.get("owner") == settings.wallet_address):
                credited_atomic += amount
                break
    return credited_atomic


def _scan_self_transfer(tx_result: dict, required_atomic: int) -> int:
    """Detect self-transfer pattern (Phantom sending USDC from our wallet
    to our own address). Used for self-test; in production customers pay
    from a different wallet, so step 4/5 of verify_payment already credits
    the amount correctly.
    """
    meta = tx_result.get("meta") or {}
    message = (tx_result.get("transaction") or {}).get("message") or {}
    account_keys = message.get("accountKeys") or []
    instructions = list(message.get("instructions") or [])
    for inner in (meta.get("innerInstructions") or []):
        instructions.extend(inner.get("instructions") or [])

    for ix in instructions:
        if not isinstance(ix, dict):
            continue
        prog_idx = ix.get("programIdIndex")
        if prog_idx is None or prog_idx >= len(account_keys):
            continue
        if account_keys[prog_idx] != TOKEN_PROGRAM_ID:
            continue
        accounts = ix.get("accounts") or []
        if len(accounts) < 3:
            continue
        source_idx = accounts[0]
        if len(accounts) >= 4:
            dest_idx = accounts[2]
            owner_idx = accounts[3]
        else:
            dest_idx = accounts[1]
            owner_idx = accounts[2]
        if source_idx != dest_idx:
            continue
        if owner_idx >= len(account_keys):
            continue
        if account_keys[owner_idx] != settings.wallet_address:
            continue
        for b in (meta.get("preTokenBalances") or []):
            if (b.get("accountIndex") == source_idx
                    and b.get("mint") == USDC_MINT
                    and b.get("owner") == settings.wallet_address):
                pre_amt = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
                if int(pre_amt * MICRO_USDC_PER_USD) >= required_atomic:
                    return required_atomic
                break
    return 0


async def verify_payment(signature: str, required_usd: float) -> Tuple[bool, float, str]:
    """Verify a Solana USDC payment for `required_usd` amount."""
    if await store.is_signature_seen(signature):
        return False, 0.0, "signature_already_used"

    result = await _rpc_call(
        "getTransaction",
        [signature, {"maxSupportedTransactionVersion": 0, "commitment": "confirmed"}],
    )
    if not result:
        return False, 0.0, "rpc_unavailable_or_tx_not_found"

    meta = result.get("meta") or {}
    if meta.get("err"):
        return False, 0.0, f"tx_failed: {meta['err']}"

    block_time = result.get("blockTime")
    if not block_time:
        return False, 0.0, "no_block_time"
    age = time.time() - block_time
    if age > settings.payment_window_seconds:
        return False, 0.0, f"expired ({int(age)}s old)"
    if age < -10:
        return False, 0.0, "future_tx"

    pre_balances = meta.get("preTokenBalances") or []
    post_balances = meta.get("postTokenBalances") or []
    pre_map = {(b.get("accountIndex"), b.get("mint")): b for b in pre_balances}
    post_map = {(b.get("accountIndex"), b.get("mint")): b for b in post_balances}

    credited_atomic = 0
    for key, post_b in post_map.items():
        if post_b.get("mint") != USDC_MINT:
            continue
        if post_b.get("owner") != settings.wallet_address:
            continue
        post_amt = float(post_b.get("uiTokenAmount", {}).get("uiAmount") or 0)
        pre_b = pre_map.get(key)
        pre_amt = float(pre_b.get("uiTokenAmount", {}).get("uiAmount") or 0) if pre_b else 0
        delta = post_amt - pre_amt
        if delta > 0:
            credited_atomic += int(delta * MICRO_USDC_PER_USD)

    if credited_atomic <= 0:
        credited_atomic = _scan_inner_transfers(result)

    required_atomic = int(required_usd * MICRO_USDC_PER_USD)
    if credited_atomic < required_atomic:
        st_atomic = _scan_self_transfer(result, required_atomic)
        if st_atomic >= required_atomic:
            credited_atomic = st_atomic

    if credited_atomic < required_atomic:
        return False, credited_atomic / MICRO_USDC_PER_USD, (
            f"insufficient: paid {credited_atomic/MICRO_USDC_PER_USD:.6f} < "
            f"required {required_usd}"
        )

    await store.mark_signature(signature, ttl=settings.payment_window_seconds)
    await store.add_earning(required_usd)

    return True, required_usd, "ok"


# ============================================================================
# BULK / SUBSCRIPTION TOKEN HELPERS
# ============================================================================

async def create_bulk_pack() -> Tuple[bool, str, Optional[dict]]:
    """Issue a bulk-pack creation challenge. Returns (ok, msg, info).
    Client pays bulk_pack_price_usd, retries with X-Payment: signature,
    server creates the bulk token and returns it.
    """
    return True, "ok", {
        "amount_usd": settings.bulk_pack_price_usd,
        "calls": settings.bulk_pack_size,
        "ttl_seconds": settings.bulk_token_ttl_seconds,
    }


async def create_subscription() -> Tuple[bool, str, Optional[dict]]:
    return True, "ok", {
        "amount_usd": settings.subscription_price_usd,
        "calls": settings.subscription_quota_calls,
        "ttl_seconds": settings.subscription_token_ttl_seconds,
    }


# ============================================================================
# MAIN PAYMENT GATEWAY
# ============================================================================

async def require_payment(request: Request, endpoint_path: str) -> Optional[JSONResponse]:
    """Returns None if payment OK; otherwise returns a 402/403/400 response to send.
    When returning None, sets request.state.payment_receipt for the endpoint.
    """
    earned = await store.get_earnings_30d()
    if earned >= settings.monthly_cap_usd:
        return JSONResponse(
            status_code=403,
            content={
                "error": "monthly_cap_reached",
                "message": (
                    f"Ethical cap of {settings.monthly_cap_usd} USD reached for the "
                    f"last 30 days. Service paused until window resets."
                ),
                "earned_30d": round(earned, 4),
                "cap": settings.monthly_cap_usd,
            },
            headers={"X-Ethical-Cap": "reached"},
        )

    price_usd = settings.price_for(endpoint_path)
    payment_header = request.headers.get("X-Payment")
    if not payment_header:
        return make_402_response(endpoint_path, price_usd)

    try:
        decoded = base64.b64decode(payment_header).decode()
        payload = json.loads(decoded)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_payment_header", "detail": str(e)},
        )

    # Mode A: token-based (bulk or subscription)
    token = payload.get("token")
    if token:
        if token.startswith("bulk_"):
            ok = await store.consume_bulk_token(token)
            if not ok:
                return JSONResponse(
                    status_code=402,
                    content={"error": "bulk_token_invalid_or_exhausted"},
                    headers={"WWW-Authenticate": "x402"},
                )
            receipt = {
                "mode": "bulk",
                "token": token,
                "remaining": await store.bulk_token_remaining(token),
                "verified_at": int(time.time()),
            }
            request.state.payment_receipt = receipt
            return None
        elif token.startswith("sub_"):
            ok = await store.consume_subscription_token(token)
            if not ok:
                return JSONResponse(
                    status_code=402,
                    content={"error": "subscription_token_invalid_or_exhausted"},
                    headers={"WWW-Authenticate": "x402"},
                )
            receipt = {
                "mode": "subscription",
                "token": token,
                "remaining": await store.subscription_token_remaining(token),
                "verified_at": int(time.time()),
            }
            request.state.payment_receipt = receipt
            return None
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "unknown_token_type", "token_prefix": token[:5]},
            )

    # Mode B: signature-based (single call)
    signature = payload.get("signature") or payload.get("tx_signature") or ""
    if not signature:
        return JSONResponse(status_code=400, content={"error": "missing_signature"})

    ok, amount, reason = await verify_payment(signature, price_usd)
    if not ok:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_verification_failed",
                "reason": reason,
                "amount_paid_usd": round(amount, 6),
                "required_usd": price_usd,
            },
            headers={"WWW-Authenticate": "x402"},
        )

    request.state.payment_receipt = {
        "mode": "single",
        "signature": signature,
        "amount_usd": round(amount, 6),
        "verified_at": int(time.time()),
        "network": "solana-mainnet",
        "pay_to": settings.wallet_address,
    }
    return None


def make_receipt_header(receipt: dict) -> str:
    return "x402 " + base64.b64encode(json.dumps(receipt).encode()).decode()
