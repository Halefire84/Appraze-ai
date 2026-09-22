import streamlit as st

from subscription_plans import PLANS
from billing import payment_link_url, verify_checkout_session
from auth import mark_paid
from telemetry import log_event

st.set_page_config(page_title="Appraze Pricing", page_icon="💳", layout="wide")
from auth import require_auth
require_auth()

st.title("💳 Appraze Pricing")
st.caption("Complete Resale Business Suite — deal math, inventory, and listing.")

# ---------------------------------------------------------------------------
# Returning from Stripe's hosted Payment Link page after checkout.
# billing.py's docstring describes the flow this completes: the Payment
# Link's "After payment" redirect (configured once, in the Stripe
# Dashboard) sends the customer back here with
# ?session_id={CHECKOUT_SESSION_ID} appended. Until this page existed,
# billing.payment_link_url()/verify_checkout_session() and
# auth.mark_paid() were all built and tested in isolation but never
# actually called by anything -- nobody could become a paid account
# through the app, only by someone hand-editing the Users sheet.
# ---------------------------------------------------------------------------
_session_id = st.query_params.get("session_id")
if _session_id and not st.session_state.get("user_is_paid", False):
    result = verify_checkout_session(_session_id)
    if result.paid:
        username = st.session_state.get("username", "")
        if username and mark_paid(username):
            st.session_state.user_is_paid = True
            st.success("Payment confirmed — your account is now on a paid plan. Thanks for subscribing!")
            log_event("INFO", "billing", "pages/8_Pricing", "subscription payment confirmed", {"username": username})
        else:
            st.warning(
                "Stripe confirmed your payment, but we couldn't save that to your account just now. "
                "Contact support and we'll fix it manually — you will not be charged again."
            )
            log_event(
                "ERROR", "billing", "pages/8_Pricing", "mark_paid failed after verified payment",
                {"username": username, "session_id": _session_id},
            )
    elif result.error:
        st.error(f"Couldn't confirm that payment: {result.error}")
    st.query_params.clear()

if st.session_state.get("user_is_paid", False):
    st.success("You're on a paid Appraze plan. Thanks for your support!")

st.markdown("---")

for plan in PLANS:
    with st.container(border=True):
        st.subheader(plan.name)
        st.markdown("Free" if plan.monthly_price == 0 else f"${plan.monthly_price}/mo")
        st.caption(plan.tagline)
        st.write(f"**{plan.analyses_per_month:,}** AI analyses / month")
        st.write("AI hunting" if plan.hunt_enabled else "Manual analysis")
        st.write("Alerts" if plan.alerts_enabled else "Basic results")
        st.write("Advanced sources" if plan.advanced_sources else "Core sources")
        st.write("Liquidation & surplus" if plan.liquidation else "—")
        st.write("Financial intelligence" if plan.financial_intelligence else "—")
        st.write("Batch analysis" if plan.batch_analysis else "—")
        st.write("Priority" if plan.priority else "Standard")
        if plan.team_seats > 1:
            st.write(f"{plan.team_seats} team seats")

st.divider()

# ---------------------------------------------------------------------------
# Deliberately ONE subscribe action, not a per-tier button. Today's actual
# enforcement (Users sheet "is_paid" column, the Apps Script AI-quota
# gate) is a single binary paid/not-paid flag -- there is exactly one
# configured Stripe Payment Link (STRIPE_PAYMENT_LINK_URL), not five
# differently-priced ones. Putting a "Subscribe" button on every tier card
# above would charge the same price no matter which one someone clicked,
# which is worse than not offering a button at all. The tier table above
# is the aspirational catalog (subscription_plans.py); per-tier billing
# and feature gating by plan is real future work, not done yet.
# ---------------------------------------------------------------------------
st.subheader("Ready to subscribe?")
_link = payment_link_url()
if st.session_state.get("user_is_paid", False):
    st.button("You're already subscribed", disabled=True)
elif _link:
    st.link_button("Subscribe to Appraze", _link, type="primary")
    st.caption("You'll pay on Stripe's secure checkout page, then land back here automatically once it's confirmed.")
else:
    st.info("Subscriptions aren't open yet in this environment — STRIPE_PAYMENT_LINK_URL isn't configured.")

st.caption("Appraze is the product of Cooper River Trading Co.")
