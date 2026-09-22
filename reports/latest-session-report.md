# Session report — eBay sandbox publish round-trip proof

**Date:** 2026-09-22 · **Scope:** brief "APPRAZE — Claude Code brief: eBay SANDBOX publish
round-trip proof" · **Branch:** `claude/beta-launch-sprint` (open as PR #29 at time of writing)

**Status: code deliverables complete and tested (mocked). The live sandbox round-trip has
NOT been executed — no real eBay sandbox credentials or a completed OAuth authorization exist
anywhere accessible to this session. This is stated plainly rather than worked around, per the
brief's own instruction: "Do not invent policy IDs, listing IDs, or status results. Report only
what the API actually returned."**

## What this session actually found first

The brief's "STATE OF THE WORLD (verified tonight, do not redo)" section claimed `ebay_sell.py`,
31 mocked tests, and authorized sandbox OAuth tokens already existed in this repository. Before
touching anything, this session searched the full git history (`git log --all`) and working tree
of this remote container for every file named in that section. **None of it existed here.** This
remote environment starts from a fresh clone every session; work done in a different (local)
Claude Code session is invisible to it unless committed and pushed, or otherwise transferred in.

The user then uploaded a git bundle (`crtc-work-2026-09-22.bundle`) containing that other
session's actual commits. Before importing anything from it, this session:
- Ran `git bundle verify` and inspected every commit's file list and diff.
- Grepped the bundle's full history for anything token/secret-shaped — confirmed
  `.ebay_tokens.json` and `ebay_config.json` were added to `.gitignore` in that session's first
  commit, *before* `ebay_sell.py` was ever created, and neither file was ever actually committed.
- Re-ran all 31 imported tests in this environment (they passed here too, not just in the
  original session's report).
- Read that session's own `reports/latest-session-report.md` (bundled), which already stated
  honestly: *"Nothing has been run against eBay's live sandbox... No merchant-location
  bootstrap. The location must be created manually... `ebay_sell.py` reads the key but does not
  create the location."* This matches exactly what tonight's brief asked to be built next.

The bundled `pages/5_🔗_Cross_List.py` diff was **not** applied wholesale — that other session's
snapshot predated this repo's existing production eBay integration (`ebay_listing.py`, built in
an earlier session on *this* remote container, with a full OAuth-connect UI already wired into
that same page). The bundle's sandbox-publish button was manually merged in as a second, clearly
labeled, independently-gated path ("PUBLISH TO EBAY (SANDBOX TEST)") alongside the existing
production one, rather than overwriting it.

## Files created / changed this session

| File | Change |
| --- | --- |
| `ebay_sell.py` | Imported from the bundle (638 lines: OAuth2 flow, sandbox Inventory client, pure mapping functions), then extended (+310 lines) with the policy/location builders below. |
| `tests/test_ebay_sell.py` | Imported (31 tests), then extended (+18 tests) for the new builders. |
| `docs/EBAY_SELL_SETUP.md` | Imported, then updated: automated policy/location creation documented as the primary path, `sell.account` scope requirement noted, `sandbox_proof.py`'s exact run command and expected output added, troubleshooting table extended. |
| `pages/5_🔗_Cross_List.py` | Merged (not overwritten): added the sandbox-test publish path alongside the existing production one. |
| `.gitignore` | Added `.ebay_tokens.json`, `ebay_config.json`, `.env` (imported from the bundle's own commit). |
| `sandbox_proof.py` | **New.** Manual-only round-trip proof script (see below). |
| `reports/latest-session-report.md` | This file. |

Not touched, as required: `finance.py`, `comps.py`, `decision_policy.py`, `auction_costs.py`,
`deal_settings.py`, `listing_store.py`, `comps_adapters.py`, `ebay_holy_grail.py`,
`ebay_image_scan.py`.

## What was built new this session (not in the imported bundle)

**Policy/location builders in `ebay_sell.py`:**
- `create_payment_policy` / `create_fulfillment_policy` / `create_return_policy` (Sell Account
  API v1, new `ACCOUNT_BASE = https://api.sandbox.ebay.com/sell/account/v1` constant — sandbox
  only, same pattern as `INVENTORY_BASE`) and `create_merchant_location` (Sell Inventory API's
  `/location/{key}` endpoint).
- `list_payment_policies` / `list_fulfillment_policies` / `list_return_policies` /
  `list_merchant_locations` for the reuse-if-exists check.
- `get_or_create_payment_policy` / `get_or_create_fulfillment_policy` /
  `get_or_create_return_policy` / `get_or_create_merchant_location`: list first, match an
  existing policy by name (or location by key), create only when nothing matches.
- `ensure_sandbox_listing_prerequisites(client)`: runs all four, fills the resulting IDs into
  `EbayConfig`, persists them via the new `save_config()` to `ebay_config.json`.
- Added the `sell.account` OAuth scope to `DEFAULT_SCOPES` — the pre-existing
  `sell.inventory`/`sell.inventory.readonly` scopes do not cover policy/location creation.
  **This means any previously-authorized sandbox token — real or the brief's claimed one — would
  need re-authorization regardless of anything else in this session's work**, since a scope
  cannot be added to an existing token via refresh.

**`sandbox_proof.py`** (new, root of repo, manual-run-only — never imported by the app, a test,
or CI): authenticates from stored tokens (fails fast with a clear message if `.ebay_tokens.json`
has no refresh token — verified live in this session, see below); calls
`ensure_sandbox_listing_prerequisites`; builds a master dict for
`"SANDBOX TEST - DELETE ME - Appraze publish proof"` at $1.00, qty 1, condition NEW, category
`9355` (a real, documented eBay example category ID — see the citation in the script's own
comment — not verified against this specific sandbox account's category tree, overridable via
`--category-id`); publishes; polls `get_offer_status` every 5s up to 120s printing every observed
status; prints the Sandbox Seller Hub URL; withdraws in a `finally` block regardless of how the
try block exits; polls again until `ENDED`/`UNPUBLISHED`; exits nonzero on any failure — including
a withdraw failure *after* a successful publish, since the acceptance bar is publish AND
withdraw, not publish alone.

## What was actually run and verified in this session

```
$ python3 -m pytest -q
483 passed, 0 failed (465 prior in this repo + 18 new), 11 pre-existing unrelated
DeprecationWarnings from starlette/httpx2

$ flake8 --select=E9,F63,F7,F82 .
0 findings (this repo's CI-blocking lint gate)

$ git check-ignore -v .ebay_tokens.json ebay_config.json .env
all three matched by .gitignore

$ python3 sandbox_proof.py          # no real tokens present -- this IS the real environment
[sandbox_proof] FAILED: No eBay sandbox authorization found -- .ebay_tokens.json is missing or
has no refresh token. Run the one-time browser authorization first (docs/EBAY_SELL_SETUP.md,
step 4), then re-run this script.
exit code: 1

$ echo '{"access_token":"fake","refresh_token":"fake","expires_at":0}' > .ebay_tokens.json
$ python3 sandbox_proof.py
[sandbox_proof] FAILED: Missing eBay Sell credentials: EBAY_SELL_CLIENT_ID,
EBAY_SELL_CLIENT_SECRET, EBAY_SELL_REDIRECT_URI. See docs/EBAY_SELL_SETUP.md.
exit code: 1
$ rm -f .ebay_tokens.json   # cleanup; confirmed via git status that nothing was ever staged
```

Both of `sandbox_proof.py`'s fail-fast paths are real, observed behavior in this actual
environment, not asserted from reading the code. No fabricated token or config file was left
behind or committed.

## What still needs the owner's real eBay developer keys — nothing here can do this

**No live sandbox round-trip has been run. This session had no eBay sandbox Client ID/Secret, no
RuName, and no way to complete the interactive browser consent step** (which needs a human
signed into an eBay sandbox test-user account, clicking "Agree" in a real browser session against
eBay's own login/consent UI — not something achievable from a headless script or fabricated).

To actually complete the acceptance criterion, the account owner needs to, per
`docs/EBAY_SELL_SETUP.md`:
1. Create a sandbox developer keyset at developer.ebay.com → `EBAY_SELL_CLIENT_ID`,
   `EBAY_SELL_CLIENT_SECRET`.
2. Register a redirect and copy the generated **RuName** (not the URL) → `EBAY_SELL_REDIRECT_URI`.
3. Create a sandbox test user (do **not** opt policies in manually — `sandbox_proof.py` does
   that automatically now).
4. Run the one-time browser authorization (`docs/EBAY_SELL_SETUP.md` step 4) — this requests the
   `sell.account` scope in addition to the inventory scopes.
5. Run `python3 sandbox_proof.py` and paste its actual output — real listing ID, real offer ID,
   every real status transition with timestamps — into this file, replacing this section.

## Unfinished / known limitations, carried forward or new

- **No live sandbox round-trip yet** (repeated from the imported session's own report — still
  true; this session closed the "can't create policies/location" gap that blocked it, but
  couldn't supply the missing credentials or complete browser consent).
- **`create_payment_policy`/`create_fulfillment_policy`/`create_return_policy`/
  `create_merchant_location` request bodies are UNVERIFIED against a live sandbox call.** Built
  from eBay's published Sell Account API v1 schema; the first real run may surface a rejected
  field (eBay's Account API is known to be picky about e.g. `categoryTypes` naming or
  Managed-Payments-specific requirements per marketplace). Each function's docstring says this
  explicitly. A rejection surfaces as a full, unredacted eBay error message via the existing
  `_error_summary()` helper — never a guess, never swallowed.
- **Default test category (`9355`) is a documented example, not verified for this account's
  sandbox category tree.** `--category-id` overrides it.
- **Default merchant-location address is a placeholder** (`123 Sandbox Test Street, San Jose, CA
  95131, US`), overridable via `EBAY_SELL_LOCATION_*` env vars / `ebay_config.json`.
- **`sell.account` scope was just added.** Any token authorized before this change (the brief's
  claimed one included, had it existed here) needs re-authorization from scratch.
- **Only eBay publishes** (sandbox or production). Etsy/Mercari/Poshmark/Depop/Facebook drafts
  still stop at `READY_TO_PUBLISH`, unchanged.
- **Production path deliberately absent** — every endpoint in `ebay_sell.py` is a hardcoded
  `*.sandbox.ebay.com` constant; `tests/test_ebay_sell.py::test_account_base_is_sandbox_only` and
  the pre-existing sandbox-URL assertions pin this.
