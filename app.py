"""
Streamlit Underwriting Workbench - Human-in-the-Loop UI.
Maps to Phase 3 "The Workbench" in the architecture diagram.

Run: streamlit run app.py
"""

import json
import graphviz
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
# Workflow diagram builder
# ---------------------------------------------------------------------------
# Ordered list of nodes a submission passes through on the "happy path"
_NODE_ORDER = [
    "ingest_and_classify",
    "check_data_completeness",
    "enrichment",
    "check_knockout_rules",
    "risk_assessment",
    "human_checkpoint",
    "generate_quote",
]

# Map (status, decision) → currently-active node id
_STATUS_TO_NODE = {
    "INGESTION": "ingest_and_classify",
    "EXTRACTION": "check_data_completeness",
    "ENRICHMENT": "enrichment",
    "ANALYSIS": "risk_assessment",
    "DECISION": "human_checkpoint",
}

_COMPLETED_NODE = {
    "MISSING_INFO": "draft_missing_info",
    "DECLINED": "draft_decline",
    "QUOTED": "generate_quote",
}


def render_workflow_diagram(current_status: str = "", current_decision: str = "") -> graphviz.Digraph:
    """Build a Graphviz Digraph of the underwriting workflow with dynamic highlighting."""

    # Determine active node
    if current_status == "COMPLETED":
        active_node = _COMPLETED_NODE.get(current_decision)
    else:
        active_node = _STATUS_TO_NODE.get(current_status)

    # Determine completed nodes (all nodes before the active one on the happy path)
    completed_nodes: set = set()
    if active_node and active_node in _NODE_ORDER:
        idx = _NODE_ORDER.index(active_node)
        completed_nodes = set(_NODE_ORDER[:idx])
    elif active_node == "draft_missing_info":
        completed_nodes = {"ingest_and_classify", "check_data_completeness"}
    elif active_node == "draft_decline":
        completed_nodes = {"ingest_and_classify", "check_data_completeness", "enrichment", "check_knockout_rules"}

    def _style(node_id: str) -> dict:
        if node_id == active_node:
            return {"fillcolor": "#FF8C00", "fontcolor": "white", "penwidth": "3", "style": "filled,bold"}
        if node_id in completed_nodes:
            return {"fillcolor": "#90EE90", "style": "filled"}
        return {"fillcolor": "white", "style": "filled"}

    g = graphviz.Digraph("workflow", format="svg")
    g.attr(rankdir="TB", bgcolor="transparent", fontname="Helvetica", nodesep="0.6", ranksep="0.8")
    g.attr("node", shape="box", style="filled,rounded", fillcolor="white", fontname="Helvetica", fontsize="11")
    g.attr("edge", fontname="Helvetica", fontsize="9")

    # START / END
    g.node("START", "START", shape="circle", width="0.5", fillcolor="#4A90D9", fontcolor="white", style="filled")
    g.node("END", "END", shape="doublecircle", width="0.5", fillcolor="#4A90D9", fontcolor="white", style="filled")

    # --- Phase 1: Ingestion & Triage ---
    with g.subgraph(name="cluster_phase1") as p1:
        p1.attr(label="Phase 1: Ingestion & Triage", style="dashed", color="#4A90D9", fontcolor="#4A90D9")
        p1.node("ingest_and_classify", "Ingest & Classify\n(Classification Agent)", **_style("ingest_and_classify"))
        p1.node("check_data_completeness", "Check Data\nCompleteness\n(Underwriting Analyst)", **_style("check_data_completeness"))
        p1.node("is_data_complete", "Data\nComplete?", shape="diamond", fillcolor="#FFF3CD", style="filled", width="1.4", height="0.9")
        p1.node("draft_missing_info", "Draft Missing\nInfo Email\n(Broker Liaison)", **_style("draft_missing_info"))

    # --- Phase 2: Qualification ---
    with g.subgraph(name="cluster_phase2") as p2:
        p2.attr(label="Phase 2: Qualification", style="dashed", color="#28A745", fontcolor="#28A745")
        p2.node("enrichment", "Enrichment\n(Data Retrieval Agent)", **_style("enrichment"))
        p2.node("check_knockout_rules", "Check Knockout\nRules\n(Underwriting Analyst)", **_style("check_knockout_rules"))
        p2.node("knockout_check", "Knockout\nRules?", shape="diamond", fillcolor="#FFF3CD", style="filled", width="1.4", height="0.9")
        p2.node("risk_assessment", "Risk Assessment\n(Underwriting Analyst)", **_style("risk_assessment"))

    # --- Phase 3: The Workbench ---
    with g.subgraph(name="cluster_phase3") as p3:
        p3.attr(label="Phase 3: The Workbench (Human-in-the-Loop)", style="dashed", color="#DC3545", fontcolor="#DC3545")
        p3.node("human_checkpoint", "Human\nCheckpoint", **_style("human_checkpoint"))
        p3.node("human_decision", "Human\nDecision?", shape="diamond", fillcolor="#FFF3CD", style="filled", width="1.4", height="0.9")
        p3.node("generate_quote", "Generate Quote\n(Broker Liaison)", **_style("generate_quote"))
        p3.node("draft_decline", "Draft Decline\n(Broker Liaison)", **_style("draft_decline"))
        p3.node("update_state", "Update State\n(Human Override)", **_style("update_state"))

    # --- Edges ---
    g.edge("START", "ingest_and_classify")
    g.edge("ingest_and_classify", "check_data_completeness")
    g.edge("check_data_completeness", "is_data_complete")
    g.edge("is_data_complete", "draft_missing_info", label="missing_docs", color="#DC3545", fontcolor="#DC3545")
    g.edge("is_data_complete", "enrichment", label="data_complete", color="#28A745", fontcolor="#28A745")
    g.edge("draft_missing_info", "END")
    g.edge("enrichment", "check_knockout_rules")
    g.edge("check_knockout_rules", "knockout_check")
    g.edge("knockout_check", "draft_decline", label="fail", color="#DC3545", fontcolor="#DC3545")
    g.edge("knockout_check", "risk_assessment", label="pass", color="#28A745", fontcolor="#28A745")
    g.edge("risk_assessment", "human_checkpoint")
    g.edge("human_checkpoint", "human_decision")
    g.edge("human_decision", "generate_quote", label="approve", color="#28A745", fontcolor="#28A745")
    g.edge("human_decision", "draft_decline", label="decline", color="#DC3545", fontcolor="#DC3545")
    g.edge("human_decision", "update_state", label="modify", color="#FF8C00", fontcolor="#FF8C00")
    g.edge("update_state", "risk_assessment", style="dashed", label="loop back", color="#FF8C00", fontcolor="#FF8C00")
    g.edge("generate_quote", "END")
    g.edge("draft_decline", "END")

    return g


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
tab_overview, tab_workflow, tab_data, tab_risk, tab_email, tab_audit, tab_override = st.tabs(
    ["Overview", "Workflow", "Extracted Data", "Risk Assessment", "Drafted Email", "Audit Trail", "Human Override"]
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

# --- Tab 2: Workflow Diagram ---
with tab_workflow:
    st.subheader("Agent Workflow Diagram")
    diagram = render_workflow_diagram(state.status, state.decision)
    st.graphviz_chart(diagram, use_container_width=True)

    # Legend
    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.markdown(":orange_square: **Current Step**")
    lc2.markdown(":green_square: **Completed**")
    lc3.markdown(":white_large_square: **Pending**")
    lc4.markdown(":yellow_square: **Decision Point**")

# --- Tab 3: Extracted Data ---
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
