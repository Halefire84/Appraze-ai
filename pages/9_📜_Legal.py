# Appraze™ — Complete Resale Business Suite
# © 2026 Christopher Hale / Cooper River Trading Co.
#
# In memory of my father, Christopher Hale, who tracked trucks in C++
# before I ever tracked a deal.

"""Appraze legal pages — Terms of Service, Privacy Policy, Refund Policy."""

import streamlit as st

st.set_page_config(page_title="Appraze — Legal", page_icon="📜", layout="wide")
from auth import require_auth
require_auth()

st.title("📜 Appraze™ Legal")
st.caption("Terms of Service · Privacy Policy · Refund Policy")

st.warning(
    "**These are starting-point templates, not legal advice.** They're "
    "written to be accurate about what this app actually does, but a "
    "lawyer should review them before you rely on them in a dispute — "
    "especially once real customer payments are involved. Replace every "
    "`[bracketed]` placeholder below with your own details first."
)

st.caption(
    "Looking for back-office paperwork instead (an NDA, a contractor "
    "agreement, a consignment/purchase agreement, a W-9 request letter)? "
    "That's a separate template library in this repo's `legal/` folder — "
    "not shown here since it's internal business paperwork, not something "
    "app users need to read."
)

LAST_UPDATED = "September 21, 2026"

tos_tab, privacy_tab, refund_tab = st.tabs(
    ["Terms of Service", "Privacy Policy", "Refund Policy"]
)

with tos_tab:
    st.markdown(f"""
### Terms of Service

_Last updated: {LAST_UPDATED}_

These Terms of Service ("Terms") govern access to and use of **Appraze™**
("the App"), operated by **Cooper River Trading Co.** ("CRTC", "we",
"us"). By creating an account or using the App, you agree to these Terms.

**1. What Appraze is.** Appraze is deal math, inventory, and listing
software for resellers — profit/ROI calculations, inventory tracking,
market comps, AI-assisted item analysis, point-of-sale checkout, and
related tools. It is a decision-support tool, not financial, legal, or
tax advice.

**2. Accounts.** You're responsible for keeping your login credentials
confidential and for all activity under your account. Notify us promptly
at [support email] if you suspect unauthorized access.

**3. Acceptable use.** Don't use Appraze to violate any law, infringe
anyone's rights, scrape or resell the App's own data/software, attempt to
bypass authentication or rate limits, or upload content you don't have
the right to upload (including listing photos/descriptions you feed into
the AI Analyzer).

**4. Your data.** You keep ownership of the deal, inventory, and customer
data you enter. We store it to provide the service (see the Privacy
Policy tab) and don't sell it.

**5. Third-party services.** Appraze integrates with third-party services
you or we configure — Stripe (payments), Anthropic (AI analysis), eBay
(market comps), and optionally Gmail (invoice tracking) and Google Sheets
(storage backend). Your use of those integrations is also subject to
their own terms. We aren't responsible for their availability or
accuracy.

**6. No guarantee of profit.** Verdicts, ROI estimates, "BUY"/"PASS"
recommendations, and comps valuations are estimates based on the data
available at the time. Markets move. Always use your own judgment before
committing money to a purchase.

**7. Beta / availability.** The App may be under active development.
Features can change, and — per the free-tier hosting note in the app
itself — data may be reset if the hosting instance restarts. Export a CSV
backup regularly.

**8. Termination.** We may suspend or terminate access for violation of
these Terms. You may stop using the App at any time.

**9. Disclaimer of warranties.** The App is provided "as is," without
warranties of any kind, express or implied.

**10. Limitation of liability.** To the maximum extent permitted by law,
CRTC is not liable for indirect, incidental, or consequential damages
arising from use of the App, including purchase decisions made using its
output.

**11. Governing law.** These Terms are governed by the laws of
[Your State/Country], without regard to conflict-of-laws principles.

**12. Changes.** We may update these Terms. Continued use after a change
means you accept the updated Terms.

**13. Contact.** Questions about these Terms: [support email].
""")

with privacy_tab:
    st.markdown(f"""
### Privacy Policy

_Last updated: {LAST_UPDATED}_

This Privacy Policy explains what Appraze collects and why. It only
describes integrations that are actually configured for this deployment —
unconfigured features (shown as "not connected" in the App) collect
nothing.

**1. Account data.** Username, hashed password, and display name, used
solely to authenticate you and keep your data separate from other users'.

**2. Business data you enter.** Deals, inventory, suppliers, customer
accounts/invoices, and business-profile/tax information you type into the
App. This is stored so the App can show it back to you — not shared with
other users, sold, or used for advertising.

**3. Storage backend.** Business data is stored via a Google Sheets +
Apps Script backend under this deployment's own Google account — not a
third-party CRTC-hosted database. Treat access to that Google account and
the app-secret token as equivalent to database-admin access.

**4. Payments.** Appraze never receives or stores your customers' card
numbers. Checkout happens on Stripe's own hosted page; the App only
receives a payment status (paid/not paid) and, for point-of-sale, an
amount and description. See
[Stripe's Privacy Policy](https://stripe.com/privacy) for how Stripe
handles payment data.

**5. AI Analyzer.** If configured, item descriptions/photos you submit to
the AI Analyzer are sent to Anthropic's API to generate an analysis. See
[Anthropic's Privacy Policy](https://www.anthropic.com/legal/privacy).
Don't submit photos or descriptions containing other people's personal
information you don't have the right to share.

**6. Market comps.** If configured, search terms are sent to eBay's
Browse API to retrieve public active-listing data. No account-specific
data is sent.

**7. Email (optional, only if enabled).** If Gmail invoice tracking is
configured, the App reads (never sends, replies to, deletes, or modifies)
supplier-invoice emails via read-only IMAP, using an app-specific
password you control and can revoke at any time.

**8. Cookies / tracking.** Appraze doesn't run advertising trackers or
sell data to data brokers. Streamlit's hosting platform uses standard
session cookies to keep you logged into a page session; see
[Streamlit's Privacy Notice](https://streamlit.io/privacy-policy) for its
own hosting-level data handling if deployed on Streamlit Community Cloud.

**9. Data retention.** Business data persists until you delete it or the
account is closed. On free-tier hosting, the underlying app process can
restart and clear in-memory session state — persisted table data (in
Google Sheets) is unaffected, but always keep your own CSV backups.

**10. Your choices.** You can export your data as CSV at any time from
the sidebar. To request deletion of your account data, contact
[support email].

**11. Children.** Appraze is a business tool not directed at children
under 13, and it should not be used by anyone under 13.

**12. Changes.** We may update this policy; the "Last updated" date above
will change.

**13. Contact.** Privacy questions: [support email].
""")

with refund_tab:
    st.markdown(f"""
### Refund Policy

_Last updated: {LAST_UPDATED}_

This policy covers **paid access to the Appraze software itself**
(subscriptions/plan billing), not the underlying resale transactions a
business runs through the App's point-of-sale tool — those are between
that business and its own customers, governed by that business's own
return/refund policy, not this one.

**1. Subscriptions.** If/when Appraze offers paid subscription plans,
charges are billed in advance for the period selected (e.g. monthly).
Subscriptions can be cancelled at any time; cancellation stops future
billing but doesn't retroactively refund the current period unless
required by law.

**2. Free trial / free tier.** Where a free tier or trial is offered, no
payment is collected until you actively upgrade to a paid plan.

**3. Requesting a refund.** Contact [support email] within
[X days, e.g. 14] of a charge if you believe it was made in error (e.g.
billed after cancellation, duplicate charge, or a service outage that
prevented use). We'll review in good faith and issue a refund via Stripe
to the original payment method when warranted.

**4. Point-of-sale charges.** Charges a business creates through the
App's "Charge Customer" tool are that business's own sales, processed
through their own Stripe account. Appraze/CRTC is not a party to that
sale and cannot issue refunds on the business's behalf — the business
processes those refunds directly in their Stripe Dashboard.

**5. Chargebacks.** Please contact us before filing a chargeback with
your card issuer — most billing issues can be resolved faster directly.

**6. Contact.** Billing questions: [support email].
""")
