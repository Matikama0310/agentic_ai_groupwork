"""
Comprehensive test suite for NorthStar Underwriting System.
Tests: Tools, State Manager, LangGraph Workflow, End-to-End.
"""

import pytest
from datetime import datetime

# Tool imports
from src.tools.decision_logic import (
    ToolResult,
    classify_naics_code,
    validate_against_guidelines,
    calculate_risk_and_price,
)
from src.tools.document_understanding import extract_structured_data, analyze_image_hazards
from src.tools.data_acquisition import internal_claims_history, fetch_external_data, web_research_applicant
from src.tools.communication import draft_missing_info_email, draft_decline_letter, draft_quote_email, generate_quote_pdf

# State manager
from src.core.state_manager import StateManager, SubmissionStatus, DecisionType

# Workflow
from src.orchestration.workflow import (
    build_underwriting_graph,
    compile_workflow,
    ingest_and_classify,
    check_data_completeness,
    enrichment,
    risk_assessment,
    is_data_complete,
    knockout_check,
    human_decision,
)


# ===========================================================================
# Document Understanding Tools
# ===========================================================================
class TestDocumentTools:
    def test_extract_structured_data_success(self):
        result = extract_structured_data("Restaurant application form with detailed info for evaluation")
        assert result.success
        assert "extracted_fields" in result.data
        assert result.data["extraction_confidence"] > 0

    def test_extract_structured_data_low_confidence(self):
        result = extract_structured_data("x")
        assert result.success
        assert result.data["extraction_confidence"] <= 0.5

    def test_analyze_image_hazards_with_image(self):
        result = analyze_image_hazards("a" * 200)
        assert result.success
        assert len(result.data["hazards_detected"]) > 0

    def test_analyze_image_hazards_empty(self):
        result = analyze_image_hazards("short")
        assert result.success
        assert len(result.data["hazards_detected"]) == 0


# ===========================================================================
# Decision Logic Tools
# ===========================================================================
class TestDecisionTools:
    def test_classify_naics_restaurant(self):
        result = classify_naics_code("Full-service restaurant with bar", "Acme Cafe")
        assert result.success
        assert result.data["naics_code"] == "722110"
        assert result.data["confidence"] > 0

    def test_classify_naics_unknown(self):
        result = classify_naics_code("xyz unknown business", "Foo Corp")
        assert result.success
        assert result.data["naics_code"] == "999999"

    def test_validate_guidelines_passes(self):
        extracted = {
            "submitted_documents": ["application_form", "financial_statements", "loss_history"],
            "debt_to_equity": 1.5,
            "years_in_business": 5,
        }
        enriched = {"credit_score": 750}
        result = validate_against_guidelines(extracted, enriched)
        assert result.success
        assert result.data["passes_guidelines"] is True
        assert len(result.data["failed_rules"]) == 0

    def test_validate_guidelines_fails_credit(self):
        extracted = {
            "submitted_documents": ["application_form", "financial_statements", "loss_history"],
            "years_in_business": 5,
            "debt_to_equity": 1.0,
        }
        enriched = {"credit_score": 300}
        result = validate_against_guidelines(extracted, enriched)
        assert result.success
        assert result.data["passes_guidelines"] is False
        assert any(r["rule_id"] == "R001" for r in result.data["failed_rules"])

    def test_validate_guidelines_missing_docs(self):
        extracted = {"submitted_documents": ["application_form"]}
        result = validate_against_guidelines(extracted)
        assert result.success
        assert result.data["passes_guidelines"] is False
        assert len(result.data["missing_critical_docs"]) > 0

    def test_calculate_risk_and_price(self):
        extracted = {"annual_revenue": 500000, "employees": 10, "debt_to_equity": 1.5}
        enriched = {"credit_score": 700, "property_risk": {"crime_score": 40}}
        result = calculate_risk_and_price(extracted, enriched)
        assert result.success
        assert result.data["annual_premium"] > 0
        assert 0 <= result.data["risk_score"] <= 100


# ===========================================================================
# Data Acquisition Tools
# ===========================================================================
class TestDataTools:
    def test_internal_claims_history(self):
        result = internal_claims_history("APP-001", "Acme Inc")
        assert result.success
        assert isinstance(result.data["loss_runs"], list)
        assert result.data["total_losses"] >= 0

    def test_fetch_external_data(self):
        result = fetch_external_data("Acme Inc", "123 Main St")
        assert result.success
        assert "credit_score" in result.data
        assert "property_risk" in result.data

    def test_web_research_applicant(self):
        result = web_research_applicant("Acme Inc", "https://acme.com")
        assert result.success
        assert "website_verified" in result.data
        assert "risk_flags" in result.data


# ===========================================================================
# Communication Tools
# ===========================================================================
class TestCommsTools:
    def test_draft_missing_info_email(self):
        result = draft_missing_info_email("broker@test.com", "John", "Acme", ["financial_statements"])
        assert result.success
        assert "subject" in result.data
        assert "Financial Statements" in result.data["body"]

    def test_draft_decline_letter(self):
        rules = [{"rule_id": "R002", "rule_description": "Loss ratio", "reason": "too high"}]
        result = draft_decline_letter("broker@test.com", "John", "Acme", rules)
        assert result.success
        assert "Decline" in result.data["subject"]

    def test_draft_quote_email(self):
        result = draft_quote_email("broker@test.com", "John", "Acme", 2500.00, "1 year", "s3://quote.pdf")
        assert result.success
        assert "2,500" in result.data["body"] or "2500" in result.data["body"]

    def test_generate_quote_pdf(self):
        result = generate_quote_pdf({"applicant_name": "Acme"}, {"risk_score": 45}, 2500, "Acme")
        assert result.success
        assert "s3://" in result.data["quote_pdf_s3_url"]


# ===========================================================================
# State Manager
# ===========================================================================
class TestStateManager:
    def setup_method(self):
        self.sm = StateManager()

    def test_create_state(self):
        state = self.sm.create_state("SUB-001", "Subj", "Body", "b@t.com", "John", [])
        assert state.submission_id == "SUB-001"
        assert state.status == SubmissionStatus.INGESTION.value

    def test_get_state(self):
        self.sm.create_state("SUB-002", "S", "B", "b@t.com", "J", [])
        assert self.sm.get_state("SUB-002") is not None
        assert self.sm.get_state("NOPE") is None

    def test_update_state(self):
        self.sm.create_state("SUB-003", "S", "B", "b@t.com", "J", [])
        self.sm.update_state("SUB-003", status=SubmissionStatus.EXTRACTION.value, extracted_data={"name": "Test"})
        state = self.sm.get_state("SUB-003")
        assert state.status == "EXTRACTION"
        assert state.extracted_data == {"name": "Test"}

    def test_audit_entry(self):
        self.sm.create_state("SUB-004", "S", "B", "b@t.com", "J", [])
        self.sm.add_audit_entry("SUB-004", "TestAgent", "test_action", {"k": "v"}, result="ok")
        state = self.sm.get_state("SUB-004")
        assert len(state.audit_trail) == 1
        assert state.audit_trail[0].action == "test_action"

    def test_apply_override(self):
        self.sm.create_state("SUB-005", "S", "B", "b@t.com", "J", [])
        self.sm.update_state("SUB-005", decision=DecisionType.QUOTED.value)
        self.sm.apply_override("SUB-005", "USER-1", DecisionType.DECLINED.value, "Bad risk")
        state = self.sm.get_state("SUB-005")
        assert state.decision == DecisionType.DECLINED.value
        assert len(state.overrides) == 1

    def test_list_submissions(self):
        for i in range(3):
            self.sm.create_state(f"SUB-{i}", "S", "B", "b@t.com", "J", [])
        assert len(self.sm.list_submissions()) == 3

    def test_submission_summary(self):
        self.sm.create_state("SUB-006", "S", "B", "b@t.com", "J", [])
        summary = self.sm.get_submission_summary("SUB-006")
        assert summary["submission_id"] == "SUB-006"
        assert "status" in summary


# ===========================================================================
# LangGraph Workflow Nodes (unit)
# ===========================================================================
class TestWorkflowNodes:
    def _base_state(self):
        return {
            "submission_id": "TEST-001",
            "email_subject": "Application for Acme Restaurant Inc.",
            "email_body": "Full-service restaurant at 123 Main St with 12 employees",
            "broker_email": "broker@test.com",
            "broker_name": "John",
            "attachments": [],
            "errors": [],
            "audit_trail": [],
        }

    def test_ingest_and_classify(self):
        result = ingest_and_classify(self._base_state())
        assert result["extracted_data"] is not None
        assert result["naics_code"] is not None
        assert result["extraction_confidence"] > 0

    def test_enrichment(self):
        state = self._base_state()
        state["extracted_data"] = {"applicant_id": "A1", "applicant_name": "Acme", "address": "123 Main", "website": ""}
        result = enrichment(state)
        assert result["internal_data"] is not None
        assert result["external_data"] is not None
        assert result["web_data"] is not None

    def test_risk_assessment(self):
        state = self._base_state()
        state["extracted_data"] = {"annual_revenue": 500000, "employees": 10, "debt_to_equity": 1.5}
        state["external_data"] = {"credit_score": 720, "property_risk": {"crime_score": 35}}
        state["internal_data"] = {"total_losses": 8000, "loss_ratio": 0.016}
        result = risk_assessment(state)
        assert result["risk_metrics"]["annual_premium"] > 0
        assert result["decision"] == "QUOTED"


# ===========================================================================
# LangGraph Conditional Edges
# ===========================================================================
class TestConditionalEdges:
    def test_is_data_complete_yes(self):
        state = {"validation_result": {"missing_critical_docs": []}}
        assert is_data_complete(state) == "data_complete"

    def test_is_data_complete_no(self):
        state = {"validation_result": {"missing_critical_docs": ["financial_statements"]}}
        assert is_data_complete(state) == "missing_docs"

    def test_knockout_pass(self):
        assert knockout_check({"decision": "QUOTED"}) == "pass"

    def test_knockout_fail(self):
        assert knockout_check({"decision": "DECLINED"}) == "fail"

    def test_human_approve(self):
        assert human_decision({"decision": "QUOTED"}) == "approve"

    def test_human_decline(self):
        assert human_decision({"decision": "DECLINED"}) == "decline"


# ===========================================================================
# End-to-End Workflow
# ===========================================================================
class TestEndToEnd:
    def test_full_workflow_quoted(self):
        """Happy path: complete submission -> QUOTED with premium."""
        workflow = compile_workflow()
        result = workflow.invoke({
            "submission_id": "E2E-001",
            "email_subject": "Application for Acme Restaurant Inc.",
            "email_body": "Full-service restaurant at 123 Main St, Springfield IL",
            "broker_email": "broker@test.com",
            "broker_name": "John Smith",
            "attachments": [],
            "decision": "UNKNOWN",
            "status": "INGESTION",
            "errors": [],
            "audit_trail": [],
        })

        assert result["decision"] == "QUOTED"
        assert result["status"] == "COMPLETED"
        assert result["risk_metrics"]["annual_premium"] > 0
        assert result["drafted_email"] is not None
        assert result["quote_pdf_url"] is not None
        assert "s3://" in result["quote_pdf_url"]

    def test_full_workflow_performance(self):
        """Workflow should complete within 10 seconds."""
        import time
        workflow = compile_workflow()
        start = time.time()
        result = workflow.invoke({
            "submission_id": "E2E-PERF",
            "email_subject": "Perf Test",
            "email_body": "Test application",
            "broker_email": "b@t.com",
            "broker_name": "Test",
            "attachments": [],
            "decision": "UNKNOWN",
            "status": "INGESTION",
            "errors": [],
            "audit_trail": [],
        })
        elapsed = time.time() - start
        assert elapsed < 10
        assert result["decision"] in ["QUOTED", "DECLINED", "MISSING_INFO"]

    def test_supervisor_agent_integration(self):
        """Test SupervisorAgent with LangGraph end-to-end."""
        from src.orchestration.supervisor_agent import SupervisorAgent

        supervisor = SupervisorAgent()
        state = supervisor.process_submission(
            submission_id="E2E-SUP-001",
            email_subject="Application for Acme Restaurant",
            email_body="Applying for general liability coverage for a restaurant.",
            broker_email="broker@test.com",
            broker_name="John",
            attachments=[],
        )

        assert state.decision == "QUOTED"
        assert state.risk_metrics is not None
        assert state.drafted_email is not None
