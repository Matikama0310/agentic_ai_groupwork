"""
Tools package: Organized by category per architecture spec.
- data_acquisition: Internal, External Bureau, Web scraping tools
- document_understanding: OCR extraction tools
- decision_logic: Guidelines validation, risk scoring, NAICS classification
- communication: Email drafting, quote generation
"""

from src.tools.data_acquisition import (
    internal_claims_history,
    fetch_external_data,
    web_research_applicant,
)
from src.tools.document_understanding import (
    extract_structured_data,
)
from src.tools.decision_logic import (
    classify_naics_code,
    validate_against_guidelines,
    calculate_risk_and_price,
    ToolResult,
    UNDERWRITING_GUIDELINES,
)
from src.tools.communication import (
    draft_missing_info_email,
    draft_decline_letter,
    draft_quote_email,
    generate_quote_pdf,
)

__all__ = [
    "internal_claims_history",
    "fetch_external_data",
    "web_research_applicant",
    "extract_structured_data",
    "classify_naics_code",
    "validate_against_guidelines",
    "calculate_risk_and_price",
    "draft_missing_info_email",
    "draft_decline_letter",
    "draft_quote_email",
    "generate_quote_pdf",
    "ToolResult",
    "UNDERWRITING_GUIDELINES",
]
