import streamlit as st

from subscription_plans import PLANS

st.set_page_config(page_title="Appraze Pricing", page_icon="💳", layout="wide")
from auth import require_auth
require_auth()

st.title("💳 Appraze Pricing")
st.caption("Complete Resale Business Suite — deal math, inventory, and listing.")

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
st.caption("Appraze is the product of Cooper River Trading Co. Payment links are configured separately through Stripe.")
