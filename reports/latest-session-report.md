# Session report — Cross-listing Milestone 1: eBay Sell API publish path (SANDBOX ONLY)

**Date:** 2026-09-22 · **Scope:** brief `~/workspace/crtc-audit/claude-code-crosslist-brief-2026-09-22.md`
**Status:** all six deliverables landed. Nothing committed (per constraints — working tree is dirty by design).

## Files created / changed

| File | Change |
| --- | --- |
| `ebay_sell.py` | **New** (~470 lines). OAuth2 authorization-code flow + sandbox Sell/Inventory client + pure mapping functions. |
| `pages/5_🔗_Cross_List.py` | **Modified.** Added a "PUBLISH TO EBAY (SANDBOX)" action on `READY_TO_PUBLISH` eBay drafts; one import line; published IDs shown on the card; updated the closing caption. Everything else on the page is untouched. |
| `tests/test_ebay_sell.py` | **New.** 31 tests, all HTTP mocked, no network, no credentials needed. |
| `docs/EBAY_SELL_SETUP.md` | **New.** Owner's key setup + the exact manual sandbox test script. |
| `reports/latest-session-report.md` | **New** (this file); `reports/` created. |

Not touched, as required: `finance.py`, `comps.py`, `decision_policy.py`, `auction_costs.py`,
`deal_settings.py`, `listing_store.py`, `comps_adapters.py`, `ebay_holy_grail.py`, `ebay_image_scan.py`.

## Design decisions (as directed)

- **No new `PUBLISHED` status.** `listing_store.py` is unchanged. A successful publish is
  `transition_listing(draft, "ACTIVE", external_id=<eBay listingId>)` — `READY_TO_PUBLISH → ACTIVE`
  was already legal and `ACTIVE` already means live-on-marketplace. The `offerId` is stored
  alongside as `ebay_offer_id` (plus `ebay_environment: "sandbox"`) so cleanup/withdraw is possible.
- **`EBAY_SELL_*` env prefix**, read via `os.environ`, with an untracked `ebay_config.json` fallback.
  Kept deliberately separate from the Browse-API `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` in
  `comps_adapters.py` — different eBay app, different scopes, sandbox vs production keys.
  A test asserts the Browse keys cannot leak into the Sell config.
- **Sandbox is not configurable.** `AUTHORIZE_URL`, `TOKEN_URL`, and `INVENTORY_BASE` are hardcoded
  `*.sandbox.ebay.com` constants. There is no env var that flips to production, so no
  misconfiguration can post a real listing. A test asserts every request URL is a sandbox URL.
- **Secrets never logged.** `EbayConfig.__repr__` renders `client_secret=set|unset`, never the value;
  API errors are rendered through `_error_summary()` which extracts only eBay's errorId/message.
  Two tests cover this. `.ebay_tokens.json` is written `chmod 600`. No secret files were created
  in the tree; `.gitignore` already covers all three paths.

## What was built

**Auth** — `get_authorization_url()`, `exchange_code_for_tokens()`, `refresh_access_token()`,
`get_valid_access_token()` (refreshes at expiry with a 120s skew), `is_authorized()`,
token persistence to untracked `.ebay_tokens.json`. Refresh responses omit `refresh_token`;
the stored one is carried forward rather than lost.

**Inventory client** — `create_or_replace_inventory_item`, `create_offer` (FIXED_PRICE),
`publish_offer`, `get_offer_status`, `withdraw_offer`, plus `get_inventory_item`,
`find_offer_id`, `update_offer`.

**Mapping** — `master_to_inventory_item(master)` and `master_to_offer(master, config)` are pure,
do no I/O, and need no credentials. Title truncated to eBay's 80 chars; free-text condition mapped
onto eBay condition enums with a `USED_GOOD` default; weight/dimensions omitted entirely when absent
rather than sent as zeros (eBay rejects zeros); images capped at eBay's 12.

**End-to-end** — `publish_master(master)`: auth → inventory item → offer → publish → `listingId`.
Re-publishing an existing SKU updates the existing offer instead of failing with a duplicate.

**UI behavior** — the button appears only on eBay drafts in `READY_TO_PUBLISH`. On success: draft
goes `ACTIVE` with the listing ID, success message. On any `EbaySellError`: the error is shown via
the page's existing message channel and **the draft state is unchanged** — still `READY_TO_PUBLISH`,
safe to retry. When no token file exists the page shows a caption pointing at the setup doc.

## Test results

```
tests/test_ebay_sell.py .............................  31 passed in 0.21s
```

Full suite, no regressions:

```
289 passed in 0.85s
```

8 test modules could not be collected — `test_auth`, `test_billing`, `test_comps_adapters`,
`test_ebay_image_scan`, `test_opportunity_sources`, `test_pos`, `test_storage`,
`test_stripe_webhook_server`. **These are pre-existing and unrelated to this work:** they fail at
import on missing third-party packages (e.g. `fastapi`) that are not installed in this container,
and none of them import anything I changed. They were excluded from the 289-test run above.

Environment note: this container has no `pytest` and PEP-668-blocks `pip install`. I ran the suite
from a throwaway venv at `/tmp/crtcvenv` (`python3 -m venv --system-site-packages` + `pip install pytest`).
Nothing was installed into the project or the system Python; the repo is unchanged by this.

## What needs the owner's eBay developer keys

Everything above is verified by mocked tests. **Nothing has been run against eBay's live sandbox** —
that needs credentials I don't have. To finish verification, the owner needs to:

1. Create a sandbox keyset at developer.ebay.com → `EBAY_SELL_CLIENT_ID`, `EBAY_SELL_CLIENT_SECRET`.
2. Add a redirect URL and copy the generated **RuName** → `EBAY_SELL_REDIRECT_URI`
   (the RuName, not the URL — this is the most common setup mistake).
3. Create a sandbox **test user**, opt it into Business Policies, and create payment / fulfillment /
   return policies → three `*_POLICY_ID` vars.
4. Create a merchant location → `EBAY_SELL_MERCHANT_LOCATION_KEY`.
5. Run the one-time browser authorization (step 4 of the setup doc).

Full instructions, the exact commands, and a troubleshooting table are in `docs/EBAY_SELL_SETUP.md`.

## Unfinished / known limitations

- **No live sandbox round-trip yet.** The happy path is proven against mocks only. The first real
  run may surface eBay-specific rejections (category requirements, item-specifics, location setup).
  Expect one debugging pass once keys exist.
- **`categoryId` is only sent if the master record has `ebay_category_id`.** Nothing in the app sets
  that field today. eBay can often infer a category, but for some items publish will fail asking for
  one. Category selection is a reasonable next milestone.
- **No item-specifics / aspects.** Some categories require them and will reject a publish without them.
- **No merchant-location bootstrap.** The location must be created manually (or via a separate API
  call); `ebay_sell.py` reads the key but does not create the location.
- **Only eBay publishes.** Etsy/Mercari/Poshmark/Depop/Facebook drafts still stop at
  `READY_TO_PUBLISH`, unchanged from before.
- **Production path deliberately absent**, per the milestone constraint.
- **Nothing committed**, per the constraints: no commits, no pushes, no branches. The four
  new/changed files are sitting in the working tree for review.
