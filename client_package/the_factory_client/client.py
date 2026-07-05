"""
The Factory client — handles x402 payment flow automatically.

Flow:
  1. Client.get(endpoint, params) → HTTP GET without X-Payment
  2. If 402: decode challenge, build & sign USDC transfer tx, broadcast, get sig
  3. Retry GET with X-Payment: base64({"signature": "<sig>"})
  4. If 200: return JSON, attach receipt
  5. If 402 (verification failed): raise PaymentVerificationError

If a token (bulk or subscription) is set, step 2-3 are replaced by:
  Retry GET with X-Payment: base64({"token": "<token>"})
"""
import base64
import json
import logging
import time
from typing import Any, Dict, Optional

import base58
import httpx
from solana.rpc.api import Client as SolanaClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.hash import Hash
from solders.address_lookup_table import AddressLookupTableAccount

# SPL Token program for USDC transfers
try:
    from spl.token.instructions import (
        TransferParams as SplTransferParams,
        transfer_checked,
        get_associated_token_address,
    )
    from spl.constants import TOKEN_PROGRAM_ID
    HAS_SPL = True
except ImportError:
    HAS_SPL = False

from .exceptions import (
    CapReachedError,
    FactoryError,
    InsufficientFundsError,
    PaymentRequiredError,
    PaymentVerificationError,
    UpstreamError,
)

log = logging.getLogger("the_factory_client")

DEFAULT_BASE_URL = "https://the-factory-9ja4.onrender.com"
DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6
SOLANA_LAMPORTS_PER_SOL = 1_000_000_000


class Factory:
    """Synchronous client for The Factory API.

    Usage:
        f = Factory(private_key_base58="...")
        weather = f.get("/api/v1/meteo", params={"q": "Milano"})
    """

    def __init__(
        self,
        private_key_base58: Optional[str] = None,
        rpc_url: str = DEFAULT_RPC_URL,
        base_url: str = DEFAULT_BASE_URL,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if not private_key_base58 and not token:
            raise FactoryError(
                "Either private_key_base58 or token must be provided. "
                "Private key is required for single-call payments; "
                "token is required for bulk/subscription mode."
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self._http = httpx.Client(timeout=timeout)

        if private_key_base58:
            try:
                key_bytes = base58.b58decode(private_key_base58)
                self.keypair = Keypair.from_bytes(key_bytes)
            except Exception as e:
                raise FactoryError(f"Invalid private key: {e}") from e
            self.solana = SolanaClient(rpc_url)
            self.wallet_pubkey = self.keypair.pubkey()
        else:
            self.keypair = None
            self.solana = None
            self.wallet_pubkey = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> dict:
        """Call an endpoint with query params. Returns the cleaned JSON.

        Raises:
            PaymentRequiredError: Server demands payment but we can't pay
                                  (no keypair, no token).
            PaymentVerificationError: Payment was rejected by server.
            InsufficientFundsError: Wallet doesn't have enough USDC.
            CapReachedError: Service is paused (monthly cap reached).
            UpstreamError: Upstream data source failed.
            FactoryError: Other errors.
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{self.base_url}{endpoint}"
        headers = self._build_payment_header()
        response = self._http.get(url, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 402:
            return self._handle_402(endpoint, params, response)

        if response.status_code == 403:
            body = self._safe_json(response)
            if body.get("error") == "monthly_cap_reached":
                raise CapReachedError(body.get("message", "Monthly cap reached"))
            raise FactoryError(f"403 Forbidden: {body}")

        if response.status_code >= 500:
            body = self._safe_json(response)
            raise UpstreamError(
                f"Upstream error {response.status_code}: {body}",
                status_code=response.status_code,
                detail=str(body),
            )

        # Other 4xx
        body = self._safe_json(response)
        raise FactoryError(f"HTTP {response.status_code}: {body}")

    def purchase_bulk(self) -> dict:
        """Buy a 10-call bulk pack for 0.08 USDC. Returns the token + remaining calls."""
        return self._purchase_pack("/bulk/purchase")

    def purchase_subscription(self) -> dict:
        """Buy a 10k-call monthly subscription for 50 USDC. Returns token + remaining."""
        return self._purchase_pack("/subscription/purchase")

    def balance(self) -> dict:
        """If a token is set, return its remaining quota."""
        if not self.token:
            return {"token": None, "remaining": 0}
        # We don't have a /balance endpoint on server, but we can try a no-op call
        # and parse the receipt header for remaining.
        # Simplest: hit /health and read X-Payment-Response if we consume a call.
        # For now, return the token info only.
        return {"token": self.token, "remaining": "see receipt header after next call"}

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payment_header(self) -> Dict[str, str]:
        if not self.token:
            return {}
        payload = json.dumps({"token": self.token}).encode()
        b64 = base64.b64encode(payload).decode()
        return {"X-Payment": b64}

    def _handle_402(self, endpoint: str, params: Optional[dict], response) -> dict:
        body = self._safe_json(response)

        # If we already sent a payment (header was set) and got 402, it failed.
        if self.token:
            error = body.get("error", "")
            if "invalid" in error or "exhausted" in error:
                raise PaymentVerificationError(
                    f"Token rejected: {error}",
                    reason=error,
                )
            # If token was OK but server still demands payment, fall through
            # to single-call flow.

        # If we have a keypair, attempt to pay via Solana
        if self.keypair is None:
            challenge = body.get("challenge", {})
            raise PaymentRequiredError(
                f"Payment required for {endpoint} but no Solana keypair configured. "
                f"Challenge: {challenge}",
                challenge=challenge,
            )

        challenge = body.get("challenge", {})
        if not challenge:
            raise PaymentRequiredError(
                f"Server returned 402 but no challenge in body: {body}"
            )

        # Check error reason if it's a verification failure
        if body.get("error") == "payment_verification_failed":
            raise PaymentVerificationError(
                f"Payment verification failed: {body.get('reason', 'unknown')}",
                reason=body.get("reason", ""),
                amount_paid_usd=body.get("amount_paid_usd", 0),
                required_usd=body.get("required_usd", 0),
            )

        # Fresh 402 (challenge present) — pay and retry
        signature = self._pay_via_solana(challenge)
        return self._retry_with_signature(endpoint, params, signature)

    def _pay_via_solana(self, challenge: dict) -> str:
        """Build, sign, and broadcast a USDC transfer tx. Returns the signature."""
        pay_to_str = challenge.get("pay_to")
        amount_atomic = challenge.get("amount_atomic")
        if not pay_to_str or amount_atomic is None:
            raise FactoryError(f"Invalid challenge: {challenge}")

        if not HAS_SPL:
            raise FactoryError(
                "spl-token library not available. Install with: pip install spl-token"
            )

        pay_to = Pubkey.from_string(pay_to_str)
        mint = Pubkey.from_string(challenge.get("mint", USDC_MINT))

        # Get our USDC associated token account (source)
        source_ata = get_associated_token_address(self.wallet_pubkey, mint)
        dest_ata = get_associated_token_address(pay_to, mint)

        # Build transfer_checked instruction
        ix = transfer_checked(
            SplTransferParams(
                program_id=TOKEN_PROGRAM_ID,
                source=source_ata,
                mint=mint,
                dest=dest_ata,
                owner=self.wallet_pubkey,
                amount=amount_atomic,
                decimals=USDC_DECIMALS,
                signers=[],
            )
        )

        # Get recent blockhash
        recent = self.solana.get_latest_blockhash().value
        blockhash = recent.blockhash

        # Build message
        msg = MessageV0.try_compile(
            payer=self.wallet_pubkey,
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash,
        )

        # Sign
        tx = VersionedTransaction(msg, [self.keypair])

        # Broadcast
        try:
            result = self.solana.send_transaction(tx, opts={"skip_preflight": False})
            sig = str(result.value)
        except Exception as e:
            err_str = str(e).lower()
            if "insufficient" in err_str or "0x1" in err_str:
                raise InsufficientFundsError(
                    f"Wallet has insufficient USDC or SOL for gas. Error: {e}"
                ) from e
            raise FactoryError(f"Solana tx broadcast failed: {e}") from e

        # Wait for confirmation (best effort, 15s)
        self._wait_for_confirmation(sig, max_wait=15)
        return sig

    def _wait_for_confirmation(self, signature: str, max_wait: int = 15):
        """Poll Solana RPC until tx is confirmed or timeout."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                resp = self.solana.get_signature_statuses([signature])
                status = resp.value[0]
                if status is not None and status.confirmation_status is not None:
                    if "confirmed" in str(status.confirmation_status).lower() \
                       or "finalized" in str(status.confirmation_status).lower():
                        return
            except Exception:
                pass
            time.sleep(1)

    def _retry_with_signature(self, endpoint: str, params: Optional[dict],
                              signature: str) -> dict:
        """Retry the endpoint with the signature in X-Payment header."""
        url = f"{self.base_url}{endpoint}"
        payload = json.dumps({"signature": signature}).encode()
        b64 = base64.b64encode(payload).decode()
        headers = {"X-Payment": b64}

        response = self._http.get(url, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 402:
            body = self._safe_json(response)
            reason = body.get("reason", "unknown")
            raise PaymentVerificationError(
                f"Payment verification failed after retry: {reason}. "
                f"Body: {body}",
                reason=reason,
                amount_paid_usd=body.get("amount_paid_usd", 0),
                required_usd=body.get("required_usd", 0),
            )

        if response.status_code == 403:
            body = self._safe_json(response)
            if body.get("error") == "monthly_cap_reached":
                raise CapReachedError(body.get("message", "Monthly cap reached"))
            raise FactoryError(f"403 Forbidden: {body}")

        body = self._safe_json(response)
        raise FactoryError(f"HTTP {response.status_code} after payment: {body}")

    def _purchase_pack(self, endpoint: str) -> dict:
        """Purchase a bulk or subscription pack. Returns the response dict."""
        if self.keypair is None:
            raise FactoryError(
                "Cannot purchase pack without Solana keypair. "
                "Initialize Factory with private_key_base58."
            )

        url = f"{self.base_url}{endpoint}"
        # First call without payment → get 402 with challenge
        response = self._http.get(url)
        if response.status_code != 402:
            body = self._safe_json(response)
            raise FactoryError(
                f"Expected 402 from {endpoint}, got {response.status_code}: {body}"
            )

        body = self._safe_json(response)
        challenge = body.get("challenge", {})
        if not challenge:
            raise FactoryError(f"No challenge in 402 response: {body}")

        # Pay
        signature = self._pay_via_solana(challenge)

        # Retry with signature
        payload = json.dumps({"signature": signature}).encode()
        b64 = base64.b64encode(payload).decode()
        response = self._http.get(url, headers={"X-Payment": b64})

        if response.status_code != 200:
            body = self._safe_json(response)
            raise FactoryError(
                f"Pack purchase failed: HTTP {response.status_code}: {body}"
            )

        result = response.json()
        # Auto-set the token for subsequent calls
        if "token" in result:
            self.token = result["token"]
        return result

    @staticmethod
    def _safe_json(response) -> dict:
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}
