"""
Dashboard Page: High-level KPI metrics, pipeline analytics, and activity feed.
"""
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database.db import get_db
from database.models import Business, LeadResearch, LeadQualification, EmailDraft, ActivityLog
from modules.lead_manager import get_all_leads_enriched


def render_dashboard():
    st.markdown("## 📊 Executive Dashboard")
    st.caption("Real-time pipeline overview of your discovered B2B prospects and outreach readiness.")

    leads = get_all_leads_enriched()
    total_leads = len(leads)

    high_priority = len([l for l in leads if l.get("lead_score", 0) >= 80])
    emails_found = len([l for l in leads if l.get("public_email")])
    drafts_created = len([l for l in leads if l.get("email_body")])
    contacted_count = len([l for l in leads if l.get("outreach_status") == "Contacted"])

    # 1. KPI Cards Row
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    with kpi_col1:
        st.metric(label="Total Discovered", value=total_leads, delta=f"+{total_leads} leads" if total_leads else None)
    with kpi_col2:
        st.metric(label="High-Priority Leads", value=high_priority, delta=f"{(high_priority/total_leads*100):.0f}% of total" if total_leads else None)
    with kpi_col3:
        st.metric(label="Public Emails Found", value=emails_found, delta=f"{(emails_found/total_leads*100):.0f}% rate" if total_leads else None)
    with kpi_col4:
        st.metric(label="Drafts Generated", value=drafts_created)
    with kpi_col5:
        st.metric(label="Leads Contacted", value=contacted_count)

    st.markdown("---")

    if total_leads == 0:
        st.info("💡 No leads discovered yet! Navigate to **Discover Leads** to start your first B2B search.")
        return

    # 2. Charts Row
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("##### 🎯 Lead Score Distribution")
        df_leads = pd.DataFrame(leads)
        
        # Color score groups
        fig_hist = px.histogram(
            df_leads,
            x="lead_score",
            nbins=10,
            color="qualification_status",
            color_discrete_map={
                "High Priority": "#2E7D32",
                "Medium Priority": "#F57C00",
                "Low Priority": "#D32F2F",
                "Not Qualified": "#757575",
            },
            labels={"lead_score": "Qualification Score (0-100)", "count": "Businesses"},
            title="",
        )
        fig_hist.update_layout(
            margin=dict(l=20, r=20, t=10, b=20),
            height=300,
            bargap=0.1,
            legend_title_text="",
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with chart_col2:
        st.markdown("##### 📈 Outreach Preparation Funnel")
        researched_count = len([l for l in leads if l.get("crawl_status") in ("Completed", "Partial")])
        qualified_count = len([l for l in leads if l.get("qualification_status") != "Not Qualified"])

        funnel_data = dict(
            number=[total_leads, researched_count, qualified_count, drafts_created, contacted_count],
            stage=["Discovered", "Website Researched", "Scored / Qualified", "Draft Ready", "Contacted"],
        )
        fig_funnel = px.funnel(funnel_data, x="number", y="stage", color_discrete_sequence=["#1976D2"])
        fig_funnel.update_layout(
            margin=dict(l=20, r=20, t=10, b=20),
            height=300,
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

    # 3. Industry Breakdown & Recent Discoveries
    lower_col1, lower_col2 = st.columns([1, 1])

    with lower_col1:
        st.markdown("##### 🏢 Leads by Industry")
        ind_counts = df_leads["industry"].value_counts().reset_index()
        ind_counts.columns = ["Industry", "Count"]
        fig_pie = px.pie(
            ind_counts,
            names="Industry",
            values="Count",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_pie.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("##### Recent discoveries")
        recent = sorted(
            leads,
            key=lambda item: item.get("date_discovered") or datetime.min,
            reverse=True,
        )[:6]
        recent_rows = [
            {
                "Company": item["name"],
                "Website": item["website_url"],
                "Industry": item["industry"],
                "Score": item["lead_score"],
                "Source": item.get("discovery_source") or "",
            }
            for item in recent
        ]
        st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)

    with lower_col2:
        st.markdown("##### ⏱️ Recent Activity Stream")
        with get_db() as session:
            logs = session.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(7).all()
            if logs:
                for log in logs:
                    time_str = log.timestamp.strftime("%b %d, %H:%M")
                    st.markdown(
                        f"""
                        <div style="padding:6px 12px;margin-bottom:6px;background-color:#F8F9FA;border-left:3px solid #1A73E8;border-radius:4px;font-size:0.87rem;">
                            <strong>{log.action}</strong> • <span style="color:#666;">{time_str}</span><br/>
                            <span style="color:#444;">{log.details or ''}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No recent events logged yet.")


render_dashboard()
