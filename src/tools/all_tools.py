# FILE: src/tools/decision_tools.py
"""
Decision & Logic Tools: Rule validation, risk scoring, pricing.
These are the "brain" of the underwriting logic.
"""

from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GuidelinesNotFoundError(Exception):
    """Raised when guidelines config is missing"""
    pass


class ToolResult:
    """Standard result object for all tools"""
    def __init__(self, success: bool, data: Dict[str, Any], error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp
        }


# Mock guidelines (in real system, load from config/guidelines.json via RAG)
MOCK_GUIDELINES = {
    "rules": [
        {
            "rule_id": "R001",
            "name": "Minimum Credit Score",
            "description": "Applicant must have credit score >= 500",
            "severity": "hard",
            "condition": "credit_score",
            "threshold": 500,
            "comparison": ">="
        },
        {
            "rule_id": "R002",
            "name": "Maximum Loss Ratio",
            "description": "Historical loss ratio must be < 80%",
            "severity": "hard",
            "condition": "loss_ratio",
            "threshold": 0.80,
            "comparison": "<"
        },
        {
            "rule_id": "R003",
            "name": "Debt to Equity",
            "description": "Debt to equity ratio must be < 3.0",
            "severity": "hard",
            "condition": "debt_to_equity",
            "threshold": 3.0,
            "comparison": "<"
        },
        {
            "rule_id": "R004",
            "name": "Minimum Years in Business",
            "description": "Must have been in business >= 2 years",
            "severity": "hard",
            "condition": "years_in_business",
            "threshold": 2,
            "comparison": ">="
        }
    ],
    "required_documents": [
        "application_form",
        "financial_statements",
        "loss_history"
    ]
}


def classify_naics_code(business_description: str, business_name: str = "") -> ToolResult:
    """
    Classify business into NAICS code.
    MVP: Uses simple keyword matching; in production, use LLM or lookup service.
    
    Args:
        business_description: Description of business
        business_name: Name of business
    
    Returns:
        ToolResult with naics_code, industry, confidence
    """
    # Mock NAICS classification based on keywords
    keywords_map = {
        ("restaurant", "cafe", "diner"): ("722110", "Food Service", 0.85),
        ("retail", "store", "shop"): ("452000", "General Merchandise Retail", 0.80),
        ("contractor", "construction"): ("238000", "Specialty Trade Contractors", 0.85),
        ("office", "administrative"): ("561000", "Administrative Services", 0.75),
        ("property", "real estate"): ("531000", "Real Estate", 0.80),
    }
    
    description_lower = f"{business_description} {business_name}".lower()
    
    # Simple keyword matching
    for keywords, (naics, industry, confidence) in keywords_map.items():
        if any(kw in description_lower for kw in keywords):
            return ToolResult(
                success=True,
                data={
                    "naics_code": naics,
                    "industry": industry,
                    "confidence": confidence
                }
            )
    
    # Default fallback
    return ToolResult(
        success=True,
        data={
            "naics_code": "999999",
            "industry": "Unknown",
            "confidence": 0.5
        }
    )


def validate_against_guidelines(extracted_data: Dict[str, Any], 
                               enriched_data: Optional[Dict[str, Any]] = None,
                               web_data: Optional[Dict[str, Any]] = None,
                               loss_history: Optional[Dict[str, Any]] = None) -> ToolResult:
    """
    Validate submission against hard-coded guidelines.
    This is the core "gate keeper" function.
    
    Args:
        extracted_data: Result from OCR/extraction
        enriched_data: Result from external APIs
        web_data: Result from web research
        loss_history: Prior loss data
    
    Returns:
        ToolResult with passes_guidelines, failed_rules, missing_critical_docs
    """
    if not MOCK_GUIDELINES:
        raise GuidelinesNotFoundError("Guidelines config not found")
    
    failed_rules = []
    missing_docs = []
    
    # Check for required documents
    submitted_docs = extracted_data.get("submitted_documents", [])
    for req_doc in MOCK_GUIDELINES["required_documents"]:
        if req_doc not in submitted_docs:
            missing_docs.append(req_doc)
    
    # If critical documents missing, fail immediately
    if missing_docs:
        return ToolResult(
            success=True,
            data={
                "passes_guidelines": False,
                "failed_rules": [],
                "missing_critical_docs": missing_docs
            }
        )
    
    # Check hard rules
    enriched_data = enriched_data or {}
    loss_history = loss_history or {}
    
    credit_score = enriched_data.get("credit_score", 0)
    loss_ratio = loss_history.get("loss_ratio", 0)
    debt_to_equity = extracted_data.get("debt_to_equity", 0)
    years_in_business = extracted_data.get("years_in_business", 0)
    
    for rule in MOCK_GUIDELINES["rules"]:
        rule_id = rule["rule_id"]
        condition = rule["condition"]
        threshold = rule["threshold"]
        comparison = rule["comparison"]
        
        # Get value based on condition
        if condition == "credit_score":
            value = credit_score
        elif condition == "loss_ratio":
            value = loss_ratio
        elif condition == "debt_to_equity":
            value = debt_to_equity
        elif condition == "years_in_business":
            value = years_in_business
        else:
            continue
        
        # Evaluate rule
        passes = False
        if comparison == ">=":
            passes = value >= threshold
        elif comparison == "<=":
            passes = value <= threshold
        elif comparison == ">":
            passes = value > threshold
        elif comparison == "<":
            passes = value < threshold
        elif comparison == "==":
            passes = value == threshold
        
        if not passes:
            failed_rules.append({
                "rule_id": rule_id,
                "rule_description": rule["name"],
                "reason": f"{condition}={value} does not meet {comparison}{threshold}"
            })
    
    passes_guidelines = len(failed_rules) == 0
    
    return ToolResult(
        success=True,
        data={
            "passes_guidelines": passes_guidelines,
            "failed_rules": failed_rules,
            "missing_critical_docs": missing_docs
        }
    )


def calculate_risk_and_price(extracted_data: Dict[str, Any],
                            enriched_data: Optional[Dict[str, Any]] = None,
                            loss_history: Optional[Dict[str, Any]] = None) -> ToolResult:
    """
    Calculate risk score and annual premium.
    Uses formula: Base Premium * Credit Modifier * Loss History Modifier * Industry Modifier
    
    Args:
        extracted_data: Extracted submission data
        enriched_data: External enrichment data
        loss_history: Prior losses
    
    Returns:
        ToolResult with risk_score, loss_ratio, debt_to_equity, annual_premium, pricing_rationale
    """
    enriched_data = enriched_data or {}
    loss_history = loss_history or {}
    
    # Extract values with defaults
    annual_revenue = extracted_data.get("annual_revenue", 100000)
    employees = extracted_data.get("employees", 5)
    credit_score = enriched_data.get("credit_score", 650)
    crime_score = enriched_data.get("property_risk", {}).get("crime_score", 50)
    total_losses = loss_history.get("total_losses", 0)
    loss_frequency = loss_history.get("loss_frequency", 0)
    
    # Calculate metrics
    loss_ratio = (total_losses / annual_revenue) if annual_revenue > 0 else 0
    debt_to_equity = extracted_data.get("debt_to_equity", 1.0)
    risk_score = min(100, max(0, 50 + (loss_ratio * 100) + (crime_score * 0.2)))
    
    # Pricing calculation
    base_premium = annual_revenue * 0.005  # 0.5% of revenue
    
    # Credit modifier (650-750 = 1.0, below = higher)
    if credit_score < 600:
        credit_modifier = 1.5
    elif credit_score < 700:
        credit_modifier = 1.2
    else:
        credit_modifier = 1.0
    
    # Loss history modifier
    if loss_ratio > 0.5:
        loss_modifier = 2.0
    elif loss_ratio > 0.3:
        loss_modifier = 1.5
    elif loss_ratio > 0.1:
        loss_modifier = 1.2
    else:
        loss_modifier = 1.0
    
    # Industry/size modifier
    size_modifier = 1.0 + (employees / 100)  # Larger = higher premium
    
    annual_premium = base_premium * credit_modifier * loss_modifier * size_modifier
    
    rationale = (
        f"Base premium ${base_premium:.2f} × "
        f"Credit {credit_modifier:.2f} × "
        f"Loss {loss_modifier:.2f} × "
        f"Size {size_modifier:.2f} = "
        f"${annual_premium:.2f}"
    )
    
    return ToolResult(
        success=True,
        data={
            "risk_score": round(risk_score, 2),
            "loss_ratio": round(loss_ratio, 4),
            "debt_to_equity": round(debt_to_equity, 2),
            "annual_premium": round(annual_premium, 2),
            "pricing_rationale": rationale
        }
    )


def calculate_loss_ratio(total_losses: float, annual_revenue: float) -> float:
    """Helper function to calculate loss ratio"""
    if annual_revenue <= 0:
        return 0.0
    return total_losses / annual_revenue


# FILE: src/tools/document_tools.py
"""
Document Understanding Tools: OCR, extraction, image analysis.
"""


def extract_structured_data(document_content: str, 
                           target_schema: str = "general_submission") -> ToolResult:
    """
    Extract structured fields from document (mock OCR + schema mapping).
    
    Args:
        document_content: Raw text or base64-encoded image
        target_schema: Type of form (general_submission, property_form, financial_form)
    
    Returns:
        ToolResult with extracted_fields, extraction_confidence, missing_fields
    """
    # Mock extraction logic
    # In production: use AWS Textract or Claude's vision capabilities
    
    # Simple heuristic: if document is long and contains key words, confidence is higher
    confidence = 0.75 if len(document_content) > 100 else 0.5
    
    extracted = {
        "applicant_name": "Acme Restaurant Inc.",
        "business_type": "Restaurant",
        "address": "123 Main St, Springfield, IL 62701",
        "year_established": 2015,
        "employees": 12,
        "annual_revenue": 500000,
        "square_footage": 2500,
        "years_in_business": 9,
        "debt_to_equity": 1.5,
        "submitted_documents": ["application_form", "financial_statements", "loss_history"]
    }
    
    missing = []
    for field in ["applicant_name", "business_type", "address", "annual_revenue"]:
        if field not in extracted or not extracted[field]:
            missing.append(field)
    
    return ToolResult(
        success=True,
        data={
            "extracted_fields": extracted,
            "extraction_confidence": confidence,
            "missing_fields": missing
        }
    )


def analyze_image_hazards(image_base64: str, hazard_types: List[str] = None) -> ToolResult:
    """
    Analyze inspection images for hazards (mock vision analysis).
    
    Args:
        image_base64: Base64-encoded image
        hazard_types: Types of hazards to look for
    
    Returns:
        ToolResult with hazards_detected, analysis_confidence
    """
    hazard_types = hazard_types or ["electrical", "fire", "structural"]
    
    # Mock hazard detection
    hazards = [
        {
            "type": "electrical",
            "description": "Outdated knob-and-tube wiring detected",
            "severity": "high"
        }
    ] if len(image_base64) > 100 else []
    
    return ToolResult(
        success=True,
        data={
            "hazards_detected": hazards,
            "analysis_confidence": 0.85 if hazards else 0.95
        }
    )


# FILE: src/tools/data_tools.py
"""
Data Acquisition Tools: Fetch from internal/external data sources.
"""


def internal_claims_history(applicant_id: str, applicant_name: str = "",
                           date_range_years: int = 5) -> ToolResult:
    """
    Fetch prior loss history from internal claims systems (mock).
    
    Args:
        applicant_id: Internal ID
        applicant_name: Business name
        date_range_years: Years of history to retrieve
    
    Returns:
        ToolResult with loss_runs, total_losses, loss_frequency, policy_history
    """
    # Mock data
    loss_runs = [
        {
            "claim_id": "CLM-2022-001",
            "loss_date": "2022-06-15",
            "amount": 5000,
            "description": "Water damage from burst pipe"
        },
        {
            "claim_id": "CLM-2020-001",
            "loss_date": "2020-11-20",
            "amount": 3000,
            "description": "Equipment damage"
        }
    ]
    
    return ToolResult(
        success=True,
        data={
            "loss_runs": loss_runs,
            "total_losses": 8000,
            "loss_frequency": 2,
            "policy_history": ["POL-2021-001", "POL-2022-001"]
        }
    )


def fetch_external_data(applicant_name: str, applicant_address: str = "",
                       data_sources: List[str] = None) -> ToolResult:
    """
    Fetch external risk data (mock D&B, HazardHub, Verisk).
    
    Args:
        applicant_name: Business name
        applicant_address: Full address
        data_sources: API sources to query
    
    Returns:
        ToolResult with credit_score, financial_health, property_risk
    """
    data_sources = data_sources or ["dun_bradstreet", "hazardhub"]
    
    # Mock data
    return ToolResult(
        success=True,
        data={
            "credit_score": 720,
            "financial_health": "good",
            "property_risk": {
                "flood_zone": "X (minimal)",
                "distance_to_fire_station_miles": 2.5,
                "crime_score": 35
            }
        }
    )


def web_research_applicant(applicant_name: str, applicant_website: str = "") -> ToolResult:
    """
    Research applicant's web presence for risk flags (mock web scraping).
    
    Args:
        applicant_name: Business name
        applicant_website: Website URL
    
    Returns:
        ToolResult with website_verified, business_operations, risk_flags, reviews_summary
    """
    # Mock web research
    return ToolResult(
        success=True,
        data={
            "website_verified": True,
            "business_operations": "Full-service restaurant with dine-in and takeout",
            "risk_flags": [],
            "public_reviews_summary": "Positive reviews; 4.5/5 stars on Google"
        }
    )


# FILE: src/tools/comms_tools.py
"""
Communication Tools: Draft emails and letters for brokers.
"""


def draft_missing_info_email(broker_email: str, broker_name: str = "",
                            applicant_name: str = "",
                            missing_documents: List[str] = None) -> ToolResult:
    """
    Draft email requesting missing documentation.
    
    Args:
        broker_email: Broker's email
        broker_name: Broker's name
        applicant_name: Applicant name
        missing_documents: List of missing docs
    
    Returns:
        ToolResult with subject, body, ready_to_send
    """
    missing_documents = missing_documents or []
    
    docs_text = "\n".join([f"  • {doc}" for doc in missing_documents])
    
    subject = f"Additional Information Needed - {applicant_name}"
    body = f"""Dear {broker_name},

Thank you for submitting the application for {applicant_name}. We are pleased to move forward with the underwriting process.

To complete our review, we need the following additional documents:

{docs_text}

Please submit these documents at your earliest convenience so we can provide a quote.

Best regards,
Underwriting Team"""
    
    return ToolResult(
        success=True,
        data={
            "subject": subject,
            "body": body,
            "ready_to_send": False  # MVP: require human review
        }
    )


def draft_decline_letter(broker_email: str, broker_name: str = "",
                        applicant_name: str = "",
                        failed_rules: List[Dict[str, str]] = None) -> ToolResult:
    """
    Draft decline letter citing specific guideline violations.
    
    Args:
        broker_email: Broker's email
        broker_name: Broker's name
        applicant_name: Applicant name
        failed_rules: List of {rule_id, rule_description, reason}
    
    Returns:
        ToolResult with subject, body, ready_to_send
    """
    failed_rules = failed_rules or []
    
    reasons_text = "\n".join([f"  • {rule['rule_description']}: {rule['reason']}" 
                             for rule in failed_rules])
    
    subject = f"Application Decline - {applicant_name}"
    body = f"""Dear {broker_name},

Thank you for your interest in coverage for {applicant_name}. After careful review of the submission, we are unable to offer coverage at this time.

The following underwriting guidelines were not met:

{reasons_text}

We appreciate your business and encourage you to resubmit if circumstances change.

Best regards,
Underwriting Team"""
    
    return ToolResult(
        success=True,
        data={
            "subject": subject,
            "body": body,
            "ready_to_send": False  # MVP: require human review
        }
    )


def draft_quote_email(broker_email: str, broker_name: str = "",
                     applicant_name: str = "",
                     quote_amount: float = 0,
                     policy_term: str = "1 year",
                     quote_pdf_url: str = "") -> ToolResult:
    """
    Draft email with quote and policy terms.
    
    Args:
        broker_email: Broker's email
        broker_name: Broker's name
        applicant_name: Applicant name
        quote_amount: Annual premium
        policy_term: Term of policy
        quote_pdf_url: URL to quote PDF
    
    Returns:
        ToolResult with subject, body, ready_to_send
    """
    subject = f"Quote Ready - {applicant_name}"
    body = f"""Dear {broker_name},

Great news! We have completed our underwriting review for {applicant_name} and are pleased to offer coverage.

Quote Summary:
  Annual Premium: ${quote_amount:,.2f}
  Policy Term: {policy_term}
  
Please find the complete quote package attached.

Best regards,
Underwriting Team"""
    
    return ToolResult(
        success=True,
        data={
            "subject": subject,
            "body": body,
            "ready_to_send": False  # MVP: require human review
        }
    )


# FILE: src/tools/output_tools.py
"""
Output Generation Tools: Generate quotes, PDFs.
"""


def generate_quote_pdf(extracted_data: Dict[str, Any],
                      risk_metrics: Dict[str, Any],
                      quote_amount: float,
                      applicant_name: str = "") -> ToolResult:
    """
    Generate quote PDF document (mock for MVP).
    
    Args:
        extracted_data: Extracted submission data
        risk_metrics: Risk assessment results
        quote_amount: Annual premium
        applicant_name: Business name
    
    Returns:
        ToolResult with quote_pdf_s3_url
    """
    # Mock: return placeholder S3 URL
    # In production: use ReportLab or similar to generate actual PDF
    
    s3_url = f"s3://quotes-bucket/quote-{applicant_name.replace(' ', '-')}-{datetime.utcnow().timestamp()}.pdf"
    
    return ToolResult(
        success=True,
        data={
            "quote_pdf_s3_url": s3_url,
            "quote_amount": quote_amount,
            "generated_at": datetime.utcnow().isoformat()
        }
    )
