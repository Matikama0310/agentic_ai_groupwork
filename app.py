"""
Streamlit Underwriting Workbench - Human-in-the-Loop UI.
Maps to Phase 3 "The Workbench" in the architecture diagram.

Run: streamlit run app.py
"""

import json
import streamlit as st
from datetime import datetime

from src.orchestration.supervisor_agent import SupervisorAgent
from src.core.state_manager import get_state_manager, DecisionType

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NorthStar Underwriting Workbench",
    page_icon="📋",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Initialize session state
# ---------------------------------------------------------------------------
if "supervisor" not in st.session_state:
    st.session_state.supervisor = SupervisorAgent()
if "state_manager" not in st.session_state:
    st.session_state.state_manager = get_state_manager()
if "current_submission" not in st.session_state:
    st.session_state.current_submission = None

sm = st.session_state.state_manager

# ---------------------------------------------------------------------------
# Sidebar - Submit new application
# ---------------------------------------------------------------------------
st.sidebar.title("NorthStar Insurance")
st.sidebar.subheader("Submit New Application")

with st.sidebar.form("submission_form"):
    email_subject = st.text_input("Email Subject", value="Application for Acme Restaurant Inc.")
    email_body = st.text_area(
        "Email Body",
        value="We are submitting an application for general liability coverage for Acme Restaurant Inc., "
              "a full-service restaurant located at 123 Main St, Springfield, IL. "
              "The business has been operating since 2015 with 12 employees and $500,000 annual revenue.",
        height=150,
    )
    broker_email = st.text_input("Broker Email", value="broker@example.com")
    broker_name = st.text_input("Broker Name", value="John Smith")
    submitted = st.form_submit_button("Submit Application", type="primary")

if submitted:
    with st.spinner("Processing submission through AI agents..."):
        sub_id = f"SUB-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        state = st.session_state.supervisor.process_submission(
            submission_id=sub_id,
            email_subject=email_subject,
            email_body=email_body,
            broker_email=broker_email,
            broker_name=broker_name,
            attachments=[],
        )
        st.session_state.current_submission = sub_id
    st.sidebar.success(f"Processed: {sub_id}")

# ---------------------------------------------------------------------------
# Sidebar - View existing submissions
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Existing Submissions")
all_subs = sm.list_submissions()
if all_subs:
    selected = st.sidebar.selectbox(
        "Select Submission",
        [s["submission_id"] for s in all_subs],
        index=0,
    )
    if st.sidebar.button("Load Submission"):
        st.session_state.current_submission = selected
else:
    st.sidebar.info("No submissions yet. Submit one above.")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("Underwriting Workbench")

sub_id = st.session_state.current_submission
if not sub_id:
    st.info("Submit a new application or select an existing one from the sidebar.")
    st.stop()

state = sm.get_state(sub_id)
if not state:
    st.error(f"Submission {sub_id} not found.")
    st.stop()

summary = sm.get_submission_summary(sub_id)

# ---------------------------------------------------------------------------
# Status header
# ---------------------------------------------------------------------------
decision_colors = {
    "QUOTED": "green",
    "DECLINED": "red",
    "MISSING_INFO": "orange",
    "MANUAL_REVIEW": "blue",
    "UNKNOWN": "gray",
}
color = decision_colors.get(state.decision, "gray")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Submission ID", sub_id)
col2.metric("Status", state.status)
col3.markdown(f"**Decision:** :{color}[{state.decision}]")
col4.metric("Created", state.created_at[:19])

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_data, tab_risk, tab_email, tab_audit, tab_override = st.tabs(
    ["Overview", "Extracted Data", "Risk Assessment", "Drafted Email", "Audit Trail", "Human Override"]
)

# --- Tab 1: Overview ---
with tab_overview:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Applicant Info")
        ed = state.extracted_data or {}
        st.write(f"**Name:** {ed.get('applicant_name', 'N/A')}")
        st.write(f"**Business Type:** {ed.get('business_type', 'N/A')}")
        st.write(f"**NAICS Code:** {state.naics_code or 'N/A'}")
        st.write(f"**Address:** {ed.get('address', 'N/A')}")
        st.write(f"**Years in Business:** {ed.get('years_in_business', 'N/A')}")
        st.write(f"**Employees:** {ed.get('employees', 'N/A')}")
        st.write(f"**Annual Revenue:** ${ed.get('annual_revenue', 0):,.0f}")

    with c2:
        st.subheader("External Data")
        ext = state.external_data or {}
        st.write(f"**Credit Score:** {ext.get('credit_score', 'N/A')}")
        st.write(f"**Financial Health:** {ext.get('financial_health', 'N/A')}")
        pr = ext.get("property_risk", {})
        st.write(f"**Flood Zone:** {pr.get('flood_zone', 'N/A')}")
        st.write(f"**Crime Score:** {pr.get('crime_score', 'N/A')}")

        web = state.web_data or {}
        st.write(f"**Website Verified:** {web.get('website_verified', 'N/A')}")
        st.write(f"**Reviews:** {web.get('public_reviews_summary', 'N/A')}")

    # Validation results
    vr = state.validation_result or {}
    if vr.get("failed_rules"):
        st.error("Failed Underwriting Rules:")
        for rule in vr["failed_rules"]:
            st.write(f"  - **{rule['rule_description']}**: {rule['reason']}")
    elif vr.get("missing_critical_docs"):
        st.warning("Missing Critical Documents:")
        for doc in vr["missing_critical_docs"]:
            st.write(f"  - {doc.replace('_', ' ').title()}")
    elif vr.get("passes_guidelines"):
        st.success("All underwriting guidelines passed.")

# --- Tab 2: Extracted Data ---
with tab_data:
    st.subheader("Extracted Data (OCR + Schema Mapping)")
    st.write(f"**Extraction Confidence:** {state.extraction_confidence or 'N/A'}")
    if state.extracted_data:
        st.json(state.extracted_data)
    else:
        st.info("No extracted data available.")

    st.subheader("Internal Claims History")
    if state.internal_data:
        st.json(state.internal_data)
    else:
        st.info("No internal data available.")

# --- Tab 3: Risk Assessment ---
with tab_risk:
    st.subheader("Risk Metrics & Pricing")
    if state.risk_metrics:
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Risk Score", f"{state.risk_metrics.get('risk_score', 0):.1f}/100")
        rc2.metric("Annual Premium", f"${state.risk_metrics.get('annual_premium', 0):,.2f}")
        rc3.metric("Loss Ratio", f"{state.risk_metrics.get('loss_ratio', 0):.2%}")
        rc4.metric("Debt/Equity", f"{state.risk_metrics.get('debt_to_equity', 0):.2f}")

        st.write(f"**Pricing Rationale:** {state.risk_metrics.get('pricing_rationale', '')}")
    else:
        st.info("Risk assessment not yet completed.")

    if state.quote_pdf_url:
        st.write(f"**Quote PDF:** `{state.quote_pdf_url}`")

# --- Tab 4: Drafted Email ---
with tab_email:
    st.subheader("Drafted Communication")
    if state.drafted_email:
        st.write(f"**To:** {state.drafted_email.get('to', state.broker_email)}")
        st.write(f"**Subject:** {state.drafted_email.get('subject', '')}")
        st.text_area("Email Body", state.drafted_email.get("body", ""), height=300, disabled=True)
        if not state.drafted_email.get("ready_to_send"):
            st.warning("This email requires human review before sending.")
    else:
        st.info("No email drafted yet.")

# --- Tab 5: Audit Trail ---
with tab_audit:
    st.subheader("Audit Trail")
    if state.audit_trail:
        for entry in reversed(state.audit_trail):
            if hasattr(entry, "timestamp"):
                ts, comp, act, res = entry.timestamp, entry.component, entry.action, entry.result
            else:
                ts = entry.get("timestamp", "")
                comp = entry.get("component", "")
                act = entry.get("action", "")
                res = entry.get("result", "")
            st.write(f"**{ts}** | `{comp}` | {act} | {res}")
    else:
        st.info("No audit entries yet.")

# --- Tab 6: Human Override ---
with tab_override:
    st.subheader("Human Decision (Override)")
    st.write(f"**Current AI Decision:** {state.decision}")

    with st.form("override_form"):
        new_decision = st.selectbox(
            "Override Decision",
            ["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"],
            index=["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"].index(
                state.decision if state.decision in ["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"] else "MANUAL_REVIEW"
            ),
        )
        reason = st.text_area("Override Reason", placeholder="Explain why you are overriding the AI decision...")
        user_id = st.text_input("Your User ID", value="underwriter-001")
        override_submitted = st.form_submit_button("Apply Override", type="primary")

    if override_submitted:
        if not reason.strip():
            st.error("Please provide a reason for the override.")
        else:
            sm.apply_override(sub_id, user_id, new_decision, reason)
            st.success(f"Override applied: {state.decision} → {new_decision}")
            st.rerun()
