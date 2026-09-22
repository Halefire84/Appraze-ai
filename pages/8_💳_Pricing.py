import streamlit as st

from subscription_plans import PLANS
from billing import plan_payment_link

st.set_page_config(page_title="Appraze Pricing", page_icon="💳", layout="wide")
from ui_theme import inject_theme
inject_theme()
from auth import require_auth
require_auth()

st.title("💳 Appraze Pricing")
st.caption("Pay for opportunity intelligence — not another spreadsheet.")

# ---------------------------------------------------------------------------
# Per-plan Stripe Payment Links (billing.plan_payment_link), replacing the
# earlier single fixed-price link (billing.payment_link_url, now legacy --
# nothing calls it). Each plan's "After payment" redirect sends the
# customer back to the app root with ?sub_plan=<key>&sub_session_id=...,
# which app.py's SUBSCRIPTION CHECKOUT RETURN handler verifies and records
# -- that verification happens once, in app.py, not duplicated here, since
# a direct page navigation to this page never re-runs app.py's top-level
# code but DOES see whatever app.py already wrote into st.session_state
# earlier in the same browser session.
# ---------------------------------------------------------------------------
_current_plan = st.session_state.get("user_plan", "free")
if st.session_state.get("user_is_admin"):
    st.success("You're on the Admin account — full access, nothing to buy.")
elif _current_plan and _current_plan != "free":
    st.success(f"Your current plan: **{_current_plan.title()}**")
else:
    st.info("You're on the Free plan.")

st.info("Launch strategy: keep the Free tier useful, make Appraiser the obvious flagship, and add higher-volume tiers only as real demand appears.")

cols = st.columns(len(PLANS))
for col, plan in zip(cols, PLANS):
    with col:
        with st.container(border=True):
            if plan.key == "appraiser":
                st.markdown("**🏆 MOST POPULAR**")
            st.subheader(plan.name)
            st.markdown("Free" if plan.monthly_price == 0 else f"**${plan.monthly_price}/mo**")
            st.caption(plan.tagline)
            st.write(f"**{plan.analyses_per_month:,}** AI analyses / month")
            st.write("✅ Holy Grail hunting" if plan.hunt_enabled else "• Manual analysis")
            st.write("✅ Alerts" if plan.alerts_enabled else "• Basic results")
            st.write("✅ Advanced sources" if plan.advanced_sources else "• Core sources")
            st.write("✅ Liquidation & surplus" if plan.liquidation else "• —")
            st.write("✅ Financial intelligence" if plan.financial_intelligence else "• —")
            st.write("✅ Batch analysis" if plan.batch_analysis else "• —")
            st.write("✅ Priority hunting" if plan.priority else "• Standard priority")
            if plan.team_seats > 1:
                st.write(f"✅ {plan.team_seats} team seats")

            if plan.key == _current_plan:
                st.button("Current plan", disabled=True, use_container_width=True, key=f"current_{plan.key}")
            elif plan.monthly_price == 0:
                st.caption("No signup needed — this is what you start with.")
            else:
                link = plan_payment_link(plan.key)
                if link:
                    button_type = "primary" if plan.key == "appraiser" else "secondary"
                    st.link_button(f"Subscribe to {plan.name}", link, use_container_width=True, type=button_type)
                else:
                    st.button("Not yet available", disabled=True, use_container_width=True, key=f"unavail_{plan.key}")

st.divider()
st.subheader("Why Appraiser is the flagship")
st.markdown("""
**$59/month** is designed around the feature that makes Appraze different: finding opportunities the market overlooked.

- Holy Grail opportunity hunting
- Information-failure scoring
- Max-bid intelligence
- Auction and liquidation research
- Opportunity alerts
- AI valuation and listing intelligence
- Financial intelligence as that layer comes online

The goal is simple: **one profitable find should be capable of paying for the subscription.**
""")

st.caption("Payment links are configured separately through Stripe. No card data is handled by Appraze source code.")
