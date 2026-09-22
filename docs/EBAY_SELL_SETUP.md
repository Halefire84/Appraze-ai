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

## 2. Create a sandbox test user, policies, and a location

Sandbox publishing needs a sandbox *seller* with business policies. Still on developer.ebay.com:

1. **Sandbox → Test Users → Create test user.** Save the generated username and password;
   that's the account you'll log into when authorizing in step 4, and the account whose
   Seller Hub will show the listing.
2. Sign in to <https://www.sandbox.ebay.com> as that test user and opt into **Business Policies**
   (My eBay → Account → Business Policies). Create one each of:
   - a **payment** policy → `EBAY_SELL_PAYMENT_POLICY_ID`
   - a **shipping/fulfillment** policy → `EBAY_SELL_FULFILLMENT_POLICY_ID`
   - a **return** policy → `EBAY_SELL_RETURN_POLICY_ID`

   The policy IDs are easiest to read back from the Account Settings API, or from the URL when
   you open each policy for editing.
3. Create a **merchant location** — a warehouse the inventory ships from. The Sell Inventory API
   creates these (`POST /sell/inventory/v1/location/{merchantLocationKey}`); the key is a string
   you choose, e.g. `CRTC_WAREHOUSE` → `EBAY_SELL_MERCHANT_LOCATION_KEY`.

`publish_master()` refuses to make any HTTP call until all four of these are set, so a missing
policy shows up as a clear error message rather than a confusing eBay rejection.

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

## 5. Publish one sandbox listing

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

## 6. Verify, then withdraw

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
