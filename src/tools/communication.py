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
from datetime import datetime

from src.tools.decision_logic import ToolResult

logger = logging.getLogger(__name__)


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
    missing_documents = missing_documents or []
    docs_text = "\n".join(f"  - {doc.replace('_', ' ').title()}" for doc in missing_documents)

    subject = f"Additional Information Needed - {applicant_name}"
    body = f"""Dear {broker_name},

Thank you for submitting the application for {applicant_name}. We are reviewing the submission and would like to move forward.

To complete our underwriting review, we require the following documents:

{docs_text}

Please submit these at your earliest convenience so we can provide a timely quote.

Best regards,
NorthStar Underwriting Team"""

    return ToolResult(True, {"subject": subject, "body": body, "to": broker_email, "ready_to_send": False})


def draft_decline_letter(
    broker_email: str,
    broker_name: str = "",
    applicant_name: str = "",
    failed_rules: Optional[List[Dict[str, str]]] = None,
) -> ToolResult:
    """
    Draft decline letter citing specific guideline violations.
    """
    failed_rules = failed_rules or []
    reasons_text = "\n".join(f"  - {r['rule_description']}: {r['reason']}" for r in failed_rules)

    subject = f"Application Decline - {applicant_name}"
    body = f"""Dear {broker_name},

Thank you for the submission for {applicant_name}. After careful review, we are unable to offer coverage at this time.

The following underwriting guidelines were not met:

{reasons_text}

We appreciate your business and encourage resubmission if circumstances change.

Best regards,
NorthStar Underwriting Team"""

    return ToolResult(True, {"subject": subject, "body": body, "to": broker_email, "ready_to_send": False})


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

    return ToolResult(True, {"subject": subject, "body": body, "to": broker_email, "ready_to_send": False})


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
    safe_name = applicant_name.replace(" ", "-").replace(".", "")
    s3_url = f"s3://northstar-quotes/{safe_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"

    return ToolResult(
        True,
        {
            "quote_pdf_s3_url": s3_url,
            "quote_amount": quote_amount,
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
