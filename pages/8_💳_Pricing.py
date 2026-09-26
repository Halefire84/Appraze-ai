import streamlit as st

from subscription_plans import PLANS

st.set_page_config(page_title="Appraze Pricing", page_icon="💳", layout="wide")
from ui_theme import inject_theme
inject_theme()
from auth import require_auth, _secret
require_auth()

st.title("💳 Appraze Pricing")
st.caption("Pay for opportunity intelligence — not another spreadsheet.")

# ---------------------------------------------------------------------------
# Payments are manual for now -- Cash App + emailed receipt, activated by
# hand. Deliberately NOT wired to billing.plan_payment_link()/Stripe here:
# no live checkout flow exists yet, so this page must never look like one.
# Google Play Billing is planned for the Android launch, not this page.
# ---------------------------------------------------------------------------
_current_plan = st.session_state.get("user_plan", "free")
if st.session_state.get("user_is_admin"):
    st.success("You're on the Admin account — full access, nothing to buy.")
elif _current_plan and _current_plan != "free":
    st.success(f"Your current plan: **{_current_plan.title()}**")
else:
    st.info("You're on the Free plan.")

cols = st.columns(len(PLANS))
for col, plan in zip(cols, PLANS):
    with col:
        with st.container(border=True):
            st.subheader(plan.name)
            st.markdown("Free" if plan.monthly_price == 0 else f"**${plan.monthly_price}/mo**")
            st.caption(plan.tagline)
            st.write(f"**{plan.analyses_per_month:,}** AI analyses / month")
            st.write("✅ Holy Grail hunting" if plan.hunt_enabled else "• Manual analysis")
            st.write("✅ Deal alerts" if plan.alerts_enabled else "• —")
            st.write("✅ Inventory tracking" if plan.inventory_tracking else "• —")
            st.write("✅ Advanced sources" if plan.advanced_sources else "• Core sources")
            st.write("✅ Liquidation intel" if plan.liquidation else "• —")
            st.write("✅ Batch analysis" if plan.batch_analysis else "• —")
            st.write("✅ Priority support" if plan.priority else "• Standard priority")
            st.write("✅ Financial intelligence" if plan.financial_intelligence else "• —")
            if plan.team_seats > 1:
                st.write(f"✅ {plan.team_seats} team seats")

            if plan.prepay_3mo:
                st.caption(f"Prepay 3 mo: **${plan.prepay_3mo}** · 6 mo: **${plan.prepay_6mo}** (~30% off)")

            if plan.key == _current_plan:
                st.button("Current plan", disabled=True, use_container_width=True, key=f"current_{plan.key}")
            elif plan.monthly_price == 0:
                st.caption("Sign up with email verification — this is what you start with.")
            else:
                st.caption("See \"How to subscribe\" below.")

st.divider()
st.subheader("How to subscribe (manual for now)")
_cashtag = _secret("PAYMENTS_CASHTAG", "")
_contact_email = _secret("PAYMENTS_CONTACT_EMAIL", "")
st.markdown(f"""
Appraze isn't wired to automated billing yet — every subscription is activated by hand:

1. Send your plan's monthly price (or a 3-month / 6-month prepay total for ~30% off) via Cash App to
   **{_cashtag or "(Cash App tag not yet configured — contact us for details)"}**.
2. Email your payment receipt and your Appraze username to
   **{_contact_email or "(contact email not yet configured)"}**.
3. We'll activate your account by hand, usually within one business day.

Cross-listing (auto-publishing to eBay/Facebook/Mercari) is **coming soon** and not included in any plan yet — every plan today gets marketplace-ready listing drafts you copy and paste yourself.

Google Play Billing (in-app purchase on Android) arrives at the Android launch — this manual flow is only for the web app in the meantime.
""")

st.caption("No card data is ever handled by Appraze source code — Cash App and email are outside this app entirely.")
