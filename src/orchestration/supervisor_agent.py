"""
Supervisor Agent: Main orchestrator using LangGraph.
Coordinates all sub-agents and ensures workflow compliance.

This is the "Traffic Controller" and "Compliance Officer" from the architecture.
It receives submissions, decomposes work, assigns to worker agents via the
LangGraph StateGraph, and compiles the final recommendation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.core.state_manager import (
    AuditEntry,
    DecisionType,
    SubmissionState,
    SubmissionStatus,
    get_state_manager,
)
from src.orchestration.workflow import UnderwritingState, compile_workflow

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Orchestrates the entire underwriting workflow via LangGraph.
    Hard-coded with NorthStar risk appetite and guidelines.
    """

    def __init__(self):
        self.state_manager = get_state_manager()
        self.workflow = compile_workflow()
        logger.info("SupervisorAgent initialized with LangGraph workflow")

    def process_submission(
        self,
        submission_id: str,
        email_subject: str,
        email_body: str,
        broker_email: str,
        broker_name: str,
        attachments: List[Dict[str, Any]],
    ) -> SubmissionState:
        """
        Main entry point: run a submission through the LangGraph workflow.
        """
        logger.info(f"[{submission_id}] Starting submission processing")

        # Persist initial state
        db_state = self.state_manager.create_state(
            submission_id=submission_id,
            email_subject=email_subject,
            email_body=email_body,
            broker_email=broker_email,
            broker_name=broker_name,
            attachments=attachments,
        )

        # Build the graph input
        graph_input: UnderwritingState = {
            "submission_id": submission_id,
            "email_subject": email_subject,
            "email_body": email_body,
            "broker_email": broker_email,
            "broker_name": broker_name,
            "attachments": attachments,
            "decision": DecisionType.UNKNOWN.value,
            "status": SubmissionStatus.INGESTION.value,
            "errors": [],
            "audit_trail": [],
        }

        try:
            # Run the LangGraph workflow
            final_state = self.workflow.invoke(graph_input)

            # Sync back to persistence layer
            self._sync_to_db(submission_id, final_state, db_state)
            logger.info(f"[{submission_id}] Completed: decision={final_state.get('decision')}")

        except Exception as e:
            logger.exception(f"[{submission_id}] Workflow error")
            db_state.status = SubmissionStatus.FAILED.value
            db_state.errors.append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "phase": "workflow",
            })
            self.state_manager.update_state(
                submission_id, status=db_state.status, errors=db_state.errors
            )

        return self.state_manager.get_state(submission_id) or db_state

    def _sync_to_db(self, submission_id: str, graph_state: dict, db_state: SubmissionState):
        """Sync the final LangGraph state back to the persistence layer."""
        field_map = {
            "extracted_data": "extracted_data",
            "extraction_confidence": "extraction_confidence",
            "naics_code": "naics_code",
            "classification_confidence": "classification_confidence",
            "internal_data": "internal_data",
            "external_data": "external_data",
            "web_data": "web_data",
            "validation_result": "validation_result",
            "risk_metrics": "risk_metrics",
            "decision": "decision",
            "drafted_email": "drafted_email",
            "quote_pdf_url": "quote_pdf_url",
            "status": "status",
            "errors": "errors",
        }

        updates = {}
        for graph_key, db_key in field_map.items():
            val = graph_state.get(graph_key)
            if val is not None:
                updates[db_key] = val

        if updates:
            self.state_manager.update_state(submission_id, **updates)

        # Sync audit trail (graph uses dicts, DB uses AuditEntry dataclasses)
        audit_entries = graph_state.get("audit_trail", [])
        if isinstance(audit_entries, list):
            for entry in audit_entries:
                if isinstance(entry, dict):
                    self.state_manager.add_audit_entry(
                        submission_id,
                        entry.get("component", ""),
                        entry.get("action", ""),
                        {},
                        result=entry.get("result", ""),
                    )
