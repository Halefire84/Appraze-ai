# Cross-listing scaffold — architecture notes

**Status: scaffold / Coming Soon. Nothing here publishes anything real.**

Branch: `crosslist/scaffold` (Halefire84/Appraze-ai). All work on this
branch is additive — `main`, the Android branch
(`codex/create-android-app-for-appraze`), and `app.py` billing/Stripe code
are untouched.

## What it is

One master listing adapted for six marketplaces:

| Marketplace | Mode | Status |
|---|---|---|
| eBay | official eBay Sell API | scaffold — payload built, wiring TODO |
| Etsy | official Etsy Open API v3 | scaffold — payload built, wiring TODO |
| Depop | partner API | **stub only** — awaiting partner-API approval |
| Poshmark | assisted publishing | payload + deep link + clipboard; human clicks publish |
| Mercari | assisted publishing | payload + deep link + clipboard; human clicks publish |
| Facebook Marketplace | assisted publishing | payload + deep link + clipboard; human clicks publish |

## Layout

```
crosslist/
  __init__.py   public API: flag, model, adapter base, registry
  config.py     APPRAZE_CROSSLIST feature flag (default OFF) + MARKETPLACES metadata
  models.py     MasterListing (title, description, price, photos, category,
                condition, shipping) + Condition enum + ShippingInfo
  base.py       MarketplaceAdapter ABC: format_listing / publish / delist
  ebay.py       eBay Sell Inventory API payloads (inventory item + offer)
  etsy.py       Etsy Open API v3 createListing body
  depop.py      stub — refuses everything until partner-API approval
  assisted.py   shared assisted-publishing framework
  poshmark.py   assisted adapter (condition labels, deep link, hashtags)
  mercari.py    assisted adapter
  facebook.py   assisted adapter
  registry.py   get_adapter / get_adapter_gated / list_marketplaces
  tracker.py    DelistTracker stub — records where each item was listed
tests/test_crosslist.py   16 offline tests (no network, no credentials)
```

## Feature flag

Everything that could publish is gated by the `APPRAZE_CROSSLIST`
environment variable (default OFF):

- Flag off: `publish()` / `delist()` raise `CrosslistDisabledError`.
- Flag on: each adapter still raises a clearly-marked
  `NotConfiguredError` until its integration is wired (eBay/Etsy), or
  `AssistedPublishRequiredError` by design (Poshmark/Mercari/Facebook),
  or `DepopNotAvailableError` (Depop).

`format_listing()` is pure/offline and always allowed — it only builds
payloads, never sends them.

## Done vs stubbed (honest list)

DONE:

- Common listing model with validation (`MasterListing`, `Condition`,
  `ShippingInfo`).
- Adapter interface (`format_listing` / `publish` / `delist`) with
  flag-guard defaults that refuse to go live.
- eBay: complete Sell Inventory API payload structure (inventory item +
  offer: product/title/condition/imageUrls/quantity, EBAY_US, FIXED_PRICE,
  pricingSummary, listingPolicies with TODO policy IDs), condition mapping,
  title truncation with warnings.
- Etsy: complete Open API v3 `createListing` body with TODO placeholders
  for shop id, taxonomy id, shipping profile id, and when_made.
- Depop: explicit stub (`DepopStubAdapter`) raising
  `DepopNotAvailableError`; private/mobile endpoints explicitly forbidden.
- Assisted framework: complete listing payload + official public
  listing-creation deep links + clipboard-ready text for Poshmark, Mercari,
  and Facebook Marketplace. The human clicks the final publish button.
- Registry with Coming Soon statuses and flag gating; in-memory delist
  tracker stub recording where each item was listed.
- 16 offline tests in `tests/test_crosslist.py` (flag behavior, model
  validation, registry, payload structure, stub refusals, assisted helpers,
  tracker roundtrip).

STUBBED / TODO:

- eBay OAuth (Authorization Code) + createOrReplaceInventoryItem /
  createOffer / publishOffer wiring; real fulfillment/payment/return policy
  IDs; per-category condition refinement.
- Etsy OAuth (+PKCE) + createListing / uploadListingImage / publish wiring;
  real shop id, taxonomy id, shipping profile id, when_made per item.
- Depop: everything (needs partner-API approval first).
- Assisted adapters: human still clicks publish *by design*; delist is
  manual (remove in the marketplace UI, record in `DelistTracker`).
- `DelistTracker` persistence (currently in-memory only).
- No UI wiring — `app.py` / `pages/` untouched by design; any future UI
  surface must carry the "Coming Soon" label and honor the flag.
- Tests were authored carefully but NOT executed in this session (browser
  only, no shell) — CI must run them before any merge.

## Hard rules honored

- No reverse-engineered private APIs — assisted adapters use only official
  public listing-creation URLs plus human paste/click.
- No real credentials anywhere — placeholders + TODOs only.
- No real listings, purchases, or money movement.
- Nothing merged; branch only. `main`, the Android branch, and `app.py`
  billing/Stripe code untouched.
