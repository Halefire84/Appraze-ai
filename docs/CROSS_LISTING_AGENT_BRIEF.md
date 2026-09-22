# Cross-listing AI agent — implementation brief

Date: 2026-09-22. Decision by Chris Hale.

## What this is

Appraze ships an in-app AI listing agent — the "Starship pattern": a model-driven
browser that logs into the user's marketplace accounts and publishes their
listings, the way a human VA would. This is in addition to official APIs where
they exist, not instead of them.

Plain-English architecture: the backend calls an AI model API; the model drives
a real headless browser (Playwright); the user's marketplace logins live in an
encrypted per-user vault. It is not "copy-paste Muse" — it is model API +
browser automation + credential custody, running as a backend service (not in
the Streamlit UI thread).

## Phases

- **Phase 1 — done 2026-09-22:** eBay Sell API sandbox publish path
  (`ebay_sell.py`). Official API, no browser needed.
- **Phase 2:** Etsy official API for listings. Same pattern as eBay: OAuth,
  server-to-server, no browser.
- **Phase 3:** In-app browser agent for Poshmark, Mercari, Depop, Facebook
  Marketplace. No public APIs exist for these — the agent is the only way to
  post programmatically.

## Phase 3 requirements

- **Agent loop:** model API + Playwright + tool calls (navigate, fill, click,
  screenshot, read). Long-running runs live server-side, never in the
  Streamlit session.
- **Credential vault:** marketplace logins stored encrypted, per user. Never in
  chat, logs, or error messages. User grants access per site; revocable.
- **Human-in-the-loop:** user approves each publish (or sets standing approval
  per marketplace). On CAPTCHA / bot challenge the agent stops and hands back
  to the user — it never auto-solves, never sneaks past.
- **Session persistence:** logged-in sessions cached per user per marketplace;
  re-login only on expiry.
- **Breakage detection:** marketplaces redesign constantly. The agent must
  detect "this page doesn't match the expected flow," abort safely without
  posting garbage, and flag the flow for re-mapping. Keep per-marketplace
  selectors/flows in config, not hardcoded.
- **Fallback:** assisted posting (app pre-fills everything, opens the page,
  user clicks publish) whenever automation is broken, blocked, or the user
  prefers it.
- **Delist tracker:** when an item sells on one marketplace, delist or update it
  on the others. (Already planned scope.)

## Accepted risks — Chris's call, 2026-09-22

- **ToS gray zone.** Poshmark, Mercari, Depop, and Facebook prohibit automated
  posting. Accounts can be flagged or banned. The app must disclose this
  plainly before a user connects an account. Never promise "ban-proof."
- **Credential custody.** The app becomes a password vault. Encryption at rest,
  minimal data retention, never log credentials, have a breach plan.
- **Cost.** Every agent-run listing burns model tokens. Meter cost per listing
  and price it into the subscription tiers. Beta: cap agent runs per user.
- **Maintenance.** Budget ongoing re-mapping work as marketplaces change their
  pages. This is a living feature, not ship-and-forget.

## Non-goals

- No reverse-engineered private/mobile APIs.
- No production eBay publishing until the sandbox proof sequence is complete
  (separate checklist in `docs/EBAY_SELL_SETUP.md`).
- The agent never invents listing content; it publishes the user's master
  listing drafts verbatim.

## Acceptance criteria (Phase 3)

1. User connects a Poshmark (or Mercari) account via the vault, approves a
   publish, agent posts the draft, returns the live listing URL.
2. CAPTCHA / bot challenge mid-run → agent stops, hands to user, nothing
   posted, no silent bypass.
3. Simulated marketplace redesign → agent aborts safely and flags for
   re-mapping instead of posting garbage.
