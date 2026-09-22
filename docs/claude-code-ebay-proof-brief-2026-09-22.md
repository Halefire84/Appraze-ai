APPRAZE — Claude Code brief: eBay SANDBOX publish round-trip proof
Date: 2026-09-22

MISSION
Finish what milestone 1 started. Publish ONE genuine test listing to eBay
SANDBOX, verify it is live, withdraw it. Prove the whole loop with real IDs.

STATE OF THE WORLD (verified tonight, do not redo)
- ebay_sell.py at repo root: OAuth2 authorization-code flow, sandbox Sell
  Inventory client (create_or_replace_inventory_item, create_offer,
  publish_offer, get_offer_status, withdraw_offer), pure mapping functions
  (master_to_inventory_item, master_to_offer), 31 mocked tests. Sandbox URLs
  are hardcoded constants; there is no production path and there must never be.
- Sandbox seller OAuth is DONE. Tokens authorized for sell.inventory and
  sell.inventory.readonly, stored in ignored .ebay_tokens.json at repo root
  (chmod 600). Use get_valid_access_token(). Never print tokens. Never commit
  them.
- Policy and merchant-location IDs are still blank. That is your first job.

DELIVERABLES
1. Policy and location builders in ebay_sell.py, with new SANDBOX-ONLY
   endpoint constants (*.sandbox.ebay.com — add a test asserting this):
   - create_payment_policy: immediate pay OFF, sandbox-acceptable method.
   - create_fulfillment_policy: simple terms for a small test item.
   - create_return_policy: simplest sandbox-accepted returns.
   - create_merchant_location via /sell/inventory/v1/location, key like
     "appraze-test-warehouse".
   - Reuse-if-exists: list existing policies/locations first and reuse a
     match instead of creating duplicates.
2. sandbox_proof.py at repo root (manual run only, never CI):
   - Authenticate from stored tokens; fail fast with a clear message if missing.
   - Create or reuse the three policies plus the merchant location.
   - Save all IDs to ignored ebay_config.json (add fields; verify gitignored).
   - Build a master dict for an OBVIOUS test item:
     title "SANDBOX TEST - DELETE ME - Appraze publish proof",
     a valid sandbox category ID, 1.00 USD, quantity 1, condition NEW.
   - publish_master -> print listingId and offerId.
   - Poll get_offer_status until ACTIVE (timeout ~2 min), print each result.
   - Print the Sandbox Seller Hub URL so the owner can eyeball the listing.
   - withdraw_offer, poll until withdrawn/ended, print final status.
   - Exit nonzero with a clear message on any failure. Withdraw in a
     finally block: never leave a live test listing behind.
3. Mocked unit tests for the new builders, reuse-if-exists logic, and the
   config save. No network, no credentials in tests.
4. Update docs/EBAY_SELL_SETUP.md with the exact run command and the
   expected output.
5. Overwrite reports/latest-session-report.md with: every ID created,
   the listing/offer IDs, each status transition with timestamps, the
   Seller Hub verification note, the withdraw confirmation, and any
   failures plus how they were fixed.

HARD CONSTRAINTS (non-negotiable)
- Sandbox only. No env var, flag, or constant may point at production.
- Secrets never in git, never in logs, never in the report. Confirm the
  gitignore covers .ebay_tokens.json and ebay_config.json before committing.
- Do not touch: finance.py, comps.py, decision_policy.py, auction_costs.py,
  deal_settings.py, listing_store.py, comps_adapters.py, ebay_holy_grail.py,
  ebay_image_scan.py.
- Listing state moves through listing_store only: READY_TO_PUBLISH -> ACTIVE
  on publish, back out on withdraw. No new statuses.
- Do not invent policy IDs, listing IDs, or status results. Report only what
  the API actually returned.

ACCEPTANCE
sandbox_proof.py runs end to end: one test listing went ACTIVE and was
withdrawn, IDs are persisted in ignored config, the report lists real IDs
and real status transitions. Commit when green.
