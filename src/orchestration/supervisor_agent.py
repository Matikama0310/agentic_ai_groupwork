# FILE: src/orchestration/supervisor_agent.py
"""
Supervisor Agent: Main orchestrator using LanGraph.
Coordinates all sub-agents and ensures workflow compliance.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import tools (mock implementations)
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

from src.core.state_manager import (
    SubmissionState,
    SubmissionStatus,
    DecisionType,
    get_state_manager
)

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Orchestrates the entire underwriting workflow.
    Uses LanGraph for state management and tool calling.
    """
    
    def __init__(self):
        self.state_manager = get_state_manager()
        self.submission_timeout_seconds = 30
        logger.info("SupervisorAgent initialized")
    
    def process_submission(self, submission_id: str, email_subject: str, email_body: str,
                          broker_email: str, broker_name: str,
                          attachments: List[Dict[str, Any]]) -> SubmissionState:
        """
        Main entry point: Process a new submission through the entire workflow.
        
        Workflow:
        1. INGESTION: Create state
        2. EXTRACTION: Parse documents
        3. ENRICHMENT: Parallel data retrieval
        4. ANALYSIS: Validate & assess risk
        5. DECISION: Generate output
        
        Args:
            submission_id: Unique submission ID
            email_subject: Email subject
            email_body: Email body
            broker_email: Broker's email
            broker_name: Broker's name
            attachments: List of attachment dicts
        
        Returns:
            Final SubmissionState
        """
        logger.info(f"[{submission_id}] Starting submission processing")
        
        try:
            # Step 1: Create initial state
            state = self.state_manager.create_state(
                submission_id=submission_id,
                email_subject=email_subject,
                email_body=email_body,
                broker_email=broker_email,
                broker_name=broker_name,
                attachments=attachments
            )
            state.status = SubmissionStatus.INGESTION.value
            
            # Step 2: Extract data from documents
            state = self._extraction_phase(state)
            if not self._should_continue(state):
                return state
            
            # Step 3: Enrich with external data (parallel)
            state = self._enrichment_phase(state)
            
            # Step 4: Analyze and validate
            state = self._analysis_phase(state)
            if not self._should_continue(state):
                return state
            
            # Step 5: Generate output
            state = self._output_phase(state)
            
            state.status = SubmissionStatus.COMPLETED.value
            logger.info(f"[{submission_id}] Submission processing completed: {state.decision}")
            
            return state
        
        except Exception as e:
            logger.exception(f"[{submission_id}] Error during processing")
            state.status = SubmissionStatus.FAILED.value
            state.errors.append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "phase": "unknown"
            })
            self.state_manager.update_state(submission_id, status=state.status, errors=state.errors)
            return state
    
    def _extraction_phase(self, state: SubmissionState) -> SubmissionState:
        """
        Phase 1: Extract structured data from submissions.
        
        Agents: ClassificationAgent (ingest + classify)
        Tools: extract_structured_data()
        """
        state.status = SubmissionStatus.EXTRACTION.value
        logger.info(f"[{state.submission_id}] === EXTRACTION PHASE ===")
        
        try:
            # Combine email body + attachment content
            document_content = f"{state.email_subject}\n{state.email_body}"
            for att in state.attachments:
                document_content += f"\n{att.get('content', '')}"
            
            # Extract structured data
            logger.info(f"[{state.submission_id}] Calling extract_structured_data")
            result = extract_structured_data(document_content)
            
            if result.success:
                state.extracted_data = result.data.get("extracted_fields")
                state.extraction_confidence = result.data.get("extraction_confidence")
                state.document_types = result.data.get("document_types", [])
                
                logger.info(f"[{state.submission_id}] Extraction successful, confidence={state.extraction_confidence}")
                
                self.state_manager.add_audit_entry(
                    submission_id=state.submission_id,
                    component="ClassificationAgent",
                    action="extract_structured_data",
                    details={"document_length": len(document_content)},
                    result=f"Extracted {len(state.extracted_data or {})} fields"
                )
                
                # Classify business (NAICS code)
                logger.info(f"[{state.submission_id}] Calling classify_naics_code")
                business_desc = state.extracted_data.get("business_type", "")
                business_name = state.extracted_data.get("applicant_name", "")
                naics_result = classify_naics_code(business_desc, business_name)
                
                if naics_result.success:
                    state.naics_code = naics_result.data.get("naics_code")
                    state.classification_confidence = naics_result.data.get("confidence")
                    logger.info(f"[{state.submission_id}] NAICS: {state.naics_code}, confidence={state.classification_confidence}")
                    
                    self.state_manager.add_audit_entry(
                        submission_id=state.submission_id,
                        component="ClassificationAgent",
                        action="classify_naics_code",
                        details={"business_description": business_desc},
                        result=f"NAICS {state.naics_code}"
                    )
                else:
                    logger.warning(f"[{state.submission_id}] NAICS classification failed")
                    state.errors.append({"phase": "extraction", "error": naics_result.error})
            else:
                logger.error(f"[{state.submission_id}] Extraction failed: {result.error}")
                state.errors.append({"phase": "extraction", "error": result.error})
        
        except Exception as e:
            logger.exception(f"[{state.submission_id}] Exception in extraction phase")
            state.errors.append({"phase": "extraction", "error": str(e)})
        
        self.state_manager.update_state(
            state.submission_id,
            status=state.status,
            extracted_data=state.extracted_data,
            extraction_confidence=state.extraction_confidence,
            naics_code=state.naics_code,
            classification_confidence=state.classification_confidence,
            errors=state.errors
        )
        
        return state
    
    def _enrichment_phase(self, state: SubmissionState) -> SubmissionState:
        """
        Phase 2a: Enrich with external data (parallel execution).
        
        Agents: DataRetrieverAgent (3x parallel)
        Tools: internal_claims_history(), fetch_external_data(), web_research_applicant()
        """
        state.status = SubmissionStatus.ENRICHMENT.value
        logger.info(f"[{state.submission_id}] === ENRICHMENT PHASE (PARALLEL) ===")
        
        applicant_id = state.extracted_data.get("applicant_id", state.submission_id)
        applicant_name = state.extracted_data.get("applicant_name", "Unknown")
        applicant_address = state.extracted_data.get("address", "")
        applicant_website = state.extracted_data.get("website", "")
        
        # Parallel execution: in real system, use asyncio or ThreadPoolExecutor
        # For MVP, execute sequentially but simulate parallelism
        
        # 1. Internal claims history
        logger.info(f"[{state.submission_id}] Calling internal_claims_history")
        try:
            result = internal_claims_history(applicant_id, applicant_name)
            if result.success:
                state.internal_data = result.data
                logger.info(f"[{state.submission_id}] Internal data retrieved: {len(result.data.get('loss_runs', []))} loss runs")
                self.state_manager.add_audit_entry(
                    state.submission_id, "DataRetrieverAgent_Internal", "internal_claims_history",
                    {"applicant_id": applicant_id}, result=f"Retrieved {len(state.internal_data.get('loss_runs', []))} claims"
                )
        except Exception as e:
            logger.warning(f"[{state.submission_id}] Internal data retrieval failed: {e}")
            state.internal_data = {"loss_runs": [], "total_losses": 0}
        
        # 2. External data (D&B, HazardHub)
        logger.info(f"[{state.submission_id}] Calling fetch_external_data")
        try:
            result = fetch_external_data(applicant_name, applicant_address)
            if result.success:
                state.external_data = result.data
                logger.info(f"[{state.submission_id}] External data retrieved: credit_score={result.data.get('credit_score')}")
                self.state_manager.add_audit_entry(
                    state.submission_id, "DataRetrieverAgent_External", "fetch_external_data",
                    {"applicant_name": applicant_name}, result=f"Credit score: {state.external_data.get('credit_score')}"
                )
        except Exception as e:
            logger.warning(f"[{state.submission_id}] External data retrieval failed: {e}")
            state.external_data = {"credit_score": 0}
        
        # 3. Web research
        logger.info(f"[{state.submission_id}] Calling web_research_applicant")
        try:
            result = web_research_applicant(applicant_name, applicant_website)
            if result.success:
                state.web_data = result.data
                logger.info(f"[{state.submission_id}] Web data retrieved: {len(result.data.get('risk_flags', []))} risk flags")
                self.state_manager.add_audit_entry(
                    state.submission_id, "DataRetrieverAgent_OpenSource", "web_research_applicant",
                    {"applicant_name": applicant_name}, result=f"Web verified: {state.web_data.get('website_verified')}"
                )
        except Exception as e:
            logger.warning(f"[{state.submission_id}] Web research failed: {e}")
            state.web_data = {"risk_flags": []}
        
        self.state_manager.update_state(
            state.submission_id,
            status=state.status,
            internal_data=state.internal_data,
            external_data=state.external_data,
            web_data=state.web_data
        )
        
        return state
    
    def _analysis_phase(self, state: SubmissionState) -> SubmissionState:
        """
        Phase 2b: Validate against guidelines and assess risk.
        
        Agents: AnalystAgent (gap analysis + risk assessment)
        Tools: validate_against_guidelines(), calculate_risk_and_price()
        """
        state.status = SubmissionStatus.ANALYSIS.value
        logger.info(f"[{state.submission_id}] === ANALYSIS PHASE ===")
        
        # Validate against guidelines
        logger.info(f"[{state.submission_id}] Calling validate_against_guidelines")
        try:
            result = validate_against_guidelines(
                state.extracted_data or {},
                state.external_data,
                state.web_data,
                state.internal_data
            )
            
            if result.success:
                state.validation_result = result.data
                logger.info(f"[{state.submission_id}] Validation: passes={result.data.get('passes_guidelines')}, "
                           f"failed_rules={len(result.data.get('failed_rules', []))}")
                
                self.state_manager.add_audit_entry(
                    state.submission_id, "AnalystAgent_GapAnalysis", "validate_against_guidelines",
                    {}, result=f"Guidelines pass: {result.data.get('passes_guidelines')}"
                )
        except Exception as e:
            logger.exception(f"[{state.submission_id}] Validation failed")
            state.errors.append({"phase": "analysis", "error": str(e)})
            state.decision = DecisionType.MANUAL_REVIEW.value
            return state
        
        # If guidelines failed or missing docs, stop here and generate output
        if not state.validation_result.get("passes_guidelines"):
            logger.warning(f"[{state.submission_id}] Guidelines validation failed")
            if state.validation_result.get("missing_critical_docs"):
                state.decision = DecisionType.MISSING_INFO.value
            else:
                state.decision = DecisionType.DECLINED.value
            self.state_manager.update_state(state.submission_id, validation_result=state.validation_result, decision=state.decision)
            return state
        
        # Calculate risk and pricing
        logger.info(f"[{state.submission_id}] Calling calculate_risk_and_price")
        try:
            result = calculate_risk_and_price(
                state.extracted_data or {},
                state.external_data,
                state.internal_data
            )
            
            if result.success:
                state.risk_metrics = result.data
                logger.info(f"[{state.submission_id}] Risk assessment: score={result.data.get('risk_score')}, "
                           f"premium=${result.data.get('annual_premium'):.2f}")
                
                state.decision = DecisionType.QUOTED.value
                
                self.state_manager.add_audit_entry(
                    state.submission_id, "AnalystAgent_RiskAssessment", "calculate_risk_and_price",
                    {}, result=f"Premium: ${result.data.get('annual_premium'):.2f}"
                )
            else:
                logger.error(f"[{state.submission_id}] Risk calculation failed")
                state.decision = DecisionType.MANUAL_REVIEW.value
                state.errors.append({"phase": "analysis", "error": result.error})
        
        except Exception as e:
            logger.exception(f"[{state.submission_id}] Risk calculation exception")
            state.decision = DecisionType.MANUAL_REVIEW.value
            state.errors.append({"phase": "analysis", "error": str(e)})
        
        self.state_manager.update_state(
            state.submission_id,
            status=state.status,
            validation_result=state.validation_result,
            risk_metrics=state.risk_metrics,
            decision=state.decision,
            errors=state.errors
        )
        
        return state
    
    def _output_phase(self, state: SubmissionState) -> SubmissionState:
        """
        Phase 3: Generate output (draft emails/PDFs).
        
        Agents: BrokerLiaisonAgent, OutputAgent
        Tools: draft_missing_info_email(), draft_decline_letter(), draft_quote_email(), generate_quote_pdf()
        """
        state.status = SubmissionStatus.DECISION.value
        logger.info(f"[{state.submission_id}] === OUTPUT PHASE (decision={state.decision}) ===")
        
        applicant_name = state.extracted_data.get("applicant_name", "Unknown")
        
        try:
            if state.decision == DecisionType.MISSING_INFO.value:
                # Draft missing info email
                missing_docs = state.validation_result.get("missing_critical_docs", [])
                logger.info(f"[{state.submission_id}] Drafting missing info email for {len(missing_docs)} docs")
                
                result = draft_missing_info_email(
                    state.broker_email, state.broker_name, applicant_name, missing_docs
                )
                if result.success:
                    state.drafted_email = result.data
                    self.state_manager.add_audit_entry(
                        state.submission_id, "BrokerLiaisonAgent", "draft_missing_info_email",
                        {"missing_docs": missing_docs}, result="Email drafted"
                    )
            
            elif state.decision == DecisionType.DECLINED.value:
                # Draft decline letter
                failed_rules = state.validation_result.get("failed_rules", [])
                logger.info(f"[{state.submission_id}] Drafting decline letter for {len(failed_rules)} violations")
                
                result = draft_decline_letter(
                    state.broker_email, state.broker_name, applicant_name, failed_rules
                )
                if result.success:
                    state.drafted_email = result.data
                    self.state_manager.add_audit_entry(
                        state.submission_id, "BrokerLiaisonAgent", "draft_decline_letter",
                        {"failed_rules": len(failed_rules)}, result="Letter drafted"
                    )
            
            elif state.decision == DecisionType.QUOTED.value:
                # Generate quote PDF
                premium = state.risk_metrics.get("annual_premium", 0)
                logger.info(f"[{state.submission_id}] Generating quote PDF for ${premium:.2f}")
                
                pdf_result = generate_quote_pdf(
                    state.extracted_data or {},
                    state.risk_metrics or {},
                    premium,
                    applicant_name
                )
                if pdf_result.success:
                    state.quote_pdf_url = pdf_result.data.get("quote_pdf_s3_url")
                    self.state_manager.add_audit_entry(
                        state.submission_id, "OutputAgent", "generate_quote_pdf",
                        {}, result=f"PDF: {state.quote_pdf_url}"
                    )
                
                # Draft quote email
                result = draft_quote_email(
                    state.broker_email, state.broker_name, applicant_name,
                    premium, "1 year", state.quote_pdf_url
                )
                if result.success:
                    state.drafted_email = result.data
                    self.state_manager.add_audit_entry(
                        state.submission_id, "BrokerLiaisonAgent", "draft_quote_email",
                        {"premium": premium}, result="Quote email drafted"
                    )
        
        except Exception as e:
            logger.exception(f"[{state.submission_id}] Exception in output phase")
            state.errors.append({"phase": "output", "error": str(e)})
        
        self.state_manager.update_state(
            state.submission_id,
            status=state.status,
            drafted_email=state.drafted_email,
            quote_pdf_url=state.quote_pdf_url,
            errors=state.errors
        )
        
        return state
    
    def _should_continue(self, state: SubmissionState) -> bool:
        """Check if workflow should continue"""
        return len(state.errors) == 0 or state.extraction_confidence >= 0.5
