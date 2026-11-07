"""
Settings page: sender defaults, database status, and local research limits.
"""
import streamlit as st

from config.settings import (
    APP_ENV,
    DATABASE_URL,
    HTTP_TIMEOUT_SECONDS,
    IS_POSTGRES,
    IS_SQLITE,
    MAX_CRAWL_PAGES_PER_SITE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    REQUEST_DELAY_SECONDS,
)
from database.db import test_connection
from modules.email_generator import check_ollama_status
from utils.helpers import get_setting, set_setting


def render_settings():
    st.markdown("## Settings")
    st.caption("These values are stored in the database and reused by the email generator.")

    with st.form("company_settings_form"):
        sender_company = st.text_input(
            "Your company name",
            value=get_setting("sender_company", "Apex Growth AI"),
        )
        sender_offering = st.text_input(
            "Product or service",
            value=get_setting("sender_offering", "B2B lead research workflow"),
        )
        value_proposition = st.text_area(
            "Value proposition",
            value=get_setting(
                "value_proposition",
                "reduce manual prospect research before the first outreach email",
            ),
            height=80,
        )
        purpose = st.text_input(
            "Default outreach purpose",
            value=get_setting("outreach_purpose", "a short introductory conversation"),
        )
        if st.form_submit_button("Save sender profile", type="primary"):
            set_setting("sender_company", sender_company.strip())
            set_setting("sender_offering", sender_offering.strip())
            set_setting("value_proposition", value_proposition.strip())
            set_setting("outreach_purpose", purpose.strip())
            for key in ("sender_company", "sender_offering", "value_prop", "purpose"):
                st.session_state.pop(key, None)
            st.success("Sender profile saved. Open Email Generator to use the new defaults.")

    st.markdown("---")
    st.markdown("### Database")
    connected, message = test_connection()
    if connected:
        st.success(message)
    else:
        st.error(message)

    engine_name = "SQLite" if IS_SQLITE else "PostgreSQL" if IS_POSTGRES else "Other"
    safe_url = DATABASE_URL
    if "@" in safe_url:
        safe_url = safe_url.split("@")[-1]
    st.write(f"**Engine:** {engine_name}")
    st.write(f"**Environment:** {APP_ENV}")
    st.code(safe_url, language="text")
    st.caption("Change DATABASE_URL in the .env file, then restart the app. Do not put passwords in source code.")

    st.markdown("---")
    st.markdown("### Research limits")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pages per website", MAX_CRAWL_PAGES_PER_SITE)
    c2.metric("Request timeout (seconds)", HTTP_TIMEOUT_SECONDS)
    c3.metric("Delay between pages", REQUEST_DELAY_SECONDS)
    st.caption("Edit these in the .env file. The crawler only reads public pages and does not bypass logins or CAPTCHA.")

    st.markdown("---")
    st.markdown("### Optional local model")
    available, ollama_message = check_ollama_status()
    if available:
        st.success(ollama_message)
    else:
        st.info(ollama_message)
    st.write(f"Configured model: `{OLLAMA_MODEL}` at `{OLLAMA_BASE_URL}`")
    st.caption("Ollama is optional. Email drafts work with the built-in templates when it is not installed.")


render_settings()
