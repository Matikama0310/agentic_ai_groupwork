"""
LangGraph StateGraph Workflow for NorthStar Underwriting.

Implements the 3-phase workflow from the architecture diagram:
  Phase 1: Ingestion & Triage  (Ingest → Extract → Is Data Complete?)
  Phase 2: Qualification        (Knockout Rules → Enrichment → Risk Assessment)
  Phase 3: The Workbench        (Human-in-the-loop checkpoint → Approve/Modify/Decline)

Agents mapped:
  - Supervisor Agent:            Orchestrates the full graph
  - Classification Agent:        Ingest & Classify node
  - Data Retrieval Agent:        Enrichment node (internal, external, web - parallel)
  - Underwriting Analyst Agent:  Data Completeness + Knockout Rules + Risk Assessment nodes
  - Broker Liaison Agent:        Missing Info / Decline / Quote output nodes
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.tools.data_acquisition import (
    fetch_external_data,
    internal_claims_history,
    web_research_applicant,
)
from src.tools.decision_logic import (
    calculate_risk_and_price,
    classify_naics_code,
    validate_against_guidelines,
)
from src.tools.document_understanding import extract_structured_data
from src.tools.communication import (
    draft_decline_letter,
    draft_missing_info_email,
    draft_quote_email,
    generate_quote_pdf,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph State  (TypedDict consumed by LangGraph)
# ---------------------------------------------------------------------------
class UnderwritingState(TypedDict, total=False):
    # Input
    submission_id: str
    email_subject: str
    email_body: str
    broker_email: str
    broker_name: str
    attachments: List[Dict[str, Any]]

    # Phase 1: Ingestion & Triage
    extracted_data: Optional[Dict[str, Any]]
    extraction_confidence: Optional[float]
    document_types: Optional[List[str]]
    naics_code: Optional[str]
    classification_confidence: Optional[float]

    # Phase 2: Qualification
    internal_data: Optional[Dict[str, Any]]
    external_data: Optional[Dict[str, Any]]
    web_data: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    risk_metrics: Optional[Dict[str, Any]]

    # Phase 3: Output
    decision: str
    drafted_email: Optional[Dict[str, Any]]
    quote_pdf_url: Optional[str]
    human_override: Optional[Dict[str, Any]]

    # Metadata
    status: str
    errors: List[Dict[str, Any]]
    audit_trail: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helper: add audit entry
# ---------------------------------------------------------------------------
def _audit(state: dict, component: str, action: str, result: str = "") -> dict:
    trail = list(state.get("audit_trail", []))
    trail.append({
        "timestamp": datetime.utcnow().isoformat(),
        "component": component,
        "action": action,
        "result": result,
    })
    return trail


# ===================================================================
# NODE FUNCTIONS  (each returns a partial state update dict)
# ===================================================================

def ingest_and_classify(state: dict) -> dict:
    """
    Phase 1 - Node: Ingest & Classify
    Splits email vs. attachments, extracts structured data, classifies NAICS.
    Agent: Classification Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: ingest_and_classify")

    document_content = f"{state.get('email_subject', '')}\n{state.get('email_body', '')}"
    for att in state.get("attachments", []):
        document_content += f"\n{att.get('content', '')}"

    result = extract_structured_data(document_content)

    updates: dict = {
        "status": "EXTRACTION",
        "errors": list(state.get("errors", [])),
    }

    if result.success:
        updates["extracted_data"] = result.data.get("extracted_fields")
        updates["extraction_confidence"] = result.data.get("extraction_confidence")
        updates["document_types"] = result.data.get("document_types", [])

        # Classify business
        business_desc = updates["extracted_data"].get("business_type", "")
        business_name = updates["extracted_data"].get("applicant_name", "")
        naics = classify_naics_code(business_desc, business_name)
        if naics.success:
            updates["naics_code"] = naics.data.get("naics_code")
            updates["classification_confidence"] = naics.data.get("confidence")
    else:
        updates["errors"] = updates["errors"] + [{"phase": "extraction", "error": result.error}]

    updates["audit_trail"] = _audit(state, "ClassificationAgent", "ingest_and_classify",
                                     f"confidence={updates.get('extraction_confidence')}")
    return updates


def check_data_completeness(state: dict) -> dict:
    """
    Phase 1 - Node: Extraction (data completeness check).
    Validates that critical documents are present.
    Agent: Underwriting Analyst Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: check_data_completeness")

    extracted = state.get("extracted_data") or {}
    result = validate_against_guidelines(extracted)

    missing = result.data.get("missing_critical_docs", []) if result.success else []

    updates: dict = {
        "validation_result": result.data if result.success else {},
        "audit_trail": _audit(state, "UnderwritingAnalystAgent", "check_data_completeness",
                               f"missing={missing}"),
    }

    if missing:
        updates["decision"] = "MISSING_INFO"

    return updates


def draft_missing_info(state: dict) -> dict:
    """
    Phase 1 - Node: Draft 'Missing Info' Email.
    Agent: Broker Liaison Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: draft_missing_info")
    extracted = state.get("extracted_data") or {}
    missing = state.get("validation_result", {}).get("missing_critical_docs", [])

    result = draft_missing_info_email(
        state.get("broker_email", ""),
        state.get("broker_name", ""),
        extracted.get("applicant_name", "Unknown"),
        missing,
    )

    return {
        "drafted_email": result.data if result.success else None,
        "status": "COMPLETED",
        "decision": "MISSING_INFO",
        "audit_trail": _audit(state, "BrokerLiaisonAgent", "draft_missing_info_email",
                               f"missing_docs={len(missing)}"),
    }


def check_knockout_rules(state: dict) -> dict:
    """
    Phase 2 - Conditional: Hard Knock-out Rules?
    Agent: Underwriting Analyst Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: check_knockout_rules")

    extracted = state.get("extracted_data") or {}
    external = state.get("external_data") or {}
    internal = state.get("internal_data") or {}

    result = validate_against_guidelines(extracted, external, state.get("web_data"), internal)

    updates: dict = {
        "validation_result": result.data if result.success else {},
        "audit_trail": _audit(state, "UnderwritingAnalystAgent", "check_knockout_rules",
                               f"passes={result.data.get('passes_guidelines') if result.success else 'error'}"),
    }

    if result.success and not result.data.get("passes_guidelines"):
        updates["decision"] = "DECLINED"

    return updates


def enrichment(state: dict) -> dict:
    """
    Phase 2 - Node: Enrichment (calls D&B / HazardHub APIs).
    Agent: Data Retrieval Agent (Internal, External Bureau, Open Source) - parallel.
    """
    logger.info(f"[{state['submission_id']}] NODE: enrichment (parallel data retrieval)")

    extracted = state.get("extracted_data") or {}
    applicant_id = extracted.get("applicant_id", state["submission_id"])
    applicant_name = extracted.get("applicant_name", "Unknown")
    applicant_address = extracted.get("address", "")
    applicant_website = extracted.get("website", "")

    # In production these run via asyncio.gather() for true parallelism
    internal = internal_claims_history(applicant_id, applicant_name)
    external = fetch_external_data(applicant_name, applicant_address)
    web = web_research_applicant(applicant_name, applicant_website)

    trail = _audit(state, "DataRetrievalAgent", "enrichment_parallel",
                    f"internal={internal.success}, external={external.success}, web={web.success}")

    return {
        "status": "ENRICHMENT",
        "internal_data": internal.data if internal.success else {},
        "external_data": external.data if external.success else {},
        "web_data": web.data if web.success else {},
        "audit_trail": trail,
    }


def risk_assessment(state: dict) -> dict:
    """
    Phase 2 - Node: Risk Assessment (RAG Search + Pricing Calc).
    Agent: Underwriting Analyst Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: risk_assessment")

    result = calculate_risk_and_price(
        state.get("extracted_data") or {},
        state.get("external_data"),
        state.get("internal_data"),
    )

    updates: dict = {
        "status": "ANALYSIS",
        "risk_metrics": result.data if result.success else {},
        "audit_trail": _audit(state, "UnderwritingAnalystAgent", "risk_assessment",
                               f"premium=${result.data.get('annual_premium', 0):.2f}" if result.success else "error"),
    }

    if result.success:
        updates["decision"] = "QUOTED"
    else:
        updates["decision"] = "MANUAL_REVIEW"

    return updates


def human_checkpoint(state: dict) -> dict:
    """
    Phase 3 - INTERRUPT / CHECKPOINT.
    Persists state and waits for human decision via Streamlit UI.
    In the graph this is a passthrough; the Streamlit app reads/writes state.
    """
    logger.info(f"[{state['submission_id']}] NODE: human_checkpoint (awaiting human decision)")

    return {
        "status": "DECISION",
        "audit_trail": _audit(state, "SupervisorAgent", "human_checkpoint",
                               f"decision={state.get('decision')} awaiting human review"),
    }


def draft_decline(state: dict) -> dict:
    """
    Phase 3 - Node: Draft Decline Letter.
    Agent: Broker Liaison Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: draft_decline")
    extracted = state.get("extracted_data") or {}
    failed = state.get("validation_result", {}).get("failed_rules", [])

    result = draft_decline_letter(
        state.get("broker_email", ""),
        state.get("broker_name", ""),
        extracted.get("applicant_name", "Unknown"),
        failed,
    )

    return {
        "drafted_email": result.data if result.success else None,
        "status": "COMPLETED",
        "decision": "DECLINED",
        "audit_trail": _audit(state, "BrokerLiaisonAgent", "draft_decline_letter",
                               f"failed_rules={len(failed)}"),
    }


def generate_quote(state: dict) -> dict:
    """
    Phase 3 - Node: Generate Quote Package (PDF + email).
    Agent: Broker Liaison Agent
    """
    logger.info(f"[{state['submission_id']}] NODE: generate_quote")
    extracted = state.get("extracted_data") or {}
    risk = state.get("risk_metrics") or {}
    premium = risk.get("annual_premium", 0)
    applicant_name = extracted.get("applicant_name", "Unknown")

    pdf = generate_quote_pdf(extracted, risk, premium, applicant_name)
    pdf_url = pdf.data.get("quote_pdf_s3_url", "") if pdf.success else ""

    email = draft_quote_email(
        state.get("broker_email", ""),
        state.get("broker_name", ""),
        applicant_name,
        premium,
        "1 year",
        pdf_url,
    )

    return {
        "quote_pdf_url": pdf_url,
        "drafted_email": email.data if email.success else None,
        "status": "COMPLETED",
        "decision": "QUOTED",
        "audit_trail": _audit(state, "BrokerLiaisonAgent", "generate_quote_package",
                               f"premium=${premium:.2f}"),
    }


def update_state_node(state: dict) -> dict:
    """
    Phase 3 - Node: Update State (Human overrides AI data).
    When human selects 'Refer / Modify' this loops back to risk_assessment.
    """
    logger.info(f"[{state['submission_id']}] NODE: update_state (human modification)")

    override = state.get("human_override") or {}
    return {
        "decision": override.get("new_decision", state.get("decision", "MANUAL_REVIEW")),
        "audit_trail": _audit(state, "Human", "update_state",
                               f"override applied: {override.get('reason', 'no reason')}"),
    }


# ===================================================================
# CONDITIONAL EDGE FUNCTIONS
# ===================================================================

def is_data_complete(state: dict) -> str:
    """Conditional Edge: Is Data Complete?"""
    validation = state.get("validation_result", {})
    missing = validation.get("missing_critical_docs", [])
    if missing or state.get("decision") == "MISSING_INFO":
        return "missing_docs"
    return "data_complete"


def knockout_check(state: dict) -> str:
    """Conditional Edge: Hard Knock-out Rules?"""
    if state.get("decision") == "DECLINED":
        return "fail"
    return "pass"


def human_decision(state: dict) -> str:
    """
    Conditional Edge: Human Decision (Via Streamlit).
    Reads the decision field which may have been modified by the UI.
    """
    decision = state.get("decision", "MANUAL_REVIEW")
    override = state.get("human_override", {})

    if override:
        decision = override.get("new_decision", decision)

    if decision == "DECLINED":
        return "decline"
    elif decision == "QUOTED":
        return "approve"
    else:
        return "modify"


# ===================================================================
# BUILD THE GRAPH
# ===================================================================

def build_underwriting_graph() -> StateGraph:
    """
    Build the LangGraph StateGraph matching the workflow diagram.

    Flow:
      START
        → ingest_and_classify
        → check_data_completeness
        → [Conditional: is_data_complete]
            ├─ missing_docs → draft_missing_info → END
            └─ data_complete → enrichment
                → check_knockout_rules
                → [Conditional: knockout_check]
                    ├─ fail → draft_decline → END
                    └─ pass → risk_assessment
                        → human_checkpoint
                        → [Conditional: human_decision]
                            ├─ approve → generate_quote → END
                            ├─ decline → draft_decline → END
                            └─ modify  → update_state → risk_assessment (loop)
    """
    graph = StateGraph(UnderwritingState)

    # --- Add nodes ---
    graph.add_node("ingest_and_classify", ingest_and_classify)
    graph.add_node("check_data_completeness", check_data_completeness)
    graph.add_node("draft_missing_info", draft_missing_info)
    graph.add_node("enrichment", enrichment)
    graph.add_node("check_knockout_rules", check_knockout_rules)
    graph.add_node("draft_decline", draft_decline)
    graph.add_node("risk_assessment", risk_assessment)
    graph.add_node("human_checkpoint", human_checkpoint)
    graph.add_node("generate_quote", generate_quote)
    graph.add_node("update_state", update_state_node)

    # --- Set entry point ---
    graph.set_entry_point("ingest_and_classify")

    # --- Edges ---
    # Phase 1: Ingestion & Triage
    graph.add_edge("ingest_and_classify", "check_data_completeness")
    graph.add_conditional_edges(
        "check_data_completeness",
        is_data_complete,
        {"missing_docs": "draft_missing_info", "data_complete": "enrichment"},
    )
    graph.add_edge("draft_missing_info", END)

    # Phase 2: Qualification
    graph.add_edge("enrichment", "check_knockout_rules")
    graph.add_conditional_edges(
        "check_knockout_rules",
        knockout_check,
        {"fail": "draft_decline", "pass": "risk_assessment"},
    )

    # Phase 3: The Workbench
    graph.add_edge("risk_assessment", "human_checkpoint")
    graph.add_conditional_edges(
        "human_checkpoint",
        human_decision,
        {"approve": "generate_quote", "decline": "draft_decline", "modify": "update_state"},
    )
    graph.add_edge("generate_quote", END)
    graph.add_edge("draft_decline", END)
    graph.add_edge("update_state", "risk_assessment")  # Loop back

    return graph


def compile_workflow():
    """Compile the graph into a runnable workflow."""
    graph = build_underwriting_graph()
    return graph.compile()
