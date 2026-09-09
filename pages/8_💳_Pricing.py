import streamlit as st

from subscription_plans import PLANS

st.set_page_config(page_title="CRTC Pricing", page_icon="💳", layout="wide")

st.title("💳 CRTC Pricing")
st.caption("Pay for opportunity intelligence — not another spreadsheet.")

st.info("Launch strategy: keep the Free tier useful, make Hunter the obvious flagship, and add higher-volume tiers only as real demand appears.")

cols = st.columns(len(PLANS))
for col, plan in zip(cols, PLANS):
    with col:
        if plan.key == "hunter":
            st.markdown("### 🏆 MOST POPULAR")
        st.subheader(plan.name)
        if plan.monthly_price == 0:
            st.markdown("# Free")
        else:
            st.markdown(f"# ${plan.monthly_price}/mo")
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

st.divider()
st.subheader("Why Hunter is the flagship")
st.markdown("""
**$49/month** is designed around the feature that makes CRTC different: finding opportunities the market overlooked.

- Holy Grail opportunity hunting
- Information-failure scoring
- Max-bid intelligence
- Auction and liquidation research
- Opportunity alerts
- AI valuation and listing intelligence
- Financial intelligence as that layer comes online

The goal is simple: **one profitable find should be capable of paying for the subscription.**
""")

st.caption("Payment links are configured separately through Stripe. No card data is handled by CRTC source code.")
