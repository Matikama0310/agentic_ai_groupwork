"""
API Handlers: FastAPI application + Lambda-compatible handlers.

Endpoints:
  POST /submit    - Process new insurance application
  POST /override  - Apply human underwriter override
  GET  /status/{submission_id} - Query submission status
  GET  /status    - List all submissions
  GET  /health    - Health check
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.state_manager import get_state_manager
from src.orchestration.supervisor_agent import SupervisorAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class Attachment(BaseModel):
    filename: str = ""
    content: str = ""
    type: str = ""


class SubmissionRequest(BaseModel):
    email_subject: str
    email_body: str
    broker_email: str
    broker_name: str = ""
    attachments: List[Attachment] = []


class OverrideRequest(BaseModel):
    submission_id: str
    user_id: str
    override_decision: str
    override_reason: str = ""


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and return the FastAPI application."""
    app = FastAPI(
        title="NorthStar Underwriting API",
        description="Agentic AI underwriting system for NorthStar Insurance Group",
        version="1.0.0",
    )

    supervisor = SupervisorAgent()
    sm = get_state_manager()

    @app.post("/submit")
    def submit(req: SubmissionRequest):
        sub_id = f"SUB-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8].upper()}"
        state = supervisor.process_submission(
            submission_id=sub_id,
            email_subject=req.email_subject,
            email_body=req.email_body,
            broker_email=req.broker_email,
            broker_name=req.broker_name,
            attachments=[a.model_dump() for a in req.attachments],
        )
        return {
            "submission_id": sub_id,
            "decision": state.decision,
            "status": state.status,
            "message": f"Processed. Decision: {state.decision}",
            "data": sm.get_submission_summary(sub_id),
        }

    @app.post("/override")
    def override(req: OverrideRequest):
        if req.override_decision not in ["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"]:
            raise HTTPException(400, f"Invalid override_decision: {req.override_decision}")
        state = sm.get_state(req.submission_id)
        if not state:
            raise HTTPException(404, f"Submission {req.submission_id} not found")
        sm.apply_override(req.submission_id, req.user_id, req.override_decision, req.override_reason)
        return {
            "submission_id": req.submission_id,
            "message": "Override applied",
            "data": sm.get_submission_summary(req.submission_id),
        }

    @app.get("/status/{submission_id}")
    def status(submission_id: str):
        summary = sm.get_submission_summary(submission_id)
        if "error" in summary:
            raise HTTPException(404, f"Submission {submission_id} not found")
        return {"message": "Found", "data": summary}

    @app.get("/status")
    def list_all(status_filter: Optional[str] = None):
        subs = sm.list_submissions(status=status_filter)
        return {"message": f"Found {len(subs)} submissions", "data": {"total": len(subs), "submissions": subs}}

    @app.get("/health")
    def health():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    return app


# ---------------------------------------------------------------------------
# Legacy handler classes (Lambda compatibility)
# ---------------------------------------------------------------------------
class SubmissionHandler:
    """Handles new submission requests (Lambda-style)."""

    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.state_manager = get_state_manager()

    def handle_submission(self, event: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not event:
                return self._error(400, "Event is empty")
            email_subject = event.get("email_subject", "")
            email_body = event.get("email_body", "")
            broker_email = event.get("broker_email", "")
            broker_name = event.get("broker_name", "")
            attachments = event.get("attachments", [])
            if not all([email_subject, email_body, broker_email]):
                return self._error(400, "Missing required fields: email_subject, email_body, broker_email")
            sub_id = f"SUB-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8].upper()}"
            state = self.supervisor.process_submission(
                sub_id, email_subject, email_body, broker_email, broker_name, attachments,
            )
            return {
                "status_code": 200,
                "submission_id": sub_id,
                "decision": state.decision,
                "message": f"Processed. Decision: {state.decision}",
                "data": self.state_manager.get_submission_summary(sub_id),
            }
        except Exception as e:
            logger.exception("Submission error")
            return self._error(500, str(e))

    def _error(self, code: int, msg: str):
        return {"status_code": code, "submission_id": None, "decision": None, "message": msg, "data": None}


class OverrideHandler:
    """Handles human overrides (Lambda-style)."""

    def __init__(self):
        self.state_manager = get_state_manager()

    def handle_override(self, event: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sid = event.get("submission_id")
            uid = event.get("user_id")
            dec = event.get("override_decision")
            reason = event.get("override_reason", "")
            if not all([sid, uid, dec]):
                return {"status_code": 400, "submission_id": None, "message": "Missing fields", "data": None}
            if dec not in ["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"]:
                return {"status_code": 400, "submission_id": None, "message": f"Invalid decision: {dec}", "data": None}
            state = self.state_manager.get_state(sid)
            if not state:
                return {"status_code": 404, "submission_id": None, "message": "Not found", "data": None}
            self.state_manager.apply_override(sid, uid, dec, reason)
            return {
                "status_code": 200,
                "submission_id": sid,
                "message": "Override applied",
                "data": self.state_manager.get_submission_summary(sid),
            }
        except Exception as e:
            return {"status_code": 500, "submission_id": None, "message": str(e), "data": None}


class QueryHandler:
    """Handles status queries (Lambda-style)."""

    def __init__(self):
        self.state_manager = get_state_manager()

    def handle_status_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sid = event.get("submission_id")
            if sid:
                summary = self.state_manager.get_submission_summary(sid)
                if "error" in summary:
                    return {"status_code": 404, "message": "Not found", "data": None}
                return {"status_code": 200, "message": "Found", "data": summary}
            subs = self.state_manager.list_submissions()
            return {"status_code": 200, "message": f"Found {len(subs)}", "data": {"total": len(subs), "submissions": subs}}
        except Exception as e:
            return {"status_code": 500, "message": str(e), "data": None}
