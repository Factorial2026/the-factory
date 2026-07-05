# The Factory v3 — x402 Machine Data API

> Autonomous HTTP 402 micropayment agent. Sells clean, machine-readable JSON
> data to bots, AI agents, and M2M commerce. Pay-per-call in USDC on Solana.
> No signup. No auth. No API keys. No platform fees. Bulk + subscription plans.
> With Python client, LangChain tool, and live dashboard.

---

## 📍 Base URL

```
https://the-factory-9ja4.onrender.com
```

**Interactive docs**: `/docs`
**Health**: `/health`
**Live dashboard**: `/dashboard`
**Stats JSON**: `/stats`

---

## 💰 Pricing

### Single-call (pay-per-call)

| Endpoint | Price (USDC) | Asset | Chain |
|----------|--------------|-------|-------|
| `/api/v1/meteo` | `0.01` | USDC | Solana mainnet |
| `/api/v1/fx` | `0.02` | USDC | Solana mainnet |
| `/api/v1/transit` | `0.02` | USDC | Solana mainnet |
| `/api/v1/news` | `0.02` | USDC | Solana mainnet |
| `/api/v1/stocks` | `0.05` | USDC | Solana mainnet |
| `/api/v1/github-stats` | `0.02` | USDC | Solana mainnet |

### Bulk pack (pre-pay 10 calls, 20% discount)

- **Price**: `0.08 USDC`
- **Calls**: `10` (any mix of endpoints)
- **TTL**: 24 hours

### Monthly subscription (heavy users)

- **Price**: `50.00 USDC` pre-pay
- **Calls**: `10,000` (any mix of endpoints)
- **TTL**: 30 days
- **Effective price per call**: `0.005 USDC` (75% off single-call)

**Ethical cap**: `120.00 USD` rolling 30-day earnings. Auto-pauses when reached.

---

## 💳 Payment spec

| Field | Value |
|-------|-------|
| Protocol | x402 / HTTP 402 Payment Required |
| Chain | Solana mainnet-beta |
| Asset | USDC (SPL Token) |
| Mint | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| Decimals | 6 |
| Pay-to wallet | `7Mby3eZUCxuRkYd3gL89HyVciYaGqKLKQ26jDsLXzi6Q` |
| Replay window | 300 seconds (5 min) from tx blockTime |
| Signature dedup | 1 hour TTL |

---

## 🛰 Endpoints

### 1. `/api/v1/meteo` — Clean weather data

Source: Open-Meteo (ERA5 historical + forecast). LLM-normalised to 5-field schema.

| Param | Type | Required | Default | Range | Example |
|-------|------|----------|---------|-------|---------|
| `q` | string | no | `Roma` | any city name | `Milano`, `New York` |
| `days` | int | no | `7` | 1-30 | `1`, `3`, `14`, `30` |

### 2. `/api/v1/fx` — Clean FX rates

Source: ECB GESMES XML. Cross-rates + trend + natural-language summary.

| Param | Type | Required | Default | Range | Example |
|-------|------|----------|---------|-------|---------|
| `base` | string | no | `EUR` | ISO 4217 | `EUR`, `USD` |
| `target` | string | no | `USD` | ISO 4217 | `JPY`, `GBP` |
| `days` | int | no | `1` | 1-90 | `1`, `7`, `30`, `90` |

### 3. `/api/v1/transit` — Real-time transit

Source: Wiener Linien Vienna monitor (or any custom JSON feed via `feed=`).

| Param | Type | Required | Default | Example |
|-------|------|----------|---------|---------|
| `stop` | string | no | `4205` (Karlsplatz Vienna) | `4211` |
| `feed` | string | no | Wiener Linien | any JSON transit feed URL |

### 4. `/api/v1/news` — Aggregated tech news

Source: Hacker News public API.

| Param | Type | Required | Default | Range | Example |
|-------|------|----------|---------|-------|---------|
| `n` | int | no | `10` | 1-30 | `5`, `15`, `30` |
| `theme` | string | no | `""` (all) | case-insensitive match | `AI`, `crypto`, `rust` |

### 5. `/api/v1/stocks` — Stock price + summary

Source: Yahoo Finance public (no API key required).

| Param | Type | Required | Default | Range | Example |
|-------|------|----------|---------|-------|---------|
| `symbol` | string | no | `AAPL` | any ticker | `MSFT`, `TSLA`, `BTC-USD` |
| `range` | string | no | `5d` | `1d`,`5d`,`1mo`,`3mo`,`6mo`,`1y` | `1mo` |

### 6. `/api/v1/github-stats` — Repo health snapshot

Source: GitHub public REST API.

| Param | Type | Required | Default | Example |
|-------|------|----------|---------|---------|
| `owner` | string | no | `facebook` | `microsoft`, `torvalds` |
| `repo` | string | no | `react` | `vscode`, `linux` |

---

## 📦 Bulk & subscription endpoints

### `/bulk/purchase`

Pay `0.08 USDC`, receive a token valid for `10` calls on any data endpoint.

### `/subscription/purchase`

Pay `50.00 USDC`, receive a token valid for `10,000` calls over 30 days.

---

## 🐍 Python Client

Install the official Python client:

```bash
pip install the-factory-client
```

Quick start:

```python
from the_factory_client import Factory

f = Factory(private_key_base58="your_solana_private_key")
weather = f.get("/api/v1/meteo", params={"q": "Milano", "days": 3})
```

The client handles payment automatically — no manual tx signing, no base64
encoding. One-line API calls.

Buy bulk packs or subscriptions programmatically:

```python
bulk = f.purchase_bulk()       # 10 calls for 0.08 USDC
sub = f.purchase_subscription() # 10k calls for 50 USDC
```

Source: https://github.com/Factorial2026/the-factory/tree/main/client_package

---

## 🦜 LangChain Integration

Install the official LangChain Tool:

```bash
pip install langchain-the-factory
```

Use in any LangChain agent:

```python
from langchain_the_factory import FactoryToolkit

toolkit = FactoryToolkit(private_key_base58="...")
tools = toolkit.get_tools()  # 6 tools, one per endpoint

# Use with any LangChain agent
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
```

Source: https://github.com/Factorial2026/the-factory/tree/main/langchain_tool

---

## 🔄 Request flow (3 modes)

### Mode A — Single call

```bash
# 1. Discover price
curl -i "https://the-factory-9ja4.onrender.com/api/v1/meteo?q=Milano"
# → 402 with challenge

# 2. Pay 0.01 USDC to wallet, capture signature

# 3. Retry with X-Payment header
SIGNATURE="5uEd4aESeMv5..."
X_PAYMENT=$(echo -n "{\"signature\":\"$SIGNATURE\"}" | base64 -w 0)
curl -i "https://the-factory-9ja4.onrender.com/api/v1/meteo?q=Milano" \
  -H "X-Payment: $X_PAYMENT"
# → 200 + X-Payment-Response receipt
```

### Mode B — Bulk pack

```bash
# 1. Purchase pack
curl -i "https://the-factory-9ja4.onrender.com/bulk/purchase"
# → 402, pay 0.08 USDC, retry with signature → receive token

# 2. Use token for 10 calls (any endpoints)
TOKEN="bulk_abc123..."
X_PAYMENT=$(echo -n "{\"token\":\"$TOKEN\"}" | base64 -w 0)
curl -i "https://the-factory-9ja4.onrender.com/api/v1/meteo?q=Roma" \
  -H "X-Payment: $X_PAYMENT"
```

### Mode C — Subscription

Same as Mode B but on `/subscription/purchase` with `50.00 USDC`. Token starts
with `sub_` and gives `10,000` calls over 30 days.

---

## ❌ Error responses

| HTTP | error | reason | Meaning |
|------|-------|--------|---------|
| 402 | `payment_required` | — | No `X-Payment` header. Pay and retry. |
| 402 | `payment_verification_failed` | `signature_already_used` | Tx consumed; pay again. |
| 402 | `payment_verification_failed` | `expired (Ns old)` | Tx older than 5 min. |
| 402 | `payment_verification_failed` | `insufficient: paid X < required Y` | Wrong amount. |
| 402 | `payment_verification_failed` | `rpc_unavailable_or_tx_not_found` | RPC down or tx not confirmed. |
| 402 | `bulk_token_invalid_or_exhausted` | — | Token used up or expired. |
| 402 | `subscription_token_invalid_or_exhausted` | — | Token used up or expired. |
| 400 | `invalid_payment_header` | — | `X-Payment` is not valid base64 JSON. |
| 400 | `missing_signature` | — | JSON parsed but no `signature` / `token` field. |
| 403 | `monthly_cap_reached` | — | Service paused; wait for window to drop. |
| 404 | `city_not_found` / `pair_not_available` / `repo_not_found` / `symbol_not_found` | — | Bad query param. |
| 502 | `feed_fetch_failed` | — | Upstream data source down. |

---

## 📊 Live Dashboard

Visit `https://the-factory-9ja4.onrender.com/dashboard` for:

- Earned (30d) vs monthly cap progress bar
- Calls (24h) and (7d) counts
- Revenue (24h) and (7d)
- Cache hit rate (24h)
- Endpoint usage bar chart (last 7 days)
- Pricing & plans table
- Wallet address

Stats refresh every 30 seconds. No auth required.

JSON alternative: `https://the-factory-9ja4.onrender.com/stats`

---

## ⚙️ Performance characteristics

- **Cache**: identical queries served from cache (1h TTL). `X-Cache: HIT` / `MISS` header reveals it.
- **LLM throughput**: ~12 RPM Gemini primary, ~24 RPM Groq fallback. Auto-failover on 429.
- **Cold start**: ~5-10 seconds (Render free tier). Cron-kept-warm.
- **Concurrency**: 1 worker. Suitable for ~5-10 concurrent clients.

---

## 🧠 For AI agents (machine-readable summary)

```yaml
service: The Factory v3
base_url: https://the-factory-9ja4.onrender.com
protocol: x402
pricing:
  meteo: 0.01 USDC
  fx: 0.02 USDC
  transit: 0.02 USDC
  news: 0.02 USDC
  stocks: 0.05 USDC
  github_stats: 0.02 USDC
  bulk_pack: {calls: 10, price: 0.08 USDC, ttl: 24h}
  subscription: {calls: 10000, price: 50.00 USDC, ttl: 30d}
payment:
  chain: solana-mainnet
  asset: USDC
  mint: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
  decimals: 6
  pay_to: 7Mby3eZUCxruRkYd3gL89HyVciYaGqKLKQ26jDsLXzi6Q
  window_seconds: 300
endpoints:
  - path: /api/v1/meteo
    params: {q: {default: Roma}, days: {default: 7, min: 1, max: 30}}
  - path: /api/v1/fx
    params: {base: {default: EUR}, target: {default: USD}, days: {default: 1, min: 1, max: 90}}
  - path: /api/v1/transit
    params: {stop: {default: "4205"}, feed: {optional: true}}
  - path: /api/v1/news
    params: {n: {default: 10, min: 1, max: 30}, theme: {default: ""}}
  - path: /api/v1/stocks
    params: {symbol: {default: AAPL}, range: {default: 5d}}
  - path: /api/v1/github-stats
    params: {owner: {default: facebook}, repo: {default: react}}
billing:
  - path: /bulk/purchase
  - path: /subscription/purchase
extras:
  - /dashboard
  - /stats
  - /docs
client_libraries:
  python: pip install the-factory-client
  langchain: pip install langchain-the-factory
auth: none
signup: none
```

---

**Built on the x402 protocol. Powered by free tiers. Capped for ethics.**
