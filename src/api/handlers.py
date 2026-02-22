# FILE: src/api/handlers.py
"""
API Handlers: Lambda entry points and request/response handling.
"""

import json
import logging
from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime

from src.orchestration.supervisor_agent import SupervisorAgent
from src.core.state_manager import get_state_manager

logger = logging.getLogger(__name__)


class SubmissionHandler:
    """Handles new submission requests"""
    
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.state_manager = get_state_manager()
    
    def handle_submission(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming submission request.
        
        Expected event structure:
        {
            "email_subject": "...",
            "email_body": "...",
            "broker_email": "...",
            "broker_name": "...",
            "attachments": [{"filename": "...", "content": "...", "type": "..."}]
        }
        
        Returns:
            {
                "status_code": 200|400|500,
                "submission_id": "...",
                "decision": "QUOTED|DECLINED|MISSING_INFO|...",
                "message": "...",
                "data": {...}
            }
        """
        try:
            # Validate input
            if not event:
                return self._error_response(400, "Event is empty")
            
            email_subject = event.get("email_subject", "")
            email_body = event.get("email_body", "")
            broker_email = event.get("broker_email", "")
            broker_name = event.get("broker_name", "")
            attachments = event.get("attachments", [])
            
            # Validate required fields
            if not all([email_subject, email_body, broker_email]):
                return self._error_response(400, "Missing required fields: email_subject, email_body, broker_email")
            
            # Generate submission ID
            submission_id = f"SUB-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8].upper()}"
            
            logger.info(f"Received submission: {submission_id}")
            
            # Process submission through supervisor
            final_state = self.supervisor.process_submission(
                submission_id=submission_id,
                email_subject=email_subject,
                email_body=email_body,
                broker_email=broker_email,
                broker_name=broker_name,
                attachments=attachments
            )
            
            # Prepare response
            summary = self.state_manager.get_submission_summary(submission_id)
            
            return {
                "status_code": 200,
                "submission_id": submission_id,
                "decision": final_state.decision,
                "message": f"Submission processed successfully. Decision: {final_state.decision}",
                "data": summary
            }
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return self._error_response(400, str(e))
        except Exception as e:
            logger.exception("Unexpected error in submission handler")
            return self._error_response(500, f"Internal server error: {str(e)}")
    
    def _error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "status_code": status_code,
            "submission_id": None,
            "decision": None,
            "message": message,
            "data": None
        }


class OverrideHandler:
    """Handles human overrides to AI decisions"""
    
    def __init__(self):
        self.state_manager = get_state_manager()
    
    def handle_override(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle override request.
        
        Expected event structure:
        {
            "submission_id": "...",
            "user_id": "...",
            "override_decision": "QUOTED|DECLINED|MISSING_INFO",
            "override_reason": "..."
        }
        
        Returns:
            {
                "status_code": 200|400|404,
                "submission_id": "...",
                "message": "...",
                "data": {...}
            }
        """
        try:
            submission_id = event.get("submission_id")
            user_id = event.get("user_id")
            override_decision = event.get("override_decision")
            override_reason = event.get("override_reason", "")
            
            # Validate input
            if not all([submission_id, user_id, override_decision]):
                return self._error_response(
                    400, "Missing required fields: submission_id, user_id, override_decision"
                )
            
            if override_decision not in ["QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"]:
                return self._error_response(400, f"Invalid override_decision: {override_decision}")
            
            # Get state
            state = self.state_manager.get_state(submission_id)
            if not state:
                return self._error_response(404, f"Submission {submission_id} not found")
            
            logger.info(f"Applying override to {submission_id}: {state.decision} -> {override_decision}")
            
            # Apply override
            self.state_manager.apply_override(
                submission_id=submission_id,
                user_id=user_id,
                override_decision=override_decision,
                override_reason=override_reason
            )
            
            # Prepare response
            summary = self.state_manager.get_submission_summary(submission_id)
            
            return {
                "status_code": 200,
                "submission_id": submission_id,
                "message": f"Override applied successfully",
                "data": summary
            }
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return self._error_response(400, str(e))
        except Exception as e:
            logger.exception("Unexpected error in override handler")
            return self._error_response(500, f"Internal server error: {str(e)}")
    
    def _error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "status_code": status_code,
            "submission_id": None,
            "message": message,
            "data": None
        }


class QueryHandler:
    """Handles status queries"""
    
    def __init__(self):
        self.state_manager = get_state_manager()
    
    def handle_status_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query submission status.
        
        Expected event structure:
        {
            "submission_id": "..."  (optional; if not provided, return all)
        }
        """
        try:
            submission_id = event.get("submission_id")
            
            if submission_id:
                # Get single submission
                summary = self.state_manager.get_submission_summary(submission_id)
                if "error" in summary:
                    return {
                        "status_code": 404,
                        "message": f"Submission {submission_id} not found",
                        "data": None
                    }
                return {
                    "status_code": 200,
                    "message": "Submission found",
                    "data": summary
                }
            else:
                # Get all submissions
                summaries = self.state_manager.list_submissions()
                return {
                    "status_code": 200,
                    "message": f"Found {len(summaries)} submissions",
                    "data": {
                        "total": len(summaries),
                        "submissions": summaries
                    }
                }
        
        except Exception as e:
            logger.exception("Unexpected error in query handler")
            return {
                "status_code": 500,
                "message": f"Internal server error: {str(e)}",
                "data": None
            }


# FILE: lambda/submission_handler.py
"""
Lambda handler for submission processing.
Entry point for AWS Lambda invocation.
"""

import json
import logging
from src.api.handlers import SubmissionHandler

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize handler
handler = SubmissionHandler()


def lambda_handler(event, context):
    """
    AWS Lambda handler for submission requests.
    
    Event source: API Gateway or direct invocation
    
    Args:
        event: Lambda event object
        context: Lambda context object
    
    Returns:
        API Gateway formatted response
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Parse body if coming from API Gateway
    if "body" in event:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_response(400, {"error": "Invalid JSON body"})
    else:
        body = event
    
    # Process submission
    result = handler.handle_submission(body)
    
    # Format response for API Gateway
    return format_response(result.pop("status_code"), result)


def format_response(status_code: int, body: dict) -> dict:
    """Format response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


# FILE: lambda/override_handler.py
"""
Lambda handler for override requests.
"""

import json
import logging
from src.api.handlers import OverrideHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

handler = OverrideHandler()


def lambda_handler(event, context):
    """AWS Lambda handler for override requests"""
    logger.info(f"Received override event: {json.dumps(event)}")
    
    if "body" in event:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_response(400, {"error": "Invalid JSON body"})
    else:
        body = event
    
    result = handler.handle_override(body)
    return format_response(result.pop("status_code"), result)


def format_response(status_code: int, body: dict) -> dict:
    """Format response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


# FILE: lambda/query_handler.py
"""
Lambda handler for status queries.
"""

import json
import logging
from src.api.handlers import QueryHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

handler = QueryHandler()


def lambda_handler(event, context):
    """AWS Lambda handler for status queries"""
    logger.info(f"Received query event: {json.dumps(event)}")
    
    if "body" in event:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_response(400, {"error": "Invalid JSON body"})
    else:
        body = event
    
    result = handler.handle_status_query(body)
    return format_response(result.pop("status_code"), result)


def format_response(status_code: int, body: dict) -> dict:
    """Format response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }
