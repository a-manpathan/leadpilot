"""
Research & Enrichment Page: Crawls websites, extracts verified contacts and services, and links sources.
"""
import streamlit as st
import pandas as pd
from database.db import get_db
from database.models import Business, LeadResearch
from modules.extraction import research_business
from modules.lead_manager import get_all_leads_enriched


def render_research():
    st.markdown("## 🌐 Website & Contact Enrichment")
    st.caption("Responsible crawling of company websites to extract public contacts, services, and company summaries.")

    leads = get_all_leads_enriched()
    if not leads:
        st.info("No leads available to research. Please discover leads first in the **Discover Leads** page.")
        return

    # Tabs: Single Lead Research vs Batch Research
    tab_single, tab_batch = st.tabs(["Single Lead Research", "Batch Enrichment"])

    with tab_single:
        # Business Selector
        biz_options = {f"{l['name']} ({l['normalized_domain']})": l['id'] for l in leads}
        selected_label = st.selectbox("Select Business to Inspect & Research", options=list(biz_options.keys()))
        selected_id = biz_options[selected_label]
        lead_data = next((l for l in leads if l["id"] == selected_id), None)

        if lead_data:
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown(f"### {lead_data['name']}")
                st.markdown(f"**Website:** [{lead_data['website_url']}]({lead_data['website_url']})")
                st.markdown(f"**Industry:** {lead_data['industry']} | **Location:** {lead_data['city'] or 'N/A'}, {lead_data['country']}")
            with col_r:
                status_color = {
                    "Completed": "green",
                    "Partial": "orange",
                    "Blocked": "red",
                    "Not Researched": "gray",
                }.get(lead_data["crawl_status"], "gray")
                st.markdown(
                    f"**Crawl Status:** <span style='color:{status_color};font-weight:bold;'>{lead_data['crawl_status']}</span> "
                    f"({lead_data.get('crawled_pages_count', 0)} pages crawled)",
                    unsafe_allow_html=True,
                )
                if st.button("🚀 Run Website Research", type="primary"):
                    with st.spinner(f"Crawling {lead_data['website_url']} responsibly..."):
                        research_business(selected_id)
                    st.success("Website research completed!")
                    st.rerun()

            st.markdown("---")

            # Display Research Findings
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown("##### 📧 Public Email")
                if lead_data.get("public_email"):
                    st.success(f"**{lead_data['public_email']}**")
                    st.caption(f"Status: **{lead_data['email_status']}**")
                    if lead_data.get("email_source_url"):
                        st.caption(f"Source: [{lead_data['email_source_url']}]({lead_data['email_source_url']})")
                else:
                    st.warning("No public email address identified.")

            with r2:
                st.markdown("##### 📞 Public Phone")
                if lead_data.get("public_phone"):
                    st.success(f"**{lead_data['public_phone']}**")
                    st.caption(f"Status: **{lead_data['phone_status']}**")
                    if lead_data.get("phone_source_url"):
                        st.caption(f"Source: [{lead_data['phone_source_url']}]({lead_data['phone_source_url']})")
                else:
                    st.caption("No public phone number detected.")

            with r3:
                st.markdown("##### 🔗 Professional Profiles")
                if lead_data.get("linkedin_url"):
                    st.markdown(f"LinkedIn: [{lead_data['linkedin_url']}]({lead_data['linkedin_url']})")
                else:
                    st.caption("No LinkedIn company page found.")
                if lead_data.get("contact_page_url"):
                    st.markdown(f"Contact Page: [{lead_data['contact_page_url']}]({lead_data['contact_page_url']})")

            st.markdown("##### 📝 Company Overview & Extracted About")
            st.text_area(
                "About Summary",
                value=lead_data.get("about_summary") or "No detailed about summary available yet.",
                height=100,
                disabled=True,
            )

            st.markdown("##### 🛠️ Extracted Services & Offerings")
            st.text_area(
                "Services Offered",
                value=lead_data.get("services_offered") or "No distinct services list identified.",
                height=100,
                disabled=True,
            )

    with tab_batch:
        unresearched = [l for l in leads if l["crawl_status"] in ("Not Researched", "Pending")]
        st.markdown(f"**Pending Unresearched Leads:** `{len(unresearched)}` of `{len(leads)}` total leads.")

        if unresearched:
            if st.button(f"⚡ Batch Research {len(unresearched)} Pending Leads", type="primary"):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                for i, lead in enumerate(unresearched):
                    status_text.text(f"Crawling ({i+1}/{len(unresearched)}): {lead['name']}...")
                    try:
                        research_business(lead["id"])
                    except Exception as e:
                        st.warning(f"Error researching {lead['name']}: {e}")
                    progress_bar.progress((i + 1) / len(unresearched))
                status_text.text("Batch enrichment finished!")
                st.success("All pending leads researched!")
                st.rerun()
        else:
            st.success("All leads in your database have already been researched!")


render_research()
