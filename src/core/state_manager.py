# FILE: src/core/state_manager.py
"""
State Manager: In-memory state store for submissions (MVP).
Handles CRUD operations, overrides, and state transitions.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class SubmissionStatus(str, Enum):
    """Valid submission statuses"""
    INGESTION = "INGESTION"
    EXTRACTION = "EXTRACTION"
    ENRICHMENT = "ENRICHMENT"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DecisionType(str, Enum):
    """Valid decision outcomes"""
    QUOTED = "QUOTED"
    DECLINED = "DECLINED"
    MISSING_INFO = "MISSING_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    UNKNOWN = "UNKNOWN"


_VALID_DECISIONS = {d.value for d in DecisionType}
_VALID_STATUSES = {s.value for s in SubmissionStatus}


@dataclass
class Override:
    """Represents a human override to AI decision"""
    timestamp: str
    user_id: str
    override_decision: str
    override_reason: str
    previous_decision: str


@dataclass
class AuditEntry:
    """Represents a single audit trail entry"""
    timestamp: str
    component: str  # agent or tool name
    action: str
    details: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SubmissionState:
    """
    Complete state for a submission throughout its lifecycle.
    This is what gets passed through the LanGraph workflow.
    """
    # Identifiers
    submission_id: str
    created_at: str
    updated_at: str

    # Input
    email_subject: str
    email_body: str
    broker_email: str
    broker_name: str
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    # Phase 1: Extraction
    extracted_data: Optional[Dict[str, Any]] = None
    extraction_confidence: Optional[float] = None
    document_types: Optional[List[str]] = None

    # Phase 2a: Enrichment (parallel)
    internal_data: Optional[Dict[str, Any]] = None
    external_data: Optional[Dict[str, Any]] = None
    web_data: Optional[Dict[str, Any]] = None

    # Phase 2b: Analysis
    naics_code: Optional[str] = None
    classification_confidence: Optional[float] = None
    validation_result: Optional[Dict[str, Any]] = None
    risk_metrics: Optional[Dict[str, Any]] = None

    # Phase 3: Output
    decision: str = DecisionType.UNKNOWN.value
    drafted_email: Optional[Dict[str, Any]] = None
    quote_pdf_url: Optional[str] = None

    # Metadata
    status: str = SubmissionStatus.INGESTION.value
    errors: List[Dict[str, Any]] = field(default_factory=list)
    audit_trail: List[AuditEntry] = field(default_factory=list)
    overrides: List[Override] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert dataclass objects to dicts
        data['audit_trail'] = [asdict(entry) if isinstance(entry, AuditEntry) else entry
                               for entry in self.audit_trail]
        data['overrides'] = [asdict(override) if isinstance(override, Override) else override
                            for override in self.overrides]
        return data


class StateManager:
    """
    In-memory state management for submissions.

    For MVP: Uses a simple in-memory dict.
    For production: Replace with DynamoDB or similar.
    """

    def __init__(self):
        """Initialize state store"""
        self._store: Dict[str, SubmissionState] = {}
        logger.info("StateManager initialized (in-memory backend)")

    def create_state(self, submission_id: str, email_subject: str, email_body: str,
                    broker_email: str, broker_name: str,
                    attachments: List[Dict[str, Any]]) -> SubmissionState:
        """
        Create initial state for a new submission.

        Raises:
            ValueError: if submission_id is empty or already exists
        """
        if not isinstance(submission_id, str) or not submission_id.strip():
            raise ValueError("submission_id must be a non-empty string")
        if submission_id in self._store:
            raise ValueError(f"Submission {submission_id} already exists")

        now = datetime.now(UTC).isoformat()

        state = SubmissionState(
            submission_id=submission_id,
            created_at=now,
            updated_at=now,
            email_subject=email_subject or "",
            email_body=email_body or "",
            broker_email=broker_email or "",
            broker_name=broker_name or "",
            attachments=attachments if isinstance(attachments, list) else [],
        )

        self._store[submission_id] = state
        logger.info(f"State created for submission {submission_id}")
        return state

    def get_state(self, submission_id: str) -> Optional[SubmissionState]:
        """Retrieve state for a submission"""
        state = self._store.get(submission_id)
        if not state:
            logger.warning(f"State not found for submission {submission_id}")
        return state

    def update_state(self, submission_id: str, **kwargs) -> SubmissionState:
        """
        Update state with new values.

        Raises:
            ValueError: if submission not found or field not allowed
        """
        state = self.get_state(submission_id)
        if not state:
            raise ValueError(f"State not found for submission {submission_id}")

        # Update allowed fields
        allowed_fields = {
            'extracted_data', 'extraction_confidence', 'document_types',
            'internal_data', 'external_data', 'web_data',
            'naics_code', 'classification_confidence', 'validation_result',
            'risk_metrics', 'decision', 'drafted_email', 'quote_pdf_url',
            'status', 'errors'
        }

        for key, value in kwargs.items():
            if key not in allowed_fields:
                raise ValueError(f"Cannot update field {key}; not in allowed_fields")
            # Validate decision values
            if key == 'decision' and isinstance(value, str) and value not in _VALID_DECISIONS:
                logger.warning(f"Non-standard decision value: {value}")
            # Validate status values
            if key == 'status' and isinstance(value, str) and value not in _VALID_STATUSES:
                logger.warning(f"Non-standard status value: {value}")
            setattr(state, key, value)

        state.updated_at = datetime.now(UTC).isoformat()
        logger.info(f"State updated for submission {submission_id}: {list(kwargs.keys())}")
        return state

    def add_audit_entry(self, submission_id: str, component: str, action: str,
                       details: Dict[str, Any], result: Optional[str] = None,
                       error: Optional[str] = None) -> None:
        """
        Add an entry to the audit trail.

        Raises:
            ValueError: if submission not found
        """
        state = self.get_state(submission_id)
        if not state:
            raise ValueError(f"State not found for submission {submission_id}")

        entry = AuditEntry(
            timestamp=datetime.now(UTC).isoformat(),
            component=component or "unknown",
            action=action or "unknown",
            details=details if isinstance(details, dict) else {},
            result=result,
            error=error
        )

        state.audit_trail.append(entry)
        logger.info(f"Audit entry added for submission {submission_id}: {action}")

    def apply_override(self, submission_id: str, user_id: str,
                      override_decision: str, override_reason: str) -> None:
        """
        Apply a human override to a submission's decision.

        Raises:
            ValueError: if submission not found, user_id missing, decision invalid, or reason empty
        """
        state = self.get_state(submission_id)
        if not state:
            raise ValueError(f"State not found for submission {submission_id}")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")
        if override_decision not in _VALID_DECISIONS:
            raise ValueError(f"Invalid decision: {override_decision!r}. Must be one of {_VALID_DECISIONS}")
        if not isinstance(override_reason, str) or not override_reason.strip():
            raise ValueError("override_reason is required")

        override = Override(
            timestamp=datetime.now(UTC).isoformat(),
            user_id=user_id,
            override_decision=override_decision,
            override_reason=override_reason,
            previous_decision=state.decision
        )

        state.overrides.append(override)
        state.decision = override_decision
        state.updated_at = datetime.now(UTC).isoformat()

        logger.warning(f"Override applied to submission {submission_id}: "
                      f"{state.decision} -> {override_decision} (reason: {override_reason})")
        self.add_audit_entry(
            submission_id=submission_id,
            component="human",
            action="override_decision",
            details={"override_reason": override_reason},
            result=f"Decision changed to {override_decision}"
        )

    def get_submission_summary(self, submission_id: str) -> Dict[str, Any]:
        """Get a summary of submission state (for API responses)."""
        state = self.get_state(submission_id)
        if not state:
            return {"error": f"Submission {submission_id} not found"}

        return {
            "submission_id": submission_id,
            "status": state.status,
            "decision": state.decision,
            "extracted_data": state.extracted_data,
            "risk_metrics": state.risk_metrics,
            "drafted_email": state.drafted_email,
            "quote_pdf_url": state.quote_pdf_url,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "overrides_count": len(state.overrides),
            "audit_trail_length": len(state.audit_trail)
        }

    def list_submissions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all submissions, optionally filtered by status."""
        result = []
        for submission_id, state in self._store.items():
            if status and state.status != status:
                continue
            result.append(self.get_submission_summary(submission_id))
        return result

    def delete_state(self, submission_id: str) -> None:
        """Delete state (use with caution; may break audit trail)"""
        if submission_id in self._store:
            del self._store[submission_id]
            logger.warning(f"State deleted for submission {submission_id}")
        else:
            logger.warning(f"Attempt to delete non-existent state {submission_id}")


# Global instance (singleton pattern)
_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    """Get or create global StateManager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
