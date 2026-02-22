"""
DEPRECATED: This file is kept for backward compatibility only.
All tools have been split into dedicated modules:

  - src/tools/decision_logic.py        (classify_naics_code, validate_against_guidelines, calculate_risk_and_price)
  - src/tools/document_understanding.py (extract_structured_data, analyze_image_hazards)
  - src/tools/data_acquisition.py       (internal_claims_history, fetch_external_data, web_research_applicant)
  - src/tools/communication.py          (draft_missing_info_email, draft_decline_letter, draft_quote_email, generate_quote_pdf)

Import from the specific modules or from src.tools directly:
    from src.tools import classify_naics_code, extract_structured_data
"""

# Re-export everything from new modules for backward compatibility
from src.tools.decision_logic import (
    ToolResult,
    classify_naics_code,
    validate_against_guidelines,
    calculate_risk_and_price,
    UNDERWRITING_GUIDELINES,
)
from src.tools.document_understanding import (
    extract_structured_data,
    analyze_image_hazards,
)
from src.tools.data_acquisition import (
    internal_claims_history,
    fetch_external_data,
    web_research_applicant,
)
from src.tools.communication import (
    draft_missing_info_email,
    draft_decline_letter,
    draft_quote_email,
    generate_quote_pdf,
)

__all__ = [
    "ToolResult",
    "classify_naics_code",
    "validate_against_guidelines",
    "calculate_risk_and_price",
    "UNDERWRITING_GUIDELINES",
    "extract_structured_data",
    "analyze_image_hazards",
    "internal_claims_history",
    "fetch_external_data",
    "web_research_applicant",
    "draft_missing_info_email",
    "draft_decline_letter",
    "draft_quote_email",
    "generate_quote_pdf",
]
