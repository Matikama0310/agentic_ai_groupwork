"""
API Handlers: FastAPI application.

Endpoints:
  POST /submit    - Process new insurance application
  POST /override  - Apply human underwriter override
  GET  /status/{submission_id} - Query submission status
  GET  /status    - List all submissions
  GET  /health    - Health check
"""

import logging
from datetime import datetime
from typing import List, Optional
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
