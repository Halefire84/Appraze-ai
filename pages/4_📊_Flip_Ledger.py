"""CRTC Flip Ledger — the operating layer after a BUY decision."""
import pandas as pd
import streamlit as st

from flip_ledger import build_flip_record, update_flip
from listing_bridge import build_master_listing
from storage import load_table, save_table

st.set_page_config(page_title="CRTC — Flip Ledger", page_icon="📊", layout="wide")
st.title("📊 CRTC Flip Ledger")
st.caption("BUY → PURCHASED → LISTED → SOLD → REALIZED PROFIT")

if "crtc_flip_ledger" not in st.session_state:
    loaded = load_table("flip_ledger")
    st.session_state["crtc_flip_ledger"] = loaded.payload or [] if loaded.success else []
    st.session_state["crtc_flip_storage_message"] = "Loaded saved ledger." if loaded.success else f"Local session ledger: {loaded.error}"

ledger = st.session_state["crtc_flip_ledger"]
intake_queue = st.session_state.get("crtc_inventory_intake", [])

st.info(st.session_state.get("crtc_flip_storage_message", ""))

with st.container(border=True):
    st.markdown("### 📥 BUY queue")
    if intake_queue:
        for i, intake in enumerate(intake_queue):
            cols = st.columns([4, 2, 2, 1])
            cols[0].write(f"**{intake.get('item_name', 'Untitled')}**")
            cols[1].write(intake.get("source", ""))
            cols[2].write(f"Cost basis: ${float(intake.get('cost_basis') or 0):,.2f}")
            if cols[3].button("TRACK", key=f"track_{i}", use_container_width=True):
                record = build_flip_record(intake, status="PURCHASED")
                ledger.append(record)
                st.session_state["crtc_flip_ledger"] = ledger
                st.session_state["crtc_inventory_intake"] = intake_queue[:i] + intake_queue[i + 1:]
                result = save_table(pd.DataFrame(ledger), "flip_ledger")
                st.session_state["crtc_flip_storage_message"] = "Saved flip to shared ledger." if result.success else f"Tracked locally; save failed: {result.error}"
                st.rerun()
    else:
        st.caption("No BUY records waiting. Use Deal Workspace to turn an approved BUY into inventory intake.")

with st.container(border=True):
    st.markdown("### ➕ Manual flip")
    with st.form("manual_flip"):
        c1, c2 = st.columns(2)
        with c1:
            item_name = st.text_input("Item name")
            source = st.text_input("Source", value="Local")
            cost_basis = st.number_input("Cost basis", min_value=0.0, value=0.0, step=1.0)
        with c2:
            list_price = st.number_input("List price", min_value=0.0, value=0.0, step=5.0)
            sale_price = st.number_input("Sale price", min_value=0.0, value=0.0, step=5.0)
        submitted = st.form_submit_button("ADD FLIP", type="primary", use_container_width=True)
    if submitted:
        record = build_flip_record({"item_name": item_name, "source": source, "cost_basis": cost_basis}, status="PURCHASED")
        record = update_flip(record, list_price=list_price, sale_price=sale_price)
        ledger.append(record)
        st.session_state["crtc_flip_ledger"] = ledger
        result = save_table(pd.DataFrame(ledger), "flip_ledger")
        st.session_state["crtc_flip_storage_message"] = "Flip added and saved." if result.success else f"Flip added locally; save failed: {result.error}"
        st.rerun()

if ledger:
    st.markdown("### 📈 Flip pipeline")
    counts = {status: sum(1 for x in ledger if x.get("status") == status) for status in ["PURCHASED", "LISTED", "SOLD", "PASSED"]}
    k = st.columns(4)
    k[0].metric("Purchased", counts["PURCHASED"])
    k[1].metric("Listed", counts["LISTED"])
    k[2].metric("Sold", counts["SOLD"])
    k[3].metric("Realized profit", f"${sum(float(x.get('profit', 0) or 0) for x in ledger):,.2f}")

    for i, record in enumerate(ledger):
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"### {record.get('item_name', 'Untitled')}")
                st.caption(f"{record.get('source', '')} · {record.get('source_listing_id', '')} · Cost basis ${float(record.get('cost_basis', 0) or 0):,.2f}")
            with right:
                current = record.get("status", "PURCHASED")
                allowed = {
                    "PURCHASED": ["PURCHASED", "LISTED", "PASSED"],
                    "LISTED": ["LISTED", "SOLD", "PASSED"],
                    "SOLD": ["SOLD"],
                    "PASSED": ["PASSED"],
                }.get(current, [current])
                new_status = st.selectbox("Status", allowed, index=0, key=f"status_{i}")
            c1, c2, c3, c4 = st.columns(4)
            list_price = c1.number_input("List price", min_value=0.0, value=float(record.get("list_price", 0) or 0), step=5.0, key=f"list_{i}")
            sale_price = c2.number_input("Sale price", min_value=0.0, value=float(record.get("sale_price", 0) or 0), step=5.0, key=f"sale_{i}")
            fee_pct = c3.number_input("Fee %", min_value=0.0, value=float(record.get("platform_fee_pct", 13) or 13), step=0.5, key=f"fee_{i}")
            ship_out = c4.number_input("Shipping out", min_value=0.0, value=float(record.get("shipping_out", 0) or 0), step=1.0, key=f"ship_{i}")
            if new_status == "SOLD" and sale_price > 0:
                preview = update_flip(record, status="SOLD", list_price=list_price, sale_price=sale_price, platform_fee_pct=fee_pct, shipping_out=ship_out)
                p1, p2, p3 = st.columns(3)
                p1.metric("Net proceeds", f"${preview['net_proceeds']:,.2f}")
                p2.metric("Realized profit", f"${preview['profit']:,.2f}")
                p3.metric("ROI", "∞" if preview['roi_pct'] == float('inf') else f"{preview['roi_pct']:.1f}%")
            if st.button("SAVE CHANGES", key=f"save_{i}", use_container_width=True):
                try:
                    updated = update_flip(record, status=new_status, list_price=list_price, sale_price=sale_price, platform_fee_pct=fee_pct, shipping_out=ship_out)
                    if new_status == "LISTED" and record.get("status") != "LISTED":
                        master = build_master_listing(updated)
                        st.session_state["crtc_master_listing"] = master
                        master_result = save_table(pd.DataFrame([master]), "listing_masters")
                        if not master_result.success:
                            st.session_state["crtc_flip_storage_message"] = f"Flip updated; master listing queued locally because save failed: {master_result.error}"
                    ledger[i] = updated
                    st.session_state["crtc_flip_ledger"] = ledger
                    result = save_table(pd.DataFrame(ledger), "flip_ledger")
                    if result.success:
                        if new_status == "LISTED" and record.get("status") != "LISTED":
                            st.session_state["crtc_flip_storage_message"] = "Flip marked LISTED and master listing sent to Cross-List."
                        else:
                            st.session_state["crtc_flip_storage_message"] = "Ledger saved."
                    else:
                        st.session_state["crtc_flip_storage_message"] = f"Updated locally; save failed: {result.error}"
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    st.markdown("### 📋 Ledger export")
    st.download_button("Export CSV", pd.DataFrame(ledger).to_csv(index=False), "crtc-flip-ledger.csv", "text/csv", use_container_width=True)
else:
    st.warning("Your flip ledger is empty. Track a BUY above or add a manual flip.")

st.caption("CRTC · One source of truth for the flip lifecycle. Marketplace publishing remains a separate approved-API integration layer.")
