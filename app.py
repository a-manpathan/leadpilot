"""
LeadPilot entry point.
Run with: streamlit run app.py
"""
import logging

import streamlit as st

from database.db import init_db, test_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(
    page_title="LeadPilot",
    page_icon="LP",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #E6EAF2;
        border-radius: 12px;
        padding: 12px 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    init_db()
except Exception as exc:
    st.error(f"The database could not be created. Check DATABASE_URL in your .env file. Details: {exc}")
    st.stop()

ok, message = test_connection()
with st.sidebar:
    st.markdown("## LeadPilot")
    st.caption("B2B lead generation and outreach preparation.")
    if ok:
        st.success("Database connected")
    else:
        st.error(message)
    st.caption("Emails are drafted only. This app does not send email.")

pages = [
    st.Page("pages/dashboard.py", title="Dashboard", default=True),
    st.Page("pages/discover.py", title="Discover Leads"),
    st.Page("pages/research.py", title="Research & Enrichment"),
    st.Page("pages/qualification.py", title="Lead Qualification"),
    st.Page("pages/email_generator.py", title="Email Generator"),
    st.Page("pages/lead_management.py", title="Lead Management"),
    st.Page("pages/export.py", title="Export Data"),
    st.Page("pages/settings.py", title="Settings"),
]

navigation = st.navigation(pages)
navigation.run()
