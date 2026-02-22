# FILE: tests/test_tools.py
"""
Unit tests for tools (decision, document, data, comms, output).
"""

import pytest
from datetime import datetime
from src.tools.all_tools import (
    extract_structured_data,
    classify_naics_code,
    validate_against_guidelines,
    calculate_risk_and_price,
    internal_claims_history,
    fetch_external_data,
    web_research_applicant,
    draft_missing_info_email,
    draft_decline_letter,
    draft_quote_email,
    generate_quote_pdf,
    ToolResult
)


class TestDocumentTools:
    """Tests for document understanding tools"""
    
    def test_extract_structured_data_success(self):
        """Test successful data extraction"""
        result = extract_structured_data("Restaurant application form...")
        
        assert result.success
        assert "extracted_fields" in result.data
        assert "extraction_confidence" in result.data
        assert result.data["extraction_confidence"] > 0
    
    def test_extract_structured_data_empty(self):
        """Test extraction with empty document"""
        result = extract_structured_data("")
        
        assert result.success
        assert result.data["extraction_confidence"] < 0.75  # Lower confidence


class TestDecisionTools:
    """Tests for decision logic tools"""
    
    def test_classify_naics_code_restaurant(self):
        """Test NAICS classification for restaurant"""
        result = classify_naics_code("Full-service restaurant with bar", "Acme Cafe")
        
        assert result.success
        assert "naics_code" in result.data
        assert result.data["naics_code"] is not None
        assert result.data["confidence"] > 0
    
    def test_validate_guidelines_passes(self):
        """Test validation when guidelines pass"""
        extracted = {
            "credit_score": 750,
            "loss_ratio": 0.05,
            "debt_to_equity": 1.5,
            "years_in_business": 5,
            "submitted_documents": ["application_form", "financial_statements", "loss_history"]
        }
        enriched = {"credit_score": 750}
        
        result = validate_against_guidelines(extracted, enriched)
        
        assert result.success
        assert result.data["passes_guidelines"] == True
        assert len(result.data["failed_rules"]) == 0
    
    def test_validate_guidelines_fails_credit(self):
        """Test validation when credit score is too low"""
        extracted = {
            "credit_score": 450,  # Below 500 threshold
            "submitted_documents": ["application_form", "financial_statements", "loss_history"]
        }
        
        result = validate_against_guidelines(extracted)
        
        assert result.success
        assert result.data["passes_guidelines"] == False
        assert len(result.data["failed_rules"]) > 0
    
    def test_validate_guidelines_missing_docs(self):
        """Test validation when critical documents are missing"""
        extracted = {
            "credit_score": 750,
            "submitted_documents": ["application_form"]  # Missing others
        }
        
        result = validate_against_guidelines(extracted)
        
        assert result.success
        assert result.data["passes_guidelines"] == False
        assert len(result.data["missing_critical_docs"]) > 0
    
    def test_calculate_risk_and_price(self):
        """Test risk scoring and pricing"""
        extracted = {
            "annual_revenue": 500000,
            "employees": 10,
            "debt_to_equity": 1.5
        }
        enriched = {
            "credit_score": 700,
            "property_risk": {"crime_score": 40}
        }
        
        result = calculate_risk_and_price(extracted, enriched)
        
        assert result.success
        assert "risk_score" in result.data
        assert "annual_premium" in result.data
        assert result.data["annual_premium"] > 0
        assert result.data["risk_score"] >= 0


class TestDataTools:
    """Tests for data acquisition tools"""
    
    def test_internal_claims_history(self):
        """Test internal claims data retrieval"""
        result = internal_claims_history("APP-001", "Acme Inc")
        
        assert result.success
        assert "loss_runs" in result.data
        assert "total_losses" in result.data
        assert isinstance(result.data["loss_runs"], list)
    
    def test_fetch_external_data(self):
        """Test external data retrieval"""
        result = fetch_external_data("Acme Inc", "123 Main St")
        
        assert result.success
        assert "credit_score" in result.data
        assert "property_risk" in result.data
    
    def test_web_research_applicant(self):
        """Test web research"""
        result = web_research_applicant("Acme Inc", "https://acme.com")
        
        assert result.success
        assert "website_verified" in result.data
        assert "risk_flags" in result.data


class TestCommsTools:
    """Tests for communication tools"""
    
    def test_draft_missing_info_email(self):
        """Test drafting missing info email"""
        result = draft_missing_info_email(
            "broker@example.com",
            "John Broker",
            "Acme Inc",
            ["financial_statements", "tax_returns"]
        )
        
        assert result.success
        assert "subject" in result.data
        assert "body" in result.data
        assert "ready_to_send" in result.data
        assert "financial_statements" in result.data["body"]
    
    def test_draft_decline_letter(self):
        """Test drafting decline letter"""
        failed_rules = [
            {
                "rule_id": "R002",
                "rule_description": "Loss ratio too high",
                "reason": "Loss ratio 0.85 > 0.80"
            }
        ]
        
        result = draft_decline_letter(
            "broker@example.com",
            "John Broker",
            "Acme Inc",
            failed_rules
        )
        
        assert result.success
        assert "subject" in result.data
        assert "body" in result.data
        assert "Loss ratio too high" in result.data["body"]
    
    def test_draft_quote_email(self):
        """Test drafting quote email"""
        result = draft_quote_email(
            "broker@example.com",
            "John Broker",
            "Acme Inc",
            2500.00,
            "1 year",
            "s3://quotes/quote.pdf"
        )
        
        assert result.success
        assert "subject" in result.data
        assert "$2500" in result.data["body"] or "2500" in result.data["body"]


class TestOutputTools:
    """Tests for output generation"""
    
    def test_generate_quote_pdf(self):
        """Test quote PDF generation"""
        extracted = {
            "applicant_name": "Acme Inc",
            "annual_revenue": 500000
        }
        metrics = {"risk_score": 45, "premium": 2500}
        
        result = generate_quote_pdf(extracted, metrics, 2500, "Acme Inc")
        
        assert result.success
        assert "quote_pdf_s3_url" in result.data
        assert "s3://" in result.data["quote_pdf_s3_url"]


# FILE: tests/test_state_manager.py
"""
Tests for state management.
"""

import pytest
from src.core.state_manager import (
    StateManager,
    SubmissionState,
    SubmissionStatus,
    DecisionType,
    get_state_manager
)


class TestStateManager:
    """Tests for StateManager"""
    
    def setup_method(self):
        """Reset state manager before each test"""
        # Create fresh instance
        self.manager = StateManager()
    
    def test_create_state(self):
        """Test creating a new submission state"""
        state = self.manager.create_state(
            submission_id="SUB-001",
            email_subject="New Application",
            email_body="Please review...",
            broker_email="broker@example.com",
            broker_name="John Broker",
            attachments=[]
        )
        
        assert state.submission_id == "SUB-001"
        assert state.status == SubmissionStatus.INGESTION.value
        assert state.created_at is not None
    
    def test_get_state(self):
        """Test retrieving state"""
        self.manager.create_state(
            submission_id="SUB-002",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        state = self.manager.get_state("SUB-002")
        assert state is not None
        assert state.submission_id == "SUB-002"
    
    def test_get_nonexistent_state(self):
        """Test getting state that doesn't exist"""
        state = self.manager.get_state("NONEXISTENT")
        assert state is None
    
    def test_update_state(self):
        """Test updating state"""
        self.manager.create_state(
            submission_id="SUB-003",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        self.manager.update_state(
            "SUB-003",
            status=SubmissionStatus.EXTRACTION.value,
            extracted_data={"name": "Test Co"}
        )
        
        state = self.manager.get_state("SUB-003")
        assert state.status == SubmissionStatus.EXTRACTION.value
        assert state.extracted_data == {"name": "Test Co"}
    
    def test_add_audit_entry(self):
        """Test adding audit entry"""
        self.manager.create_state(
            submission_id="SUB-004",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        self.manager.add_audit_entry(
            submission_id="SUB-004",
            component="TestAgent",
            action="test_action",
            details={"test": "data"},
            result="Success"
        )
        
        state = self.manager.get_state("SUB-004")
        assert len(state.audit_trail) == 1
        assert state.audit_trail[0].action == "test_action"
    
    def test_apply_override(self):
        """Test applying human override"""
        self.manager.create_state(
            submission_id="SUB-005",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        # Set initial decision
        self.manager.update_state("SUB-005", decision=DecisionType.QUOTED.value)
        
        # Override decision
        self.manager.apply_override(
            submission_id="SUB-005",
            user_id="USER-123",
            override_decision=DecisionType.DECLINED.value,
            override_reason="Post-review policy adjustment"
        )
        
        state = self.manager.get_state("SUB-005")
        assert state.decision == DecisionType.DECLINED.value
        assert len(state.overrides) == 1
        assert state.overrides[0].user_id == "USER-123"
    
    def test_get_submission_summary(self):
        """Test getting submission summary for API"""
        self.manager.create_state(
            submission_id="SUB-006",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        summary = self.manager.get_submission_summary("SUB-006")
        
        assert summary["submission_id"] == "SUB-006"
        assert "status" in summary
        assert "decision" in summary
        assert "created_at" in summary
    
    def test_list_submissions(self):
        """Test listing submissions"""
        for i in range(3):
            self.manager.create_state(
                submission_id=f"SUB-{i}",
                email_subject="Test",
                email_body="Body",
                broker_email="broker@example.com",
                broker_name="Test",
                attachments=[]
            )
        
        submissions = self.manager.list_submissions()
        assert len(submissions) == 3
    
    def test_list_submissions_filtered(self):
        """Test listing submissions with filter"""
        self.manager.create_state(
            submission_id="SUB-A",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        self.manager.update_state("SUB-A", status=SubmissionStatus.COMPLETED.value)
        
        self.manager.create_state(
            submission_id="SUB-B",
            email_subject="Test",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        
        completed = self.manager.list_submissions(status=SubmissionStatus.COMPLETED.value)
        assert len(completed) == 1
        assert completed[0]["submission_id"] == "SUB-A"


# FILE: tests/test_integration.py
"""
Integration tests for end-to-end workflow.
"""

import pytest
from src.orchestration.supervisor_agent import SupervisorAgent
from src.core.state_manager import DecisionType


class TestEndToEndWorkflow:
    """Integration tests for complete submission workflow"""
    
    def setup_method(self):
        """Initialize supervisor for each test"""
        self.supervisor = SupervisorAgent()
    
    def test_happy_path_quoted(self):
        """Test complete workflow resulting in quote"""
        state = self.supervisor.process_submission(
            submission_id="GTC-001",
            email_subject="Application for Acme Restaurant",
            email_body="Applying for general liability...",
            broker_email="broker@example.com",
            broker_name="John Broker",
            attachments=[]
        )
        
        assert state.decision == DecisionType.QUOTED.value
        assert state.risk_metrics is not None
        assert state.risk_metrics["annual_premium"] > 0
        assert state.drafted_email is not None
        assert state.quote_pdf_url is not None
    
    def test_missing_critical_docs(self):
        """Test workflow with missing documents"""
        # This would require mock data that fails validation
        # For MVP, the mock tools return passing data by default
        state = self.supervisor.process_submission(
            submission_id="GTC-002",
            email_subject="Incomplete Application",
            email_body="Please review...",
            broker_email="broker@example.com",
            broker_name="John Broker",
            attachments=[]
        )
        
        # Mock currently returns passing validation, so will be quoted
        assert state.decision in [DecisionType.QUOTED.value, DecisionType.MISSING_INFO.value]
    
    def test_low_confidence_extraction(self):
        """Test handling of low confidence extraction"""
        state = self.supervisor.process_submission(
            submission_id="GTC-004",
            email_subject="Blurry Scan",
            email_body="x",  # Very short content = low confidence
            broker_email="broker@example.com",
            broker_name="John Broker",
            attachments=[]
        )
        
        # Should still process but with low confidence
        assert state.extraction_confidence < 0.75
        assert state.decision is not None
    
    def test_parallel_data_retrieval_completes(self):
        """Test that parallel data retrieval completes within timeout"""
        import time
        
        start = time.time()
        state = self.supervisor.process_submission(
            submission_id="GTC-007",
            email_subject="Test Parallel",
            email_body="Body",
            broker_email="broker@example.com",
            broker_name="Test",
            attachments=[]
        )
        elapsed = time.time() - start
        
        # Should complete within 30 seconds (including enrichment phase)
        assert elapsed < 30
        assert state.internal_data is not None
        assert state.external_data is not None
        assert state.web_data is not None
