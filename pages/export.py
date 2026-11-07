"""
Export Data page: CSV downloads for the full pipeline and filtered subsets.
"""
import streamlit as st

from modules.exporter import EXPORT_PRESETS, export_leads_to_csv


def render_export():
    st.markdown("## Export Data")
    st.caption("Download UTF-8 CSV files you can open in Excel, Google Sheets, or a CRM import tool.")

    preset = st.selectbox("Which leads should be included?", options=EXPORT_PRESETS)
    st.markdown(
        """
        - **All Discovered Leads** includes every saved business.
        - **High-Priority Leads Only** includes scores from 80 to 100.
        - **Leads with Available Email Addresses** includes a public email found on a website or entered by you.
        - **Leads with Generated Email Drafts** includes saved outreach drafts.
        """
    )

    if st.button("Prepare CSV", type="primary"):
        csv_bytes, count, filename = export_leads_to_csv(preset)
        st.session_state["export_payload"] = {
            "bytes": csv_bytes,
            "count": count,
            "filename": filename,
            "preset": preset,
        }

    payload = st.session_state.get("export_payload")
    if payload and payload.get("preset") == preset:
        st.success(f"{payload['count']} lead(s) are ready in `{payload['filename']}`.")
        st.download_button(
            label="Download CSV",
            data=payload["bytes"],
            file_name=payload["filename"],
            mime="text/csv",
            type="primary",
        )
        if payload["count"] == 0:
            st.info("The file contains column headers only, because no leads matched this filter.")


render_export()
