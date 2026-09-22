#!/usr/bin/env python3
"""sandbox_proof.py -- manual, one-shot round-trip proof for ebay_sell.py.

Run by hand only. Never imported by the app, never run in CI (there are no
real credentials in CI, and there should never be -- this hits eBay's real
sandbox over the network). Proves the full publish path end-to-end:

    authenticate -> ensure business policies + merchant location exist
        (reuse-if-exists) -> publish one obvious test listing
        -> poll until ACTIVE -> withdraw -> poll until ended

Prerequisites (see docs/EBAY_SELL_SETUP.md for the exact steps):
  - EBAY_SELL_CLIENT_ID / EBAY_SELL_CLIENT_SECRET / EBAY_SELL_REDIRECT_URI
    set via environment or ebay_config.json.
  - A completed one-time browser authorization, so .ebay_tokens.json holds
    a refresh token (this script fails fast with a clear message if not).

Business policy IDs and the merchant location key do NOT need to be
pre-filled -- this script creates or reuses them automatically and saves
whatever it creates back into ebay_config.json for next time.

Usage:
    python3 sandbox_proof.py [--category-id 9355]

Exit code is 0 only if the listing actually reached ACTIVE AND was
successfully withdrawn afterward -- a withdraw failure after a successful
publish still exits nonzero, because a live sandbox test listing would
otherwise be left behind unreported. Every failure prints exactly which
step failed and eBay's own error message; nothing here invents a
policy/listing ID or a status this script did not actually observe.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import ebay_sell

TEST_TITLE = "SANDBOX TEST - DELETE ME - Appraze publish proof"

# "Cell Phones & Smartphones" -- a real, documented eBay category ID used
# in eBay's own Sell API examples and tutorials (see
# https://developer.ebay.com/devzone/xml/docs/howto/XML_ListingAndSelling/ListingAndSelling_listing.html).
# Sandbox and production category trees can diverge, and this has never
# been exercised against this account's actual sandbox category tree --
# override with --category-id if eBay rejects it.
DEFAULT_CATEGORY_ID = "9355"

POLL_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 5

_ACTIVE_STATUSES = {"PUBLISHED"}
_ENDED_STATUSES = {"ENDED", "UNPUBLISHED"}


def _log(message: str) -> None:
    print(f"[sandbox_proof] {message}", flush=True)


def _poll_until(client: ebay_sell.EbaySellClient, offer_id: str, target_statuses: set, timeout: int) -> dict:
    """Poll getOfferStatus until status is in target_statuses or timeout.
    Prints every observed status (never silently waits). Returns whatever
    the last real API response was -- never a fabricated final state."""
    deadline = time.time() + timeout
    last: dict = {}
    while True:
        try:
            last = client.get_offer_status(offer_id)
        except ebay_sell.EbaySellError as exc:
            _log(f"status check failed: {exc}")
            last = {"status": "STATUS_CHECK_FAILED", "error": str(exc)}
            break
        status = str(last.get("status", "UNKNOWN"))
        _log(f"offer {offer_id} status: {status}")
        if status in target_statuses:
            break
        if time.time() >= deadline:
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    return last


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--category-id", default=DEFAULT_CATEGORY_ID, help="eBay sandbox category ID for the test listing")
    args = parser.parse_args()

    if not ebay_sell.is_authorized():
        _log(
            "FAILED: No eBay sandbox authorization found -- .ebay_tokens.json is "
            "missing or has no refresh token. Run the one-time browser "
            "authorization first (docs/EBAY_SELL_SETUP.md, step 4), then re-run "
            "this script."
        )
        return 1

    try:
        config = ebay_sell.load_config()
        config.require_auth_fields()
    except ebay_sell.EbaySellConfigError as exc:
        _log(f"FAILED: {exc}")
        return 1

    client = ebay_sell.EbaySellClient(config=config)

    _log("Authenticating (refreshing the access token if needed)...")
    try:
        _ = client.access_token
    except ebay_sell.EbaySellError as exc:
        _log(f"FAILED: authentication failed: {exc}")
        return 1
    _log("Authenticated.")

    _log("Ensuring business policies and merchant location exist (reuse-if-exists)...")
    try:
        config = ebay_sell.ensure_sandbox_listing_prerequisites(client)
    except ebay_sell.EbaySellError as exc:
        _log(f"FAILED: could not create/reuse a business policy or the merchant location: {exc}")
        return 1
    _log(f"payment_policy_id      = {config.payment_policy_id}")
    _log(f"fulfillment_policy_id  = {config.fulfillment_policy_id}")
    _log(f"return_policy_id       = {config.return_policy_id}")
    _log(f"merchant_location_key  = {config.merchant_location_key}")
    _log(f"(saved to {ebay_sell.CONFIG_FILE})")

    sku = f"APPRAZE-SANDBOX-PROOF-{int(time.time())}"
    master = {
        "sku": sku,
        "title": TEST_TITLE,
        "description": TEST_TITLE,
        "condition": "New",
        "price": 1.00,
        "quantity": 1,
        "ebay_category_id": args.category_id,
    }
    _log(f"Test item: SKU={sku} title={TEST_TITLE!r} price=$1.00 qty=1 condition=NEW category={args.category_id}")

    offer_id: Optional[str] = None
    listing_id: Optional[str] = None
    published_ok = False
    active_ok = False
    withdrawn_ok = False

    try:
        _log("Publishing to eBay sandbox (inventory item -> offer -> publish)...")
        try:
            result = ebay_sell.publish_master(master, config=config, client=client)
        except ebay_sell.EbaySellError as exc:
            _log(f"FAILED: publish failed: {exc}")
            return 1
        offer_id = result["offer_id"]
        listing_id = result["listing_id"]
        published_ok = True
        _log(f"Published. listingId={listing_id} offerId={offer_id}")

        _log(f"Polling getOfferStatus until ACTIVE (timeout {POLL_TIMEOUT_SECONDS}s)...")
        status_result = _poll_until(client, offer_id, _ACTIVE_STATUSES, POLL_TIMEOUT_SECONDS)
        active_ok = str(status_result.get("status")) in _ACTIVE_STATUSES
        if not active_ok:
            _log(f"FAILED: listing did not reach ACTIVE within {POLL_TIMEOUT_SECONDS}s; last observed status: {status_result.get('status', 'UNKNOWN')}")
            return 1

        _log("Listing is live on eBay sandbox.")
        _log("Sandbox Seller Hub (view your active listings): https://www.sandbox.ebay.com/sh/lst/active")
        _log(f"listingId={listing_id} / offerId={offer_id} / SKU={sku}")

        return 0
    finally:
        if offer_id:
            _log(f"Withdrawing offer {offer_id} (cleanup -- never leave a live sandbox test listing behind)...")
            try:
                client.withdraw_offer(offer_id)
            except ebay_sell.EbaySellError as exc:
                _log(f"FAILED: withdraw request itself failed: {exc}")
                _log(f"ACTION NEEDED: manually withdraw offer {offer_id} (listing {listing_id}) in Seller Hub.")
                withdrawn_ok = False
            else:
                final = _poll_until(client, offer_id, _ENDED_STATUSES, POLL_TIMEOUT_SECONDS)
                final_status = str(final.get("status", "UNKNOWN"))
                withdrawn_ok = final_status in _ENDED_STATUSES
                if withdrawn_ok:
                    _log(f"Withdraw confirmed. Final status: {final_status}")
                else:
                    _log(f"FAILED: withdraw was requested but final status is still {final_status}, not ENDED/UNPUBLISHED. Check Seller Hub manually.")

            if published_ok and active_ok and not withdrawn_ok:
                # A live listing may still be on eBay's sandbox site. Force a
                # nonzero exit even though the publish itself succeeded --
                # the round-trip proof isn't complete until cleanup is too.
                _log("SUMMARY: publish succeeded, listing went ACTIVE, but withdraw did NOT confirm ENDED. Exiting nonzero.")
                sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
