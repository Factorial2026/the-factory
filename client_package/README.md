# The Factory Client

Python client for [The Factory](https://github.com/Factorial2026/the-factory) — an x402 micropayment agent that sells clean JSON data to AI agents and bots.

## Install

```bash
pip install the-factory-client
```

## Quick start

```python
from the_factory_client import Factory

# Initialize with your Solana private key (Phantom → Settings → Show Private Key)
f = Factory(
    private_key_base58="YOUR_BASE58_PRIVATE_KEY",
    # optional: rpc_url="https://api.mainnet-beta.solana.com",
)

# Call any endpoint — payment is handled automatically
weather = f.get("/api/v1/meteo", params={"q": "Milano", "days": 3})
print(weather)
# {'location': 'Milano', 'avg_temp_c': 24.3, 'days': [...]}

fx = f.get("/api/v1/fx", params={"base": "EUR", "target": "USD", "days": 7})
transit = f.get("/api/v1/transit", params={"stop": "4205"})
```

## Bulk packs and subscriptions

Pre-pay for discounted calls:

```python
# Buy a 10-call bulk pack for 0.08 USDC
bulk = f.purchase_bulk()
print(bulk["token"])  # bulk_abc123...

# Use the token for the next 10 calls
for _ in range(10):
    data = f.get("/api/v1/meteo", params={"q": "Roma"})

# Or buy a monthly subscription (10k calls for $50)
sub = f.purchase_subscription()
```

## How it works (under the hood)

1. Client calls `GET /api/v1/<endpoint>` without payment header
2. Server returns `402` with `WWW-Authenticate: x402 challenge=...`
3. Client decodes the challenge, builds a USDC transfer tx to `pay_to` for `amount_atomic`
4. Client signs with the provided Solana keypair
5. Client broadcasts via Solana RPC, captures the tx signature
6. Client retries the endpoint with `X-Payment: base64({"signature":"<sig>"})`
7. Server verifies on-chain, returns `200` + clean JSON

All of this happens in `f.get(...)`. One line.

## API reference

### `Factory(private_key_base58=None, rpc_url=None, base_url=DEFAULT, token=None)`

- `private_key_base58`: Solana private key in base58 (from Phantom). Required for auto-payment.
- `rpc_url`: Solana RPC URL. Defaults to public mainnet.
- `base_url`: The Factory base URL. Defaults to `https://the-factory-9ja4.onrender.com`.
- `token`: Pre-purchased bulk or subscription token. If set, no Solana key needed.

### `f.get(endpoint, params=None) -> dict`

Call an endpoint with query params. Returns the cleaned JSON from the server.

### `f.purchase_bulk() -> dict`

Buy a 10-call bulk pack (0.08 USDC). Returns `{"token": "...", "calls_remaining": 10}`.

### `f.purchase_subscription() -> dict`

Buy a 10k-call monthly subscription (50 USDC). Returns `{"token": "...", "calls_remaining": 10000}`.

### `f.balance() -> dict`

Check the bulk/subscription token balance (if a token is set).

## License

MIT
