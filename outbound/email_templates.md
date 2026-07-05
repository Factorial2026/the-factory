# Email Templates — B2B Outbound for The Factory

3 templates, in order of use:

- **A. Cold intro** — first contact, 120 words, plain text, no fluff
- **B. Follow-up** — 4 business days after A, 80 words
- **C. Technical deep-dive** — when they reply and want to talk

All templates are plain text. No HTML, no images, no attachments. Plain text
emails have 2x reply rate vs HTML in B2B cold outreach (Mailshake 2024 study).

---

## Template A — Cold Intro

**Subject line options** (pick one, A/B test across batches):

1. `Quick question about [Company]'s [weather / FX / transit] data`
2. `Clean JSON API for [weather / FX / transit] — pay per call, no API keys`
3. `[Company] + clean data API — 30 sec eval`

**Body** (replace `[bracketed]` parts):

```
Hi [First Name],

I noticed [Company] uses [FX rates / weather data / real-time transit] in
[specific feature — e.g. "your cross-border pricing module"]. Most teams I've
talked to in [their industry] are paying $200-500/mo to RapidAPI or maintaining
custom parsers for ECB XML / Open-Meteo WMO codes / Wiener Linien feeds.

I built a small HTTP API that returns clean JSON for 6 endpoints (weather, FX,
transit, news, stocks, GitHub stats) — pay per call ($0.01-0.05) via the x402
HTTP 402 protocol. No API keys, no signup, no monthly tier.

For a team like yours doing ~[realistic number, e.g. 5000] data calls/mo, the
subscription is $50 flat. That's roughly 10x cheaper than RapidAPI for the same
volume.

Live to test (no signup): https://the-factory-9ja4.onrender.com/api/v1/fx?base=EUR&target=USD&days=7
Docs: https://github.com/Factorial2026/the-factory/blob/main/SHOWCASE.md

Worth a 15-min call next week? I'm free Tue/Thu afternoon CET.

— [Your Name]
[Optional: link to your LinkedIn]
```

**Notes**:
- Replace `[specific feature]` with something genuinely observed on their site
  ("I noticed [Company] uses FX rates in your cross-border pricing module")
  → shows you actually looked, not blast emailing.
- `[realistic number]` should be defensible: 5000 calls/mo for a mid-team is
  reasonable. Don't go too high (suspicious) or too low (not interesting).
- Always end with a specific call-to-action ("Tue/Thu afternoon CET"), not
  "let me know if interested".

---

## Template B — Follow-up (4 business days later)

**Subject**: `re: [original subject line]`

**Body**:

```
Hi [First Name],

Floating this back to the top of your inbox — wanted to make sure you saw it.

If it's not a priority right now, no problem. Just reply "not now" and I'll
stop following up.

If you want to try it: the subscription is $50/mo for 10,000 calls, no commitment.
First call is $0.01 if you want to test pay-per-call mode first.

Live: https://the-factory-9ja4.onrender.com/docs

— [Your Name]
```

**Notes**:
- The "I'll stop following up" line is a known reply-rate booster (~30% lift).
  It gives the recipient permission to say no, which feels respectful.
- One follow-up only. After this, mark as "no reply" in tracking CSV and move on.

---

## Template C — Technical Deep-Dive (when they reply)

**Subject**: `re: [original subject]`

**Body**:

```
Hi [First Name],

Thanks for the reply — appreciate you taking a look.

Quick technical context so you can decide if it's worth a call:

Architecture:
- 6 endpoints (meteo, fx, transit, news, stocks, github-stats)
- Each fetches raw upstream API (Open-Meteo, ECB, Wiener Linien, HN, Yahoo, GitHub)
- LLM (Gemini + Groq fallback) cleans to flat JSON schema
- Response cache (1h TTL) — identical queries = 0 LLM calls
- x402 protocol: HTTP 402 + USDC on Solana, no API keys, no signup

Payment modes:
- Pay-per-call: $0.01-0.05 per call, sliding scale by endpoint
- Bulk pack: 10 calls for $0.08 (20% off)
- Subscription: 10,000 calls for $50/mo (75% off)

Integration:
- HTTP GET with X-Payment header (base64-encoded JSON)
- Python client: pip install the-factory-client (when published on PyPI)
- LangChain Tool available for agent integration

Honest caveats:
- Hard-coded ethical cap at $120/mo rolling 30-day. If we hit it, service pauses
  until window clears. Not a SaaS — proof-of-concept for AI agent micropayments.
- Free-tier hosting (Render) — cold start ~5s on first call after 15min idle.
- 1 worker, suitable for ~5-10 concurrent clients. Not for production-critical
  high-volume pipelines.

15-min call options:
- Tue 14:00 CET
- Wed 10:00 CET
- Thu 16:00 CET

Reply with a slot that works, or grab any time here: [your Calendly link if you have one]

— [Your Name]
```

**Notes**:
- The "Honest caveats" section is critical. Tech buyers smell marketing bullshit
  from a mile away. Admitting the limitations up front builds trust.
- Calendly free tier is fine if you don't have one — just use the time slots.
- 15 minutes max. Don't accept 30-min or 1-hour calls for $50/mo subscription
  — you'll burn out.

---

## Sending rules

1. **Volume**: max 5 emails per day, max 25 per week. Going higher triggers
   ProtonMail spam filters.
2. **Personalization**: every email must have at least 1 line that's specific
   to the company. "I noticed [Company] uses X" — verified by visiting their
   site for 30 seconds.
3. **Sender signature**: keep it minimal. Name + optional LinkedIn. No banner
   images, no marketing taglines, no "Founder & CEO" title.
4. **Sending time**: Tuesday 10am CET for EU targets, Tuesday 9am ET for US
   targets. Monday is inbox-cleanup day. Friday afternoon is dead.
5. **From address**: use your ProtonMail (TheFactorial@proton.me). Don't use
   a "founder@the-factory.com" alias — feels corporate and sketchy for a
   side project.

---

## Tracking template (copy to a spreadsheet)

| Date sent | Company | Contact name | Email | Template | Reply? | Reply date | Outcome |
|-----------|---------|--------------|-------|----------|--------|------------|---------|
| 2026-07-10 | Stuart | Jane Doe | jane@stuart.com | A | no | - | - |
| 2026-07-10 | Packeta | - | info@packeta.com | A | - | - | - |

Track every email. After 30 emails sent, look at the data: which category had
the highest reply rate? Double down on that category for the next batch.
