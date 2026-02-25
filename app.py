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

# Preset scenarios for quick testing
_PRESETS = {
    "Custom (type your own)": {
        "subject": "",
        "body": "",
        "broker_email": "broker@example.com",
        "broker_name": "John Smith",
    },
    "Restaurant - QUOTED ($2,800)": {
        "subject": "Application for Acme Restaurant Inc.",
        "body": (
            "We are submitting an application for general liability coverage for Acme Restaurant Inc., "
            "a full-service restaurant located at 123 Main St, Springfield, IL. "
            "The business has been operating since 2015 with 12 employees and $500,000 annual revenue."
        ),
        "broker_email": "broker@example.com",
        "broker_name": "John Smith",
    },
    "Tech Startup - QUOTED ($306)": {
        "subject": "Application for TechStart LLC",
        "body": (
            "We need general liability coverage for TechStart LLC, a software company "
            "at 456 Oak Ave, Boston, MA 02101. Founded in 2024 with 2 employees and $50,000 annual revenue."
        ),
        "broker_email": "jane@techbroker.com",
        "broker_name": "Jane Lee",
    },
    "New Bakery - DECLINED (< 2 yrs)": {
        "subject": "Insurance request for Fresh Bakery Corp",
        "body": (
            "New bakery started in 2025 with 3 employees, revenue $80,000, "
            "located at 789 Pine Rd, Miami, FL 33101."
        ),
        "broker_email": "bob@insurancebrokers.com",
        "broker_name": "Bob Martinez",
    },
    "Incomplete Info - MISSING_INFO": {
        "subject": "Help",
        "body": "Need insurance for my business.",
        "broker_email": "info@broker.com",
        "broker_name": "Sarah",
    },
    "Large Manufacturer - QUOTED ($27,500)": {
        "subject": "Application for Midwest Manufacturing Corp.",
        "body": (
            "Requesting general liability coverage for Midwest Manufacturing Corp., "
            "a manufacturing plant at 2200 Industrial Blvd, Detroit, MI 48201. "
            "Established in 1998 with 120 employees and $2,500,000 annual revenue. "
            "Debt-to-equity ratio is 2.1."
        ),
        "broker_email": "mike@commercialbrokers.com",
        "broker_name": "Mike Chen",
    },
    "Medical Clinic - QUOTED ($1,725)": {
        "subject": "Application for Springfield Health Clinic LLC",
        "body": (
            "Submitting an application for general liability coverage for Springfield Health Clinic LLC, "
            "a health clinic at 500 Wellness Dr, Springfield, MO 65801. "
            "Operating since 2018 with 15 employees and $300,000 annual revenue."
        ),
        "broker_email": "lisa@healthinsurance.com",
        "broker_name": "Lisa Park",
    },
}

preset_choice = st.sidebar.selectbox("Scenario Preset", list(_PRESETS.keys()), index=1)
preset = _PRESETS[preset_choice]

with st.sidebar.form("submission_form"):
    email_subject = st.text_input("Email Subject", value=preset["subject"])
    email_body = st.text_area(
        "Email Body",
        value=preset["body"],
        height=150,
    )
    broker_email = st.text_input("Broker Email", value=preset["broker_email"])
    broker_name = st.text_input("Broker Name", value=preset["broker_name"])
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
    """Build an enhanced Graphviz Digraph of the underwriting workflow with dynamic highlighting."""

    # ── Agent colour palette ────────────────────────────────────
    # Each agent gets a distinct base colour used for its nodes
    AGENT_COLORS = {
        "classification":  {"fill": "#E8F0FE", "border": "#4285F4", "font": "#1A3B6B"},  # blue
        "data_retrieval":  {"fill": "#E6F4EA", "border": "#34A853", "font": "#1B5E20"},  # green
        "analyst":         {"fill": "#FEF7E0", "border": "#F9AB00", "font": "#7A5800"},  # amber
        "broker_liaison":  {"fill": "#FCE8E6", "border": "#EA4335", "font": "#8B1A1A"},  # red
        "supervisor":      {"fill": "#F3E8FD", "border": "#A142F4", "font": "#4A148C"},  # purple
        "human":           {"fill": "#F3E8FD", "border": "#A142F4", "font": "#4A148C"},  # purple (same)
    }
    DECISION_FILL   = "#FFF8E1"   # pale amber for diamond decision nodes
    DECISION_BORDER = "#FFB300"
    ACTIVE_FILL     = "#FF6D00"   # vivid orange for current step
    ACTIVE_BORDER   = "#BF360C"
    COMPLETED_FILL  = "#C8E6C9"   # soft green for completed
    COMPLETED_BORDER= "#388E3C"
    TERMINAL_FILL   = "#1B1F3B"   # dark navy for START / END
    EDGE_DEFAULT    = "#90A4AE"   # muted grey for normal edges
    EDGE_PASS       = "#2E7D32"   # green
    EDGE_FAIL       = "#C62828"   # red
    EDGE_MODIFY     = "#E65100"   # deep orange

    # ── Determine active / completed nodes ──────────────────────
    if current_status == "COMPLETED":
        active_node = _COMPLETED_NODE.get(current_decision)
    else:
        active_node = _STATUS_TO_NODE.get(current_status)

    completed_nodes: set = set()
    if active_node and active_node in _NODE_ORDER:
        idx = _NODE_ORDER.index(active_node)
        completed_nodes = set(_NODE_ORDER[:idx])
    elif active_node == "draft_missing_info":
        completed_nodes = {"ingest_and_classify", "check_data_completeness"}
    elif active_node == "draft_decline":
        completed_nodes = {"ingest_and_classify", "check_data_completeness", "enrichment", "check_knockout_rules"}

    # If the workflow finished, mark the final node as completed too
    if current_status == "COMPLETED" and active_node:
        completed_nodes.add(active_node)

    def _node_style(node_id: str, agent_key: str) -> dict:
        ac = AGENT_COLORS[agent_key]
        if node_id == active_node and current_status != "COMPLETED":
            return {
                "fillcolor": ACTIVE_FILL,
                "color": ACTIVE_BORDER,
                "fontcolor": "white",
                "penwidth": "3",
                "style": "filled,bold,rounded",
            }
        if node_id in completed_nodes:
            return {
                "fillcolor": COMPLETED_FILL,
                "color": COMPLETED_BORDER,
                "fontcolor": "#1B5E20",
                "penwidth": "2",
                "style": "filled,rounded",
            }
        return {
            "fillcolor": ac["fill"],
            "color": ac["border"],
            "fontcolor": ac["font"],
            "penwidth": "1.5",
            "style": "filled,rounded",
        }

    def _decision_style() -> dict:
        return {
            "shape": "diamond",
            "fillcolor": DECISION_FILL,
            "color": DECISION_BORDER,
            "fontcolor": "#5D4037",
            "style": "filled",
            "width": "1.6",
            "height": "1.0",
            "penwidth": "1.5",
        }

    # ── Build the graph ─────────────────────────────────────────
    g = graphviz.Digraph("workflow", format="svg")
    g.attr(
        rankdir="TB",
        bgcolor="white",
        fontname="Helvetica Neue, Helvetica, Arial, sans-serif",
        nodesep="0.7",
        ranksep="1.0",
        pad="0.5",
        margin="0.3",
        splines="ortho",
    )
    g.attr(
        "node",
        shape="box",
        style="filled,rounded",
        fillcolor="white",
        fontname="Helvetica Neue, Helvetica, Arial, sans-serif",
        fontsize="11",
        margin="0.2,0.15",
    )
    g.attr(
        "edge",
        fontname="Helvetica Neue, Helvetica, Arial, sans-serif",
        fontsize="9",
        color=EDGE_DEFAULT,
        arrowsize="0.8",
        penwidth="1.5",
    )

    # START / END terminals
    g.node(
        "START", "▶  START",
        shape="box", style="filled,rounded", width="1.2", height="0.4",
        fillcolor=TERMINAL_FILL, fontcolor="white", color=TERMINAL_FILL,
        fontsize="12", fontname="Helvetica Neue Bold",
    )
    g.node(
        "END", "◼  END",
        shape="box", style="filled,rounded", width="1.2", height="0.4",
        fillcolor=TERMINAL_FILL, fontcolor="white", color=TERMINAL_FILL,
        fontsize="12", fontname="Helvetica Neue Bold",
    )

    # ── Phase 1: Ingestion & Triage ────────────────────────────
    with g.subgraph(name="cluster_phase1") as p1:
        p1.attr(
            label="  PHASE 1  ·  Ingestion & Triage  ",
            labeljust="l",
            style="filled,rounded",
            color="#4285F4",
            fillcolor="#F8FAFF",
            fontcolor="#4285F4",
            fontsize="13",
            fontname="Helvetica Neue Bold",
            penwidth="2",
            margin="18",
        )
        p1.node(
            "ingest_and_classify",
            "📄  Ingest & Classify\nClassification Agent",
            **_node_style("ingest_and_classify", "classification"),
        )
        p1.node(
            "check_data_completeness",
            "🔍  Check Data Completeness\nUnderwriting Analyst",
            **_node_style("check_data_completeness", "analyst"),
        )
        p1.node("is_data_complete", "Data\nComplete?", **_decision_style())
        p1.node(
            "draft_missing_info",
            "✉️  Draft Missing Info Email\nBroker Liaison",
            **_node_style("draft_missing_info", "broker_liaison"),
        )

    # ── Phase 2: Qualification ──────────────────────────────────
    with g.subgraph(name="cluster_phase2") as p2:
        p2.attr(
            label="  PHASE 2  ·  Qualification & Enrichment  ",
            labeljust="l",
            style="filled,rounded",
            color="#34A853",
            fillcolor="#F6FFF8",
            fontcolor="#34A853",
            fontsize="13",
            fontname="Helvetica Neue Bold",
            penwidth="2",
            margin="18",
        )
        p2.node(
            "enrichment",
            "🔗  Enrichment  (3 sources)\nData Retrieval Agent",
            **_node_style("enrichment", "data_retrieval"),
        )
        p2.node(
            "check_knockout_rules",
            "⚖️  Check Knockout Rules\nUnderwriting Analyst",
            **_node_style("check_knockout_rules", "analyst"),
        )
        p2.node("knockout_check", "Knockout\nRules?", **_decision_style())
        p2.node(
            "risk_assessment",
            "📊  Risk Assessment & Pricing\nUnderwriting Analyst",
            **_node_style("risk_assessment", "analyst"),
        )

    # ── Phase 3: The Workbench ──────────────────────────────────
    with g.subgraph(name="cluster_phase3") as p3:
        p3.attr(
            label="  PHASE 3  ·  The Workbench  (Human-in-the-Loop)  ",
            labeljust="l",
            style="filled,rounded",
            color="#A142F4",
            fillcolor="#FBF6FF",
            fontcolor="#A142F4",
            fontsize="13",
            fontname="Helvetica Neue Bold",
            penwidth="2",
            margin="18",
        )
        p3.node(
            "human_checkpoint",
            "🧑‍💼  Human Checkpoint\nSupervisor Agent",
            **_node_style("human_checkpoint", "supervisor"),
        )
        p3.node("human_decision", "Human\nDecision?", **_decision_style())
        p3.node(
            "generate_quote",
            "✅  Generate Quote Package\nBroker Liaison",
            **_node_style("generate_quote", "broker_liaison"),
        )
        p3.node(
            "draft_decline",
            "❌  Draft Decline Letter\nBroker Liaison",
            **_node_style("draft_decline", "broker_liaison"),
        )
        p3.node(
            "update_state",
            "🔄  Update State\nHuman Override",
            **_node_style("update_state", "human"),
        )

    # ── Edges ───────────────────────────────────────────────────
    _edge = g.edge  # shorthand

    # Phase 1 flow
    _edge("START", "ingest_and_classify", color="#4285F4", penwidth="2")
    _edge("ingest_and_classify", "check_data_completeness", color=EDGE_DEFAULT)
    _edge("check_data_completeness", "is_data_complete", color=EDGE_DEFAULT)
    _edge("is_data_complete", "draft_missing_info",
          label="  missing docs  ", color=EDGE_FAIL, fontcolor=EDGE_FAIL, penwidth="2", style="dashed")
    _edge("is_data_complete", "enrichment",
          label="  complete  ", color=EDGE_PASS, fontcolor=EDGE_PASS, penwidth="2")
    _edge("draft_missing_info", "END", color=EDGE_FAIL, style="dashed")

    # Phase 2 flow
    _edge("enrichment", "check_knockout_rules", color=EDGE_DEFAULT)
    _edge("check_knockout_rules", "knockout_check", color=EDGE_DEFAULT)
    _edge("knockout_check", "draft_decline",
          label="  fail  ", color=EDGE_FAIL, fontcolor=EDGE_FAIL, penwidth="2", style="dashed")
    _edge("knockout_check", "risk_assessment",
          label="  pass  ", color=EDGE_PASS, fontcolor=EDGE_PASS, penwidth="2")

    # Phase 2 → Phase 3
    _edge("risk_assessment", "human_checkpoint", color="#A142F4", penwidth="2")

    # Phase 3 flow
    _edge("human_checkpoint", "human_decision", color=EDGE_DEFAULT)
    _edge("human_decision", "generate_quote",
          label="  approve  ", color=EDGE_PASS, fontcolor=EDGE_PASS, penwidth="2")
    _edge("human_decision", "draft_decline",
          label="  decline  ", color=EDGE_FAIL, fontcolor=EDGE_FAIL, penwidth="2", style="dashed")
    _edge("human_decision", "update_state",
          label="  modify  ", color=EDGE_MODIFY, fontcolor=EDGE_MODIFY, penwidth="2")
    _edge("update_state", "risk_assessment",
          label="  loop back  ", color=EDGE_MODIFY, fontcolor=EDGE_MODIFY,
          style="dashed", penwidth="2", constraint="false")

    # Terminals
    _edge("generate_quote", "END", color=EDGE_PASS, penwidth="2")
    _edge("draft_decline", "END", color=EDGE_FAIL, style="dashed")

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

    # Enhanced legend
    st.markdown("---")
    st.caption("LEGEND")
    leg1, leg2 = st.columns(2)

    with leg1:
        st.markdown(
            """
            **Node Status**
            - 🟧 **Orange** — Current active step
            - 🟩 **Green** — Completed
            - ⬜ **Colored border** — Pending (color = agent)
            - 🔶 **Diamond** — Conditional decision point
            """
        )

    with leg2:
        st.markdown(
            """
            **Agent Colors**
            - 🔵 **Blue** — Classification Agent
            - 🟢 **Green** — Data Retrieval Agent
            - 🟡 **Amber** — Underwriting Analyst Agent
            - 🔴 **Red** — Broker Liaison Agent
            - 🟣 **Purple** — Supervisor / Human Override
            """
        )

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
