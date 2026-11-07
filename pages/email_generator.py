"""
Email Generator Page: Grounded cold outreach drafting across 4 tones with copy-ready exports and draft storage.
"""
import streamlit as st
from modules.email_generator import (
    generate_email,
    save_email_draft,
    check_ollama_status,
    TONES,
)
from modules.lead_manager import get_all_leads_enriched
from utils.helpers import get_setting
import json
import streamlit.components.v1 as components


def _clipboard_button(label: str, text: str):
    """Browser copy button. The code block copy icon remains available as a fallback."""
    payload = json.dumps(text)
    components.html(
        f"""
        <button
          style="background:#1D4ED8;color:#fff;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer;"
          onclick="navigator.clipboard.writeText({payload}).then(() => {{ this.innerText = 'Copied'; }})"
        >{label}</button>
        """,
        height=46,
    )


def render_email_generator():
    st.markdown("## ✉️ Personalized Cold Email Generator")
    st.caption("Craft authentic, high-converting outreach grounded strictly in the prospect's real business data.")

    st.info("💡 **Grounded Outreach Rule:** LeadPilot uses verified research data and never hallucinates fake meetings or personal relationships. Automatic sending is intentionally disabled so you retain complete control over your sender reputation.")

    leads = get_all_leads_enriched()
    if not leads:
        st.info("No leads available. Please discover prospects first in **Discover Leads**.")
        return

    # Check Ollama AI status
    ollama_ok, ollama_msg = check_ollama_status()

    # Lead Selector
    biz_options = {
        f"{l['name']} | {l.get('public_email') or 'No email'} | Score: {l.get('lead_score', 0)}/100": l['id']
        for l in leads
    }
    selected_label = st.selectbox("Select Target Business", options=list(biz_options.keys()))
    selected_id = biz_options[selected_label]
    lead = next((l for l in leads if l["id"] == selected_id), None)

    if "sender_company" not in st.session_state:
        st.session_state["sender_company"] = get_setting("sender_company", "Apex Growth AI")
        st.session_state["sender_offering"] = get_setting("sender_offering", "B2B lead research workflow")
        st.session_state["value_prop"] = get_setting(
            "value_proposition",
            "reduce manual prospect research before the first outreach email",
        )
        st.session_state["purpose"] = get_setting("outreach_purpose", "a short introductory conversation")

    # Sender & Campaign Configuration Form
    with st.expander("💼 Your Sender Profile & Value Proposition", expanded=True):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sender_company = st.text_input("Your Company / Brand Name *", key="sender_company")
            sender_offering = st.text_input("Your Product or Service *", key="sender_offering")
        with col_s2:
            value_prop = st.text_input("Value Proposition *", key="value_prop")
            purpose = st.text_input("Outreach Objective / Purpose *", key="purpose")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tone = st.selectbox("Desired Email Tone", options=TONES, index=0)
        with col_t2:
            use_ollama = st.checkbox(
                f"Use Local Ollama AI ({ollama_msg})",
                value=False,
                disabled=not ollama_ok,
                help="Requires Ollama running on localhost:11434.",
            )

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        generate_clicked = st.button("✨ Generate Email", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("🔄 Regenerate", use_container_width=False):
            generate_clicked = True

    # Check if existing draft exists in DB
    existing_draft = lead.get("email_body")

    if generate_clicked:
        if not sender_company.strip() or not sender_offering.strip() or not value_prop.strip():
            st.error("Please fill in your Sender Company, Offering, and Value Proposition.")
            return

        with st.spinner("Synthesizing grounded cold email draft..."):
            email_res = generate_email(
                business_id=selected_id,
                sender_company=sender_company,
                sender_offering=sender_offering,
                value_proposition=value_prop,
                purpose=purpose,
                tone=tone,
                use_ollama=use_ollama,
            )
        st.session_state[f"draft_{selected_id}"] = email_res

    # Display active draft
    active_draft = st.session_state.get(f"draft_{selected_id}")

    if active_draft:
        st.markdown("---")
        st.markdown(f"### 📋 Outreach Draft Preview ({active_draft.get('tone', tone)} Tone)")

        st.markdown("##### 📌 Subject Line")
        st.caption("Use the copy icon on the right of each box.")
        st.code(active_draft["subject"], language="text")
        copy_col1, copy_col2 = st.columns(2)
        with copy_col1:
            _clipboard_button("Copy subject", active_draft["subject"])
        with copy_col2:
            _clipboard_button("Copy email body", active_draft["full_body"])

        st.markdown("##### ✉️ Email Body")
        st.code(active_draft["full_body"], language="text")

        # Breakdown Sections
        with st.expander("🔍 Inspect Email Components & Grounding"):
            st.markdown(f"**Personalized Opening:**\n> {active_draft.get('personalized_opening')}")
            st.markdown(f"**Business Context:**\n> {active_draft.get('business_context')}")
            st.markdown(f"**Value Proposition:**\n> {active_draft.get('value_proposition')}")
            st.markdown(f"**Call to Action:**\n> {active_draft.get('call_to_action')}")

        # Save Draft Options Form
        st.markdown("---")
        st.markdown("##### 💾 Save & Manage Draft")
        with st.form(f"save_draft_form_{selected_id}"):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                outreach_status = st.selectbox(
                    "Outreach Status",
                    ["Draft Created", "Reviewed", "Ready to Send", "Contacted"],
                    index=0,
                )
                set_follow_up = st.checkbox("Set a follow-up date", value=False)
                follow_up_date = st.date_input("Follow-up date") if set_follow_up else None
            with col_d2:
                notes = st.text_area("Internal Outreach Notes", value=lead.get("notes") or "", height=100)

            if st.form_submit_button("Save Draft to Lead Record", type="primary"):
                save_email_draft(
                    business_id=selected_id,
                    email_data=active_draft,
                    sender_company=sender_company,
                    sender_offering=sender_offering,
                    outreach_status=outreach_status,
                    notes=notes,
                    follow_up_date=follow_up_date,
                )
                st.success("Draft and status successfully saved into lead management database!")
                st.rerun()

    elif existing_draft:
        st.markdown("---")
        st.markdown(f"### 📄 Existing Saved Draft ({lead.get('email_tone') or 'Professional'} Tone)")
        st.markdown(f"**Subject:** `{lead.get('email_subject')}`")
        st.code(existing_draft, language="text")
        st.caption(f"Current Status: **{lead.get('outreach_status')}** | Notes: {lead.get('notes') or 'None'}")


render_email_generator()
