# eBay Sell API setup — SANDBOX ONLY

This is the publishing path behind **Cross-List → PUBLISH TO EBAY (SANDBOX)**. It posts real
listings to eBay's *sandbox*, which is a separate, fake marketplace: nothing here can create a
listing buyers can see, and no money moves. There is no production switch in this milestone.

It is a different eBay surface from the one Appraze already uses for comps. `comps_adapters.py`
and `ebay_holy_grail.py` call the **Browse/Marketplace Insights** APIs with `EBAY_CLIENT_ID` /
`EBAY_CLIENT_SECRET`. Publishing uses the **Sell/Inventory** API with its own keys under the
`EBAY_SELL_*` prefix. Don't reuse one set for the other — the Browse keys are production keys,
and sandbox publishing needs sandbox keys.

---

## 1. Create the eBay developer application

1. Sign in at <https://developer.ebay.com> with your eBay account and join the developer program.
2. Go to **Application Keys** (Hi *your name* → Application Keys).
3. You'll see two columns: **Sandbox** and **Production**. Use the **Sandbox** column only.
4. From the Sandbox row, copy:
   - **App ID (Client ID)** → `EBAY_SELL_CLIENT_ID`
   - **Cert ID (Client Secret)** → `EBAY_SELL_CLIENT_SECRET`
5. Click **User Tokens** under the Sandbox keyset → **Get a Token from eBay via Your Application**
   → **Add eBay Redirect URL**. Fill in:
   - *Display title*: anything (e.g. "Appraze Cross-List Sandbox")
   - *Your auth accepted URL*: an HTTPS URL you control. It never has to serve anything — you
     only copy the `?code=` out of the browser's address bar. `https://localhost/ebay-auth` works
     if you have any HTTPS listener; otherwise use a real page you own.
   - *Your privacy policy URL*: any page you own.
6. eBay generates an **RuName** (looks like `Alex_Smith-AlexSmit-apprze-abcdefg`).
   **This RuName — not the URL — is `EBAY_SELL_REDIRECT_URI`.** Everyone gets this wrong once.

## 2. Create a sandbox test user, then let the script set up policies/location

Sandbox publishing needs a sandbox *seller* with business policies:

1. **Sandbox → Test Users → Create test user.** Save the generated username and password;
   that's the account you'll log into when authorizing in step 4, and the account whose
   Seller Hub will show the listing.
2. Sign in to <https://www.sandbox.ebay.com> as that test user and opt into **Business Policies**
   (My eBay → Account → Business Policies) — a sandbox test user needs to be opted in before any
   policy can be created on the account, even via the API.

**You do not need to manually create the payment/fulfillment/return policies or the merchant
location yourself.** `sandbox_proof.py` (step 6 below) creates each one automatically the first
time it runs and reuses them on every later run — see `ebay_sell.py`'s
`ensure_sandbox_listing_prerequisites()`. `publish_master()` still refuses to make any HTTP call
until all four IDs are set, so a genuinely missing one shows up as a clear error message rather
than a confusing eBay rejection; `sandbox_proof.py` fills them in before it ever calls
`publish_master()`.

If you'd rather create them by hand instead (e.g. to use specific existing policies), you still
can, in Seller Hub → Account → Business Policies, and set the resulting IDs as
`EBAY_SELL_PAYMENT_POLICY_ID` / `EBAY_SELL_FULFILLMENT_POLICY_ID` / `EBAY_SELL_RETURN_POLICY_ID` /
`EBAY_SELL_MERCHANT_LOCATION_KEY` per step 3 below — `ensure_sandbox_listing_prerequisites()`
reuses whatever is already set instead of creating a duplicate.

## 3. Put the keys where the app reads them

Two options. **Environment variables win over the file.**

### Option A — environment (preferred)

```bash
export EBAY_SELL_CLIENT_ID="...sandbox App ID..."
export EBAY_SELL_CLIENT_SECRET="...sandbox Cert ID..."
export EBAY_SELL_REDIRECT_URI="Alex_Smith-AlexSmit-apprze-abcdefg"   # the RuName
export EBAY_SELL_MARKETPLACE_ID="EBAY_US"
export EBAY_SELL_MERCHANT_LOCATION_KEY="CRTC_WAREHOUSE"
export EBAY_SELL_FULFILLMENT_POLICY_ID="..."
export EBAY_SELL_PAYMENT_POLICY_ID="..."
export EBAY_SELL_RETURN_POLICY_ID="..."
```

Put these in a local `.env` (already gitignored) if you want them to persist.

### Option B — local `ebay_config.json`

```python
python3 -c "import ebay_sell; print(ebay_sell.write_config_template())"
```

writes an empty template. Fill in the same values without the `EBAY_SELL_` prefix
(`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, …).

`ebay_config.json`, `.ebay_tokens.json`, and `.env` are all in `.gitignore`. **Never commit them.**
If you ever paste a key into a commit, treat it as burned and regenerate it in the developer portal.

## 4. Authorize once (the manual test script)

Publishing needs a *user* token, so this step needs a browser once. The refresh token eBay hands
back lasts ~18 months; after this you won't do it again.

**Scopes requested:** `sell.inventory`, `sell.inventory.readonly`, and `sell.account` (the last
one is required for the policy/location builders in step 2 above — creating or listing a
business policy or a merchant location is an Account API call, not an Inventory API call).
If you authorized before `sell.account` was added, the stored token does not have it and cannot
gain it via refresh — delete `.ebay_tokens.json` and redo this step from scratch.

```bash
cd ~/workspace/crtc-work

# 1. Get the consent URL.
python3 -c "import ebay_sell; print(ebay_sell.get_authorization_url())"

# 2. Open that URL in a browser. Sign in as the SANDBOX TEST USER from step 2
#    (not your real eBay account) and click Agree.

# 3. The browser lands on your redirect URL. Copy the whole ?code=... value out of
#    the address bar — it is long and URL-encoded. Copy all of it, no trailing &state.

# 4. Exchange it for tokens (writes .ebay_tokens.json, chmod 600).
python3 -c "import ebay_sell; ebay_sell.exchange_code_for_tokens('PASTE_THE_CODE_HERE'); print('authorized')"
```

The code expires in about five minutes — if step 4 says `invalid_grant`, just redo step 1.

Verify the token works:

```bash
python3 -c "import ebay_sell; print(bool(ebay_sell.get_valid_access_token()))"
```

## 5. Run the round-trip proof

`sandbox_proof.py` is the fastest way to confirm everything above actually works, end to end,
without touching the Streamlit app. It authenticates, creates/reuses the three business policies
and the merchant location, publishes one obvious throwaway test listing, polls until it's ACTIVE,
and withdraws it again — printing every step. Run by hand only; it is never invoked by the app,
a test, or CI (there are no real credentials in CI, and there should never be).

```bash
python3 sandbox_proof.py
```

Optional: `--category-id <id>` to override the default test category if eBay rejects `9355`
("Cell Phones & Smartphones" — a documented example category, not verified against every
sandbox account's category tree).

**Expected output** on a fully successful run:

```
[sandbox_proof] Authenticating (refreshing the access token if needed)...
[sandbox_proof] Authenticated.
[sandbox_proof] Ensuring business policies and merchant location exist (reuse-if-exists)...
[sandbox_proof] payment_policy_id      = 6196932000
[sandbox_proof] fulfillment_policy_id  = 6196933000
[sandbox_proof] return_policy_id       = 6196934000
[sandbox_proof] merchant_location_key  = appraze-test-warehouse
[sandbox_proof] (saved to ebay_config.json)
[sandbox_proof] Test item: SKU=APPRAZE-SANDBOX-PROOF-1758... title='SANDBOX TEST - DELETE ME - Appraze publish proof' price=$1.00 qty=1 condition=NEW category=9355
[sandbox_proof] Publishing to eBay sandbox (inventory item -> offer -> publish)...
[sandbox_proof] Published. listingId=<real eBay listingId> offerId=<real eBay offerId>
[sandbox_proof] Polling getOfferStatus until ACTIVE (timeout 120s)...
[sandbox_proof] offer <offerId> status: PUBLISHED
[sandbox_proof] Listing is live on eBay sandbox.
[sandbox_proof] Sandbox Seller Hub (view your active listings): https://www.sandbox.ebay.com/sh/lst/active
[sandbox_proof] listingId=<...> / offerId=<...> / SKU=APPRAZE-SANDBOX-PROOF-...
[sandbox_proof] Withdrawing offer <offerId> (cleanup -- never leave a live sandbox test listing behind)...
[sandbox_proof] offer <offerId> status: ENDED
[sandbox_proof] Withdraw confirmed. Final status: ENDED
```

exit code `0`. The placeholder-shaped IDs above (`6196932000`, etc.) are illustrative only —
this doc has never been updated from an actual run; your real output will have eBay's real IDs.
Every listed ID and status line in a real run should be copied verbatim into
`reports/latest-session-report.md` when this is actually executed, never retyped from memory.

On any failure, the script prints exactly which step failed and eBay's own error message, and
still exits nonzero even if the listing had already gone ACTIVE but the withdraw step then failed
— see the Troubleshooting table below.

## 6. Publish one sandbox listing from the app instead

```bash
streamlit run app.py
```

In the app: **Cross-List** → generate drafts → on the **eBay** draft click **MARK READY**, then
**PUBLISH TO EBAY (SANDBOX)**.

On success the draft moves to `ACTIVE`, the eBay `listingId` is stored as the listing's
`external_id`, and the `offerId` is kept as `ebay_offer_id` so you can withdraw it later.
On failure the error is shown and the draft stays in `READY_TO_PUBLISH` — safe to retry.

Or from a shell, without the UI:

```bash
python3 -c "
import ebay_sell
master = {
    'sku': 'SANDBOX-TEST-1',
    'title': 'Appraze sandbox test listing — do not buy',
    'description': 'Sandbox smoke test.',
    'condition': 'Used',
    'price': 19.99,
    'quantity': 1,
    'weight_lbs': 2,
}
print(ebay_sell.publish_master(master))
"
```

## 7. Verify, then withdraw manually (only if not using sandbox_proof.py, which does this for you)

1. Sign in to <https://www.sandbox.ebay.com> as the test user → **Seller Hub → Listings → Active**.
   Your listing should be there with the title and price from the master record.
2. Clean it up so the sandbox account doesn't accumulate junk:

```bash
python3 -c "import ebay_sell; print(ebay_sell.EbaySellClient().get_offer_status('OFFER_ID'))"
python3 -c "import ebay_sell; ebay_sell.EbaySellClient().withdraw_offer('OFFER_ID'); print('withdrawn')"
```

`withdraw_offer` ends the listing but keeps the offer, so you can republish the same SKU.
Re-publishing an already-published SKU is handled: `publish_master` looks for an existing offer
and updates it rather than failing with a duplicate-SKU error.

---

## Sandbox vs production

Every endpoint in `ebay_sell.py` is a hardcoded `*.sandbox.ebay.com` constant
(`AUTHORIZE_URL`, `TOKEN_URL`, `INVENTORY_BASE`). There is deliberately no environment variable
that flips this — a wrong env value cannot post a real listing. Going live is a later milestone
and needs, at minimum: production keys, a second authorization against the real account, eBay's
production compliance review, and a deliberate review of the fee/pricing math before anything
real is posted.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `Missing eBay Sell credentials: EBAY_SELL_...` | Step 3 — the env var isn't set in the shell running Streamlit. |
| `Missing eBay Sell offer settings` | Step 2 — business policies or merchant location not created/set. |
| `invalid_grant` on code exchange | The `?code=` expired (5 min) or was truncated. Redo step 4. |
| `errorId 25002 ... SKU already exists` | The SKU is on another offer; withdraw it or use a new SKU. |
| `eBay sandbox is not authorized yet` | No `.ebay_tokens.json` — run step 4. |
| Listing publishes but Seller Hub is empty | You authorized as your real account instead of the sandbox test user. |
| `could not create/reuse a business policy or the merchant location` (403 / insufficient scope) | The stored token was authorized before `sell.account` was added to `DEFAULT_SCOPES`. Delete `.ebay_tokens.json` and redo step 4 from scratch — a refresh cannot add a scope to an existing token. |
| Policy creation rejected (400, e.g. a missing/invalid field) | The exact JSON body `create_payment_policy`/`create_fulfillment_policy`/`create_return_policy`/`create_merchant_location` send has never been run against a real sandbox account — see `ebay_sell.py`'s docstrings on each. eBay's error message (surfaced in full, never swallowed) says exactly which field it rejected; fix that field's value, not the whole approach. |
| `sandbox_proof.py` exits nonzero after printing "Listing is live" | The publish and ACTIVE poll both succeeded, but the withdraw step afterward failed or didn't confirm ENDED in time. The listing may still be live — check Seller Hub and withdraw it manually if so; the script's own log names the exact offer/listing ID to look for. |
