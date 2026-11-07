"""
Discover Leads Page: Search query generation, live DuckDuckGo discovery, deduplication, and database persistence.
"""
import streamlit as st
import pandas as pd
from modules.discovery import (
    generate_search_queries,
    discover_businesses,
    save_discovered_leads,
)
from utils.search import MockSearchProvider


def render_discover():
    st.markdown("## 🔍 B2B Business Discovery")
    st.caption("Discover potential commercial clients and agencies using targeted free search queries.")

    # Form inputs
    with st.form("discovery_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            industry = st.text_input(
                "Industry or Business Niche *",
                value="Digital Marketing Agencies",
                help="E.g. Digital Marketing Agencies, Logistics Providers, SaaS Solutions, IT Staffing",
            )
            target_country = st.text_input(
                "Target Country *",
                value="India",
                help="Country where your prospects operate.",
            )
        with col2:
            target_city = st.text_input(
                "Target City (Optional)",
                value="Bengaluru",
                help="Leave blank to search nationwide.",
            )
            business_type = st.text_input(
                "Business Type / Profile",
                value="B2B service providers",
                help="E.g. B2B service providers, Commercial manufacturers, Software consultants",
            )

        col_opt1, col_opt2 = st.columns([1, 1])
        with col_opt1:
            max_prospects = st.slider("Maximum Prospects to Find", min_value=5, max_value=50, value=15, step=5)
        with col_opt2:
            skip_aggregators = st.checkbox("Filter out common directory aggregators (Yelp, Clutch, Wikipedia)", value=True)
            use_sample_data = st.checkbox(
                "Use offline sample data",
                value=False,
                help="Loads clearly labeled demonstration businesses when you want to try the app without live search.",
            )

        submitted = st.form_submit_button("🚀 Discover Prospects", use_container_width=True)

    # Search Query Preview
    with st.expander("🔎 View Generated Search Query Variations", expanded=False):
        preview_queries = generate_search_queries(industry, target_country, target_city, business_type)
        for i, q in enumerate(preview_queries, 1):
            st.markdown(f"**Query {i}:** `{q}`")

    if submitted:
        if not industry.strip() or not target_country.strip():
            st.error("Please provide both an Industry and Target Country.")
            return

        with st.spinner("Searching DuckDuckGo and aggregating clean business domains..."):
            discovered, stats = discover_businesses(
                industry=industry.strip(),
                country=target_country.strip(),
                city=target_city.strip(),
                business_type=business_type.strip(),
                max_results=max_prospects,
                skip_aggregators=skip_aggregators,
                search_provider=MockSearchProvider() if use_sample_data else None,
            )
            if use_sample_data:
                stats["fallback_used"] = True

        st.session_state["last_discovery_results"] = discovered
        st.session_state["last_discovery_stats"] = stats

    if "last_discovery_results" in st.session_state:
        results = st.session_state["last_discovery_results"]
        stats = st.session_state["last_discovery_stats"]

        if stats.get("fallback_used"):
            st.warning(
                "⚠️ External search encountered temporary rate limits. "
                "Sample demonstration prospects have been loaded so you can continue testing seamlessly. "
                "All sample data is clearly tagged in the source column."
            )

        # Summary Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Candidates Found", len(results))
        with m2:
            st.metric("New to Database", stats.get("new_leads_ready", 0))
        with m3:
            st.metric("Already in Database", stats.get("already_in_db", 0))
        with m4:
            st.metric("Aggregators Filtered", stats.get("aggregators_skipped", 0))

        if results:
            st.markdown("#### Discovered Candidates")
            
            table_data = []
            for item in results:
                table_data.append({
                    "Status": "✅ Already Saved" if item["already_in_db"] else "✨ New Candidate",
                    "Company Name": item["name"],
                    "Domain": item["normalized_domain"],
                    "Website URL": item["website_url"],
                    "Industry": item["industry"],
                    "Location": f"{item.get('city') or ''}, {item.get('country')}".strip(", "),
                    "Source": item["discovery_source"],
                })

            df_view = pd.DataFrame(table_data)
            st.dataframe(
                df_view,
                use_container_width=True,
                column_config={
                    "Website URL": st.column_config.LinkColumn("Website URL"),
                },
                hide_index=True,
            )

            # Save Button
            new_leads = [l for l in results if not l["already_in_db"]]
            if new_leads:
                if st.button(f"💾 Save {len(new_leads)} New Leads to Database", type="primary"):
                    saved, skipped = save_discovered_leads(new_leads)
                    st.success(f"Successfully saved {saved} prospects to the database! ({skipped} duplicates skipped).")
                    # Update session state to mark as saved
                    for item in results:
                        item["already_in_db"] = True
                    st.session_state["last_discovery_stats"]["new_leads_ready"] = 0
                    st.rerun()
            else:
                st.info("All discovered prospects from this run are already saved in your database.")


render_discover()
