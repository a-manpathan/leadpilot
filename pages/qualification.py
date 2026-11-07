"""
Lead Qualification Page: Transparent lead scoring (0-100), criteria breakdown, and manual override.
"""
import json
import streamlit as st
from modules.qualification import calculate_lead_score, override_lead_qualification
from modules.lead_manager import get_all_leads_enriched
from utils.helpers import format_score_badge


def render_qualification():
    st.markdown("## ⭐ AI-Assisted Lead Qualification")
    st.caption("Objective 0-100 scoring based on ICP industry alignment, business model, contact availability, and geography.")

    st.warning("⚠️ **Note on Intent:** Qualification scores reflect Ideal Customer Profile (ICP) alignment and contact completeness. A high score does not predict or guarantee internal buying intent.")

    leads = get_all_leads_enriched()
    if not leads:
        st.info("No leads discovered yet. Please discover leads in **Discover Leads** first.")
        return

    # Tabs: Single Lead Scoring vs Batch
    tab_single, tab_batch = st.tabs(["Prospect Scoring & Breakdown", "Batch Qualification"])

    with tab_single:
        biz_options = {f"{l['name']} (Score: {l.get('lead_score', 0)}/100)": l['id'] for l in leads}
        selected_label = st.selectbox("Select Business to Inspect Scoring", options=list(biz_options.keys()))
        selected_id = biz_options[selected_label]
        lead_data = next((l for l in leads if l["id"] == selected_id), None)

        if lead_data:
            col_score, col_act = st.columns([1, 2])
            with col_score:
                score = lead_data.get("lead_score", 0)
                status = lead_data.get("qualification_status", "Low Priority")
                st.metric(
                    label="Lead Score",
                    value=f"{score}/100",
                    delta=status,
                )
                if lead_data.get("manual_override"):
                    st.caption(f"🔧 *Manually Overridden:* {lead_data.get('override_reason')}")

            with col_act:
                st.markdown(f"##### Recommended Next Action")
                st.info(lead_data.get("recommended_action") or "Run scoring to generate action recommendation.")
                if st.button("🔄 Recalculate Score", type="primary"):
                    calculate_lead_score(selected_id)
                    st.success("Score updated!")
                    st.rerun()

            st.markdown("---")

            # Score Breakdown Cards
            st.markdown("#### Criteria Point Breakdown")
            breakdown_json = lead_data.get("score_breakdown")
            breakdown = {}
            if breakdown_json:
                try:
                    breakdown = json.loads(breakdown_json) if isinstance(breakdown_json, str) else breakdown_json
                except Exception:
                    pass

            c1, c2, c3 = st.columns(3)
            with c1:
                item = breakdown.get("industry_relevance", {"points": 0, "max": 30, "reason": "Not calculated"})
                st.markdown(
                    f"""
                    <div style="border:1px solid #E0E0E0;padding:12px;border-radius:8px;background-color:#FAFAFA;">
                        <h4 style="margin:0;color:#1A73E8;">{item['points']} / {item['max']} pts</h4>
                        <strong>Industry Relevance</strong>
                        <p style="font-size:0.85rem;color:#555;margin-top:6px;">{item.get('reason','')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c2:
                item = breakdown.get("business_type_match", {"points": 0, "max": 25, "reason": "Not calculated"})
                st.markdown(
                    f"""
                    <div style="border:1px solid #E0E0E0;padding:12px;border-radius:8px;background-color:#FAFAFA;">
                        <h4 style="margin:0;color:#1A73E8;">{item['points']} / {item['max']} pts</h4>
                        <strong>Business Type Match</strong>
                        <p style="font-size:0.85rem;color:#555;margin-top:6px;">{item.get('reason','')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c3:
                item = breakdown.get("website_relevance", {"points": 0, "max": 20, "reason": "Not calculated"})
                st.markdown(
                    f"""
                    <div style="border:1px solid #E0E0E0;padding:12px;border-radius:8px;background-color:#FAFAFA;">
                        <h4 style="margin:0;color:#1A73E8;">{item['points']} / {item['max']} pts</h4>
                        <strong>Website & Services</strong>
                        <p style="font-size:0.85rem;color:#555;margin-top:6px;">{item.get('reason','')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.write("")
            c4, c5 = st.columns(2)
            with c4:
                item = breakdown.get("contact_info", {"points": 0, "max": 15, "reason": "Not calculated"})
                st.markdown(
                    f"""
                    <div style="border:1px solid #E0E0E0;padding:12px;border-radius:8px;background-color:#FAFAFA;">
                        <h4 style="margin:0;color:#1A73E8;">{item['points']} / {item['max']} pts</h4>
                        <strong>Contact Info Availability</strong>
                        <p style="font-size:0.85rem;color:#555;margin-top:6px;">{item.get('reason','')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c5:
                item = breakdown.get("geographic_match", {"points": 0, "max": 10, "reason": "Not calculated"})
                st.markdown(
                    f"""
                    <div style="border:1px solid #E0E0E0;padding:12px;border-radius:8px;background-color:#FAFAFA;">
                        <h4 style="margin:0;color:#1A73E8;">{item['points']} / {item['max']} pts</h4>
                        <strong>Geographic Match</strong>
                        <p style="font-size:0.85rem;color:#555;margin-top:6px;">{item.get('reason','')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Missing info checklist
            st.markdown("---")
            st.markdown("##### ⚠️ Missing Information Checklist")
            missing_json = lead_data.get("missing_info")
            missing_items = []
            if missing_json:
                try:
                    missing_items = json.loads(missing_json) if isinstance(missing_json, str) else missing_json
                except Exception:
                    pass

            if missing_items:
                for item in missing_items:
                    st.markdown(f"- ❌ {item}")
            else:
                st.success("✅ No critical data points missing. Prospect profile is complete!")

            # Manual Score Override Form
            st.markdown("---")
            with st.expander("🛠️ Manual Score & Priority Adjustment"):
                st.caption("Override calculated score if you possess verified offline context or domain knowledge.")
                with st.form("override_form"):
                    col_o1, col_o2 = st.columns(2)
                    with col_o1:
                        new_score = st.slider("New Score (0-100)", 0, 100, int(score))
                    with col_o2:
                        new_priority = st.selectbox("New Classification", ["High Priority", "Medium Priority", "Low Priority"])
                    reason = st.text_input("Reason for adjustment", value="Direct client fit verified through manual review.")
                    if st.form_submit_button("Save Manual Override"):
                        override_lead_qualification(selected_id, new_score, new_priority, reason)
                        st.success("Manual qualification saved successfully!")
                        st.rerun()

    with tab_batch:
        st.markdown("##### ⚡ Bulk Score Recalculation")
        st.caption(
            "Recalculate qualification scores from the current research profile. "
            "Leads with a manual score override keep that override."
        )
        if st.button("Score All Leads", type="primary"):
            progress = st.progress(0.0)
            for i, l in enumerate(leads):
                calculate_lead_score(l["id"])
                progress.progress((i + 1) / len(leads))
            st.success("All leads successfully qualified and scored!")
            st.rerun()


render_qualification()
