"""
Communication Tools: Broker Liaison Agent capabilities.
Maps to: Broker Liaison Agent in the architecture.

Tools:
- draft_missing_info_email: Request missing documents from broker
- draft_decline_letter: Decline with specific guideline citations
- draft_quote_email: Send quote with terms
- generate_quote_pdf: Create quote PDF package
"""

from typing import Dict, Any, List, Optional
import logging
import re
from datetime import datetime, UTC

from src.tools.decision_logic import ToolResult

logger = logging.getLogger(__name__)

# Basic email format check (RFC 5322 simplified)
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validate_email(email: str) -> bool:
    """Return True if email looks structurally valid."""
    return bool(isinstance(email, str) and _EMAIL_RE.match(email.strip()))


def _sanitize(text: str, max_len: int = 200) -> str:
    """Strip control characters and truncate."""
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return cleaned[:max_len]


def draft_missing_info_email(
    broker_email: str,
    broker_name: str = "",
    applicant_name: str = "",
    missing_documents: Optional[List[str]] = None,
) -> ToolResult:
    """
    Draft email requesting missing documentation.
    Triggered by Underwriting Analyst Agent when critical docs are absent.
    """
    try:
        if not _validate_email(broker_email):
            return ToolResult(False, {}, error=f"Invalid broker email: {broker_email!r}")

        broker_name = _sanitize(broker_name) or "Broker"
        applicant_name = _sanitize(applicant_name) or "the applicant"
        missing_documents = missing_documents if isinstance(missing_documents, list) else []

        if not missing_documents:
            return ToolResult(False, {}, error="missing_documents list is empty")

        docs_text = "\n".join(f"  - {doc.replace('_', ' ').title()}" for doc in missing_documents)

        subject = f"Additional Information Needed - {applicant_name}"
        body = f"""Dear {broker_name},

Thank you for submitting the application for {applicant_name}. We are reviewing the submission and would like to move forward.

To complete our underwriting review, we require the following documents:

{docs_text}

Please submit these at your earliest convenience so we can provide a timely quote.

Best regards,
NorthStar Underwriting Team"""

        return ToolResult(True, {"subject": subject, "body": body, "to": broker_email.strip(), "ready_to_send": False})

    except Exception as e:
        logger.error(f"draft_missing_info_email failed: {e}")
        return ToolResult(False, {}, error=f"Email draft failed: {e}")


def draft_decline_letter(
    broker_email: str,
    broker_name: str = "",
    applicant_name: str = "",
    failed_rules: Optional[List[Dict[str, str]]] = None,
) -> ToolResult:
    """
    Draft decline letter citing specific guideline violations.
    """
    try:
        if not _validate_email(broker_email):
            return ToolResult(False, {}, error=f"Invalid broker email: {broker_email!r}")

        broker_name = _sanitize(broker_name) or "Broker"
        applicant_name = _sanitize(applicant_name) or "the applicant"
        failed_rules = failed_rules if isinstance(failed_rules, list) else []

        reasons_text = "\n".join(
            f"  - {_sanitize(r.get('rule_description', 'Unknown rule'))}: {_sanitize(r.get('reason', 'Not specified'))}"
            for r in failed_rules
            if isinstance(r, dict)
        )
        if not reasons_text:
            reasons_text = "  - Underwriting guidelines not met."

        subject = f"Application Decline - {applicant_name}"
        body = f"""Dear {broker_name},

Thank you for the submission for {applicant_name}. After careful review, we are unable to offer coverage at this time.

The following underwriting guidelines were not met:

{reasons_text}

We appreciate your business and encourage resubmission if circumstances change.

Best regards,
NorthStar Underwriting Team"""

        return ToolResult(True, {"subject": subject, "body": body, "to": broker_email.strip(), "ready_to_send": False})

    except Exception as e:
        logger.error(f"draft_decline_letter failed: {e}")
        return ToolResult(False, {}, error=f"Decline letter draft failed: {e}")


def draft_quote_email(
    broker_email: str,
    broker_name: str = "",
    applicant_name: str = "",
    quote_amount: float = 0,
    policy_term: str = "1 year",
    quote_pdf_url: str = "",
) -> ToolResult:
    """
    Draft email with quote and policy terms.
    """
    try:
        if not _validate_email(broker_email):
            return ToolResult(False, {}, error=f"Invalid broker email: {broker_email!r}")
        if not isinstance(quote_amount, (int, float)) or quote_amount < 0:
            return ToolResult(False, {}, error=f"Invalid quote_amount: {quote_amount!r}")

        broker_name = _sanitize(broker_name) or "Broker"
        applicant_name = _sanitize(applicant_name) or "the applicant"
        policy_term = _sanitize(policy_term) or "1 year"

        subject = f"Quote Ready - {applicant_name}"
        body = f"""Dear {broker_name},

We have completed our underwriting review for {applicant_name} and are pleased to offer coverage.

Quote Summary:
  Annual Premium: ${quote_amount:,.2f}
  Policy Term: {policy_term}
  Quote Document: {quote_pdf_url}

This quote is valid for 30 days. Please contact us with any questions.

Best regards,
NorthStar Underwriting Team"""

        return ToolResult(True, {"subject": subject, "body": body, "to": broker_email.strip(), "ready_to_send": False})

    except Exception as e:
        logger.error(f"draft_quote_email failed: {e}")
        return ToolResult(False, {}, error=f"Quote email draft failed: {e}")


def generate_quote_pdf(
    extracted_data: Dict[str, Any],
    risk_metrics: Dict[str, Any],
    quote_amount: float,
    applicant_name: str = "",
) -> ToolResult:
    """
    Generate quote PDF document.
    MVP: returns placeholder URL.  Production: ReportLab / wkhtmltopdf.
    """
    try:
        if not isinstance(extracted_data, dict):
            return ToolResult(False, {}, error="extracted_data must be a dict")
        if not isinstance(risk_metrics, dict):
            return ToolResult(False, {}, error="risk_metrics must be a dict")
        if not isinstance(quote_amount, (int, float)) or quote_amount < 0:
            return ToolResult(False, {}, error=f"Invalid quote_amount: {quote_amount!r}")

        # Sanitize name for S3 key (only allow alphanumeric and hyphens)
        safe_name = re.sub(r'[^A-Za-z0-9-]', '-', applicant_name)[:60] or "unknown"
        safe_name = re.sub(r'-+', '-', safe_name).strip('-')
        s3_url = f"s3://northstar-quotes/{safe_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"

        return ToolResult(
            True,
            {
                "quote_pdf_s3_url": s3_url,
                "quote_amount": quote_amount,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"generate_quote_pdf failed: {e}")
        return ToolResult(False, {}, error=f"PDF generation failed: {e}")
