"""
Lead Management Page: Full CRUD operations, multi-criteria filtering, search, status progression, and notes.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from modules.lead_manager import (
    get_all_leads_enriched,
    update_lead_details,
    update_lead_contact_info,
    update_lead_outreach_status,
    delete_lead,
    get_unique_industries,
)
from utils.helpers import format_score_badge, format_status_badge


def render_lead_management():
    st.markdown("## 👥 Lead Management Hub")
    st.caption("Organize, track, filter, and manage your prospect pipeline with persistent database storage.")

    # Top Filters Row
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
    
    with f_col1:
        search_query = st.text_input("🔍 Search Leads", placeholder="Company, domain, city, or email...")
    
    with f_col2:
        industries = ["All"] + get_unique_industries()
        industry_filter = st.selectbox("Industry", options=industries)
        
    with f_col3:
        qualification_filter = st.selectbox("Qualification", options=["All", "High Priority", "Medium Priority", "Low Priority"])
        
    with f_col4:
        outreach_filter = st.selectbox("Outreach Status", options=["All", "Not Started", "Draft Created", "Reviewed", "Ready to Send", "Contacted"])
        
    with f_col5:
        sort_by = st.selectbox(
            "Sort By",
            options=["Score (High to Low)", "Score (Low to High)", "Newest First", "Oldest First", "Company Name (A-Z)"],
        )

    min_score = st.slider("Minimum lead score", min_value=0, max_value=100, value=0, step=5)

    # Fetch leads
    leads = get_all_leads_enriched(
        search_query=search_query,
        industry_filter=industry_filter,
        qualification_filter=qualification_filter,
        outreach_filter=outreach_filter,
        sort_by=sort_by,
        min_score=min_score,
    )

    st.markdown(f"**Showing `{len(leads)}` matching leads**")

    if not leads:
        st.info("No leads match the specified filter criteria.")
        return

    # Leads Overview Table
    table_rows = []
    for l in leads:
        table_rows.append({
            "ID": l["id"],
            "Company": l["name"],
            "Domain": l["normalized_domain"],
            "Industry": l["industry"],
            "Location": f"{l['city'] or ''}, {l['country']}".strip(", "),
            "Score": l["lead_score"],
            "Priority": l["qualification_status"],
            "Email": l["public_email"] or "—",
            "Outreach Status": l["outreach_status"],
        })

    df_view = pd.DataFrame(table_rows)
    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score",
                format="%d/100",
                min_value=0,
                max_value=100,
            ),
        },
    )

    st.markdown("---")
    st.markdown("### ✏️ Inspect & Edit Lead Record")

    # Lead detail selector for editing
    lead_choices = {f"#{l['id']} - {l['name']} ({l['normalized_domain']})": l['id'] for l in leads}
    selected_label = st.selectbox("Select Lead to Edit", options=list(lead_choices.keys()))
    selected_id = lead_choices[selected_label]
    lead = next((l for l in leads if l["id"] == selected_id), None)

    if lead:
        edit_tab1, edit_tab2, edit_tab3, edit_tab4 = st.tabs(["Company Profile", "Contact Info", "Outreach & Notes", "Danger Zone"])

        with edit_tab1:
            with st.form(f"edit_company_form_{selected_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Company Name", value=lead["name"])
                    industry = st.text_input("Industry", value=lead["industry"])
                    website_url = st.text_input("Website URL", value=lead["website_url"])
                with c2:
                    country = st.text_input("Country", value=lead["country"])
                    city = st.text_input("City", value=lead["city"] or "")
                    business_type = st.text_input("Business Type", value=lead["business_type"] or "")
                
                description = st.text_area("Company Description", value=lead["description"] or "", height=80)

                if st.form_submit_button("Update Company Profile", type="primary"):
                    update_lead_details(
                        business_id=selected_id,
                        name=name,
                        industry=industry,
                        country=country,
                        city=city,
                        business_type=business_type,
                        description=description,
                        website_url=website_url,
                    )
                    st.success("Company profile updated!")
                    st.rerun()

        with edit_tab2:
            with st.form(f"edit_contact_form_{selected_id}"):
                email = st.text_input("Public Business Email", value=lead["public_email"] or "")
                phone = st.text_input("Public Phone Number", value=lead["public_phone"] or "")
                linkedin = st.text_input("LinkedIn Company URL", value=lead["linkedin_url"] or "")

                if st.form_submit_button("Update Contact Details", type="primary"):
                    update_lead_contact_info(
                        business_id=selected_id,
                        email=email,
                        phone=phone,
                        linkedin=linkedin,
                    )
                    st.success("Contact details updated!")
                    st.rerun()

        with edit_tab3:
            with st.form(f"edit_outreach_form_{selected_id}"):
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    current_status = lead.get("outreach_status") or "Not Started"
                    status_idx = ["Not Started", "Draft Created", "Reviewed", "Ready to Send", "Contacted"].index(current_status) if current_status in ["Not Started", "Draft Created", "Reviewed", "Ready to Send", "Contacted"] else 0
                    outreach_status = st.selectbox(
                        "Outreach Pipeline Status",
                        ["Not Started", "Draft Created", "Reviewed", "Ready to Send", "Contacted"],
                        index=status_idx,
                    )
                with col_o2:
                    curr_fu = lead.get("follow_up_date")
                    fu_val = curr_fu.date() if isinstance(curr_fu, datetime) else None
                    follow_up = st.date_input("Follow-Up Calendar Date", value=fu_val)

                notes = st.text_area("Internal Sales / Outreach Notes", value=lead.get("notes") or "", height=100)

                if st.form_submit_button("Update Outreach Progression", type="primary"):
                    update_lead_outreach_status(
                        business_id=selected_id,
                        outreach_status=outreach_status,
                        notes=notes,
                        follow_up_date=follow_up,
                    )
                    st.success("Outreach progress updated!")
                    st.rerun()

        with edit_tab4:
            st.error("⚠️ Deleting a business lead is permanent and removes all associated research, scores, and email drafts.")
            if st.button(f"🗑️ Permanently Delete '{lead['name']}'", type="secondary"):
                delete_lead(selected_id)
                st.warning(f"Deleted lead '{lead['name']}'.")
                st.rerun()


render_lead_management()
