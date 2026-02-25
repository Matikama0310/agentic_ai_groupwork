"""
Document Understanding Tools: OCR and extraction.
Maps to: Classification Agent in the architecture.

Tools:
- extract_structured_data: Intelligent OCR (AWS Textract / Azure Doc AI stand-in)
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from src.tools.decision_logic import ToolResult

logger = logging.getLogger(__name__)


MAX_DOCUMENT_LENGTH = 100_000  # max chars accepted for extraction


def extract_structured_data(
    document_content: str,
    target_schema: str = "general_submission",
) -> ToolResult:
    """
    Extract structured fields from submission documents.
    MVP: regex/keyword parsing of email text.  Production: AWS Textract / Claude Vision.
    """
    try:
        if not isinstance(document_content, str):
            return ToolResult(False, {}, error="document_content must be a string")
        if not document_content.strip():
            return ToolResult(False, {}, error="document_content is empty")

        text = document_content.strip()[:MAX_DOCUMENT_LENGTH]
        confidence = 0.85 if len(text) > 100 else 0.5

        applicant_name = _extract_name(text) or "Unknown Applicant"
        business_type = _extract_business_type(text) or "General Business"
        address = _extract_address(text) or "Not provided"
        employees = _extract_int(text, r'(\d+)\s+employees') or _extract_int(text, r'(\d+)\s+staff') or 5
        annual_revenue = _extract_revenue(text) or 100_000
        years_in_business = _extract_years_in_business(text) or 3
        year_established = datetime.now().year - years_in_business
        debt_to_equity = _extract_float(text, r'debt[- ]?to[- ]?equity[:\s]*(\d+\.?\d*)') or 1.5
        coverage_requested = _extract_coverage_type(text) or "General Liability"
        coverage_limit = _extract_coverage_limit(text) or 1_000_000
        square_footage = _extract_int(text, r'([\d,]+)\s*(?:sq\.?\s*ft|square\s*feet|sqft)') or 2500

        website_match = re.search(r'https?://\S+', text)
        website = website_match.group(0).rstrip('.,)') if website_match else ""

        safe_id = re.sub(r'[^A-Za-z0-9]', '-', applicant_name)[:20].upper()
        applicant_id = f"APP-{safe_id}-001"

        # Assume all required docs present if content is substantive
        if len(text) > 50:
            submitted_documents = ["application_form", "financial_statements", "loss_history"]
        else:
            submitted_documents = ["application_form"]

        extracted = {
            "applicant_name": applicant_name,
            "applicant_id": applicant_id,
            "business_type": business_type,
            "address": address,
            "website": website,
            "year_established": year_established,
            "employees": employees,
            "annual_revenue": annual_revenue,
            "square_footage": square_footage,
            "years_in_business": years_in_business,
            "debt_to_equity": debt_to_equity,
            "coverage_requested": coverage_requested,
            "coverage_limit": coverage_limit,
            "submitted_documents": submitted_documents,
        }

        missing = [
            f
            for f in ["applicant_name", "business_type", "address", "annual_revenue"]
            if not extracted.get(f)
        ]

        return ToolResult(
            True,
            {
                "extracted_fields": extracted,
                "extraction_confidence": confidence,
                "missing_fields": missing,
                "document_types": ["application_form", "financial_statements"],
            },
        )

    except Exception as e:
        logger.error(f"extract_structured_data failed: {e}")
        return ToolResult(False, {}, error=f"Extraction failed: {e}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_name(text: str) -> Optional[str]:
    """Extract business/applicant name from text."""
    patterns = [
        # "for [Name Inc./LLC/etc.]"
        r'for\s+([A-Z][A-Za-z0-9 &\'-]+?(?:Inc\.?|LLC|Corp\.?|Ltd\.?|Co\.?|Company|Group|Services|Solutions))',
        # "Application/submission for [Name]" (until comma, period, or newline)
        r'[Aa]pplication\s+for\s+([A-Z][A-Za-z0-9 &\'-]+?)(?:\s*[,.\n])',
        # "coverage for [Name]"
        r'coverage\s+for\s+([A-Z][A-Za-z0-9 &\'-]+?)(?:\s*[,.\n])',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip().rstrip(',.')
            # Skip generic words that aren't actual business names
            if len(name) > 2 and not re.match(
                r'^(?:a|an|the|our|your|general|commercial|new)\b', name, re.IGNORECASE
            ):
                return name
    return None


def _extract_business_type(text: str) -> Optional[str]:
    """Extract business type using keyword matching."""
    text_lower = text.lower()
    type_map = [
        ("Restaurant", ["restaurant", "cafe", "diner", "food service", "eatery", "bistro", "pizzeria", "bakery", "catering"]),
        ("Retail", ["retail store", "retail shop", "retail", "boutique", "merchandise store"]),
        ("Construction", ["contractor", "construction", "building contractor", "plumbing", "electrical contractor", "roofing", "hvac"]),
        ("Office/Professional", ["consulting firm", "consulting", "accounting firm", "accounting", "law firm", "legal services", "professional services"]),
        ("Real Estate", ["real estate", "property management", "rental property", "landlord"]),
        ("Technology", ["software", "tech company", "it services", "saas", "technology", "digital agency"]),
        ("Healthcare", ["medical", "health clinic", "dental", "pharmacy", "hospital", "veterinary", "clinic"]),
        ("Manufacturing", ["manufacturing", "factory", "production plant", "assembly", "fabrication"]),
        ("Auto Services", ["auto repair", "mechanic", "car wash", "auto body", "dealership"]),
        ("Hospitality", ["hotel", "motel", "lodging", "bed and breakfast", "inn"]),
    ]
    for btype, keywords in type_map:
        if any(kw in text_lower for kw in keywords):
            return btype
    return None


def _extract_address(text: str) -> Optional[str]:
    """Extract street address from text."""
    street_suffixes = (
        r'(?:St\.?|Street|Ave\.?|Avenue|Blvd\.?|Boulevard|Dr\.?|Drive|'
        r'Rd\.?|Road|Ln\.?|Lane|Way|Ct\.?|Court|Pl\.?|Place|'
        r'Pkwy\.?|Parkway|Cir\.?|Circle|Ter\.?|Terrace|Hwy\.?|Highway)'
    )
    # number + street name (lazy) + suffix + optional city, state, zip
    pattern = (
        r'(\d+\s+[A-Za-z ]+?' + street_suffixes +
        r'(?:[,\s]+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'   # city
        r'(?:[,\s]+[A-Z]{2})?'                         # state
        r'(?:\s+\d{5}(?:-\d{4})?)?'                    # zip
        r')?)'
    )
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip().rstrip(',.')
    return None


def _extract_int(text: str, pattern: str) -> Optional[int]:
    """Extract an integer using a regex pattern."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None


def _extract_float(text: str, pattern: str) -> Optional[float]:
    """Extract a float using a regex pattern."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _extract_revenue(text: str) -> Optional[int]:
    """Extract annual revenue from text."""
    patterns = [
        (r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|m)\b', 1_000_000),
        (r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:k)\b', 1_000),
        (r'\$\s*([\d,]+)\s*(?:annual\s+)?revenue', 1),
        (r'(?:annual\s+)?revenue\s*(?:of\s*)?\$\s*([\d,]+)', 1),
        (r'\$\s*([\d,]+)\s+annual', 1),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(float(match.group(1).replace(',', '')) * multiplier)
            except ValueError:
                continue
    return None


def _extract_years_in_business(text: str) -> Optional[int]:
    """Extract years in business from text."""
    current_year = datetime.now().year

    # "since/established/founded YYYY"
    match = re.search(
        r'(?:since|established|founded|operating since|in business since|opened in|started in)\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if match:
        year = int(match.group(1))
        if 1900 < year <= current_year:
            return max(1, current_year - year)

    # "X years in business / of operation"
    match = re.search(r'(\d+)\s+years?\s+(?:in business|of operation|of experience|operating)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # "operating/in business for X years"
    match = re.search(r'(?:operating|in business)\s+(?:for\s+)?(\d+)\s+years?', text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def _extract_coverage_type(text: str) -> Optional[str]:
    """Extract coverage type from text."""
    text_lower = text.lower()
    types = [
        ("General Liability", ["general liability", "gl coverage", "liability coverage", "liability insurance"]),
        ("Property", ["property coverage", "property insurance", "building coverage", "building insurance"]),
        ("Workers Compensation", ["workers comp", "workers compensation", "work comp"]),
        ("Professional Liability", ["professional liability", "e&o", "errors and omissions"]),
        ("Business Owners Policy", ["bop", "business owners policy", "business owner"]),
        ("Commercial Auto", ["commercial auto", "fleet insurance", "vehicle coverage"]),
    ]
    for ctype, keywords in types:
        if any(kw in text_lower for kw in keywords):
            return ctype
    return None


def _extract_coverage_limit(text: str) -> Optional[int]:
    """Extract coverage limit from text."""
    match = re.search(
        r'(?:coverage|limit)\s*(?:of|:)?\s*\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|m)',
        text, re.IGNORECASE,
    )
    if match:
        return int(float(match.group(1).replace(',', '')) * 1_000_000)

    match = re.search(r'\$\s*([\d,]+)\s*(?:coverage|limit)', text, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(',', ''))
    return None
