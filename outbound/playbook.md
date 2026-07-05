# B2B Outbound Playbook — The Factory

> Realistic goal: send 30 cold emails over 6 weeks. Get 1-3 replies. Convert
> 0-1 to paying $50/mo subscription. Total time investment: ~6 hours.

## Phase 1 — Preparation (1 hour)

### 1.1 Set up tracking
1. Open the `tracking_template.csv` file in Excel/Google Sheets.
2. Save a copy as `the_factory_outbound_tracking.xlsx` (or keep CSV).
3. Add a column "batch_number" — you'll send in batches of 5.

### 1.2 Pick the first 5 targets
Open `target_list.md`. From the 30 companies, pick 5 that:
- Are most likely to need FX data (cross-border e-commerce is highest signal)
- Have a public email or LinkedIn-findable founder
- Are NOT competitors you'd want to avoid (e.g. don't email RapidAPI)

Recommended first batch (cross-border e-commerce focus):
1. Tweak Exchange
2. Lengow
3. Channable
4. Linnworks
5. Productsup

### 1.3 Find contact emails (15-20 min per company)
For each company:
1. Visit their "About" / "Team" page. Find Head of Engineering / CTO / VP Eng.
2. Search LinkedIn: `[company] "head of engineering"` — usually 1-3 candidates.
3. Guess the email format using one of:
   - `firstname@company.com`
   - `firstname.lastname@company.com`
   - `firstinitial@company.com` (e.g. `jdoe@company.com`)
4. Verify with a free tool: https://hunter.io/email-verifier (10 free checks/mo)
   OR https://tools.verifyemailaddress.io (unlimited free).

If you can't find a personal email after 15 min, use the company contact form
with the same template (slight adaptation: "Hi team" instead of "Hi [Name]").

## Phase 2 — Sending (1 hour per batch of 5)

### 2.1 Compose in ProtonMail
1. Log in to ProtonMail (https://mail.proton.me).
2. Click "New message".
3. **From**: TheFactorial@proton.me
4. **To**: the verified contact email
5. **Subject**: pick one of the 3 options from template A
6. **Body**: paste template A, replace all `[bracketed]` parts.
7. Read aloud once. If anything sounds robotic or generic, rewrite it.

### 2.2 Send rules
- Send **one email at a time**, with 10-15 min gaps between them.
- **Max 5 emails per day.** Going higher triggers spam filters.
- **Send between Tuesday 10:00 and Wednesday 16:00 CET**. Monday is inbox-cleanup
  day (your email gets archived). Friday afternoon is dead.
- **Use plain text** (no rich text formatting, no bold/italic). In ProtonMail
  composer: click the "Aa" icon → "Plain text".

### 2.3 Track immediately
After sending each email, fill a row in your tracking spreadsheet:
- date_sent, company, contact_name, email, template_used=A, reply_received=no

## Phase 3 — Follow-up (1 hour, 4 business days later)

For each email in the batch where `reply_received = no`:
1. Reply to your own sent email (preserves subject line as "re: ...").
2. Paste template B body.
3. Replace `[First Name]`.
4. Send.

In tracking spreadsheet, add a note "follow-up sent on [date]" in the notes column.

## Phase 4 — Handling replies (variable)

### Reply type A: "Not interested" / "No thanks"
- Reply with: "Got it, thanks for the reply. Won't follow up again. Good luck
  with [their project]."
- Mark in spreadsheet: outcome = "not_interested".
- Move on. Don't argue.

### Reply type B: "Tell me more" / "How does it work?"
- Reply with template C (technical deep-dive).
- Offer 2-3 specific time slots for a 15-min call.
- Mark in spreadsheet: outcome = "engaged, sent template C".

### Reply type C: "Send me pricing" / "Send me a quote"
- Reply with the pricing summary from SHOWCASE.md.
- Be explicit: "Subscription is $50/mo for 10,000 calls, no commitment, cancel
  anytime (just stop paying)."
- Mention: "If you want a custom enterprise plan (higher volume, SLA, dedicated
  support), I can scope one — but for 95% of teams the $50/mo plan is enough."
- Mark in spreadsheet: outcome = "pricing_sent".

### Reply type D: "Let's hop on a call"
- Pick the earliest slot you can do.
- Use Google Meet (free, no time limit). Don't use Zoom (40-min limit on free).
- Prepare for the call: have the SHOWCASE open, have the /health endpoint open,
  have a test payment ready to demo.

## Phase 5 — Conversion (post-call)

If the call goes well:
1. Send a recap email within 2 hours: "Great chatting. As discussed, here's the
   subscription link: [link to /subscription/purchase on your service]. Pay $50
   USDC, you'll receive a token in the response. Use the token as
   `X-Payment: base64({token:...})` on any endpoint for the next 10,000 calls."
2. Offer to help with integration (provide the Python client package).
3. If they pay, mark in spreadsheet: outcome = "CONVERTED 🎉". Add a column
   for "MRR" = $50.

If they don't pay after 1 week, send ONE final email: "Hey, no pressure — wanted
to check if you had any questions about the subscription. If it's not the right
fit, totally understand."

## Phase 6 — Analyze & iterate (after 30 emails sent)

Open your tracking spreadsheet. Calculate:

- **Reply rate** by company category (logistics, e-commerce, fintech, etc.)
- **Reply rate** by template subject line
- **Reply rate** by sender time of day

Double down on whatever's working. If logistics has 30% reply rate and fintech
has 0%, send the next 30 emails only to logistics. If template subject line 2
has 3x the reply rate of line 1, use line 2 for the next batch.

## Realistic expectations

| Metric | Range |
|--------|-------|
| Emails sent (6 weeks total) | 30 |
| Reply rate (target) | 10-15% = 3-5 replies |
| Reply rate (realistic) | 5-10% = 1-3 replies |
| Calls booked | 1-2 |
| Conversions to $50/mo subscription | 0-1 |
| Conversion to bulk pack (lower commitment) | 0-1 |

**Honest math**: 6 hours of work for a 30% chance of $50/mo recurring = expected
value ~$15/mo. Not amazing, but the learnings + portfolio + reference customer
are worth more than the $50.

If you get 0 conversions after 30 emails, it's not because the product is bad —
it's because:
1. The target list was wrong (wrong company stage, wrong industry)
2. The pitch was wrong (too technical, or too generic)
3. The price was wrong (try $20/mo for 5,000 calls in next batch)

Pivot and try again with a different list / pitch / price.

## Anti-patterns (do NOT do these)

- ❌ Email all 30 targets in one day → spam filter death
- ❌ Send follow-up #3 ("just bumping this") → desperate, kills credibility
- ❌ Use HTML email with banner image → looks like marketing, deleted instantly
- ❌ Send on Monday morning → your email is in the bottom 20 of an inbox of 80
- ❌ Email the CEO of a 500-person company → too high, gets filtered by EA
- ❌ Email `info@company.com` and hope → 99% ignored, 1% auto-replied
- ❌ Pitch "AI" or "blockchain" in subject line → instant delete in 2026
- ❌ Offer "free trial" or "money-back guarantee" → signals lack of confidence

## If you want to outsource

If you don't have time for outbound but have $200-300 to spare:
- **Lemlist** (https://lemlist.com) — cold email automation, $59/mo, includes
  email finder. Quality is decent.
- **Apollo.io** (https://apollo.io) — bigger database, ~$49/mo, has free tier
  with 50 emails/mo.

But honestly, manual outreach with personalized emails beats automated blast
every time. The 6 hours of manual work will outperform $300 of automation.
