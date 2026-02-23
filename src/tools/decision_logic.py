"""
Decision & Logic Tools: Rule validation, risk scoring, pricing.
Maps to: Underwriting Analyst Agent in the architecture.

Tools:
- classify_naics_code: NAICS/SIC classification
- validate_against_guidelines: Hard constraint validation (Rule Engine)
- calculate_risk_and_price: Risk scoring + premium calculation (Code Interpreter)
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolResult:
    """Standard result object for all tools."""

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
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Underwriting Guidelines (RAG Knowledge Base stand-in for MVP)
# In production: loaded from a vector DB / RAG retrieval pipeline
# ---------------------------------------------------------------------------
UNDERWRITING_GUIDELINES = {
    "rules": [
        {
            "rule_id": "R001",
            "name": "Minimum Credit Score",
            "description": "Applicant must have credit score >= 500",
            "severity": "hard",
            "condition": "credit_score",
            "threshold": 500,
            "comparison": ">=",
        },
        {
            "rule_id": "R002",
            "name": "Maximum Loss Ratio",
            "description": "Historical loss ratio must be < 80%",
            "severity": "hard",
            "condition": "loss_ratio",
            "threshold": 0.80,
            "comparison": "<",
        },
        {
            "rule_id": "R003",
            "name": "Debt to Equity",
            "description": "Debt to equity ratio must be < 3.0",
            "severity": "hard",
            "condition": "debt_to_equity",
            "threshold": 3.0,
            "comparison": "<",
        },
        {
            "rule_id": "R004",
            "name": "Minimum Years in Business",
            "description": "Must have been in business >= 2 years",
            "severity": "hard",
            "condition": "years_in_business",
            "threshold": 2,
            "comparison": ">=",
        },
    ],
    "required_documents": [
        "application_form",
        "financial_statements",
        "loss_history",
    ],
}


# ---------------------------------------------------------------------------
# Classification Agent Tool
# ---------------------------------------------------------------------------
def classify_naics_code(business_description: str, business_name: str = "") -> ToolResult:
    """
    Classify business into NAICS code.
    MVP: keyword matching.  Production: LLM + lookup service.
    """
    keywords_map = {
        ("restaurant", "cafe", "diner", "food"): ("722110", "Food Service", 0.85),
        ("retail", "store", "shop"): ("452000", "General Merchandise Retail", 0.80),
        ("contractor", "construction", "building"): ("238000", "Specialty Trade Contractors", 0.85),
        ("office", "administrative", "consulting"): ("561000", "Administrative Services", 0.75),
        ("property", "real estate", "rental"): ("531000", "Real Estate", 0.80),
        ("tech", "software", "it"): ("541500", "Computer Systems Design", 0.80),
        ("medical", "health", "clinic", "doctor"): ("621000", "Health Care", 0.85),
        ("manufacturing", "factory", "plant"): ("332000", "Manufacturing", 0.80),
    }

    text = f"{business_description} {business_name}".lower()

    for keywords, (naics, industry, confidence) in keywords_map.items():
        if any(kw in text for kw in keywords):
            return ToolResult(True, {"naics_code": naics, "industry": industry, "confidence": confidence})

    return ToolResult(True, {"naics_code": "999999", "industry": "Unknown", "confidence": 0.5})


# ---------------------------------------------------------------------------
# Underwriting Analyst Agent Tool  (Rule Engine Validator)
# ---------------------------------------------------------------------------
def validate_against_guidelines(
    extracted_data: Dict[str, Any],
    enriched_data: Optional[Dict[str, Any]] = None,
    web_data: Optional[Dict[str, Any]] = None,
    loss_history: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Validate submission against hard-coded underwriting guidelines.
    Returns pass/fail + specific failed rules + missing documents.
    """
    failed_rules: List[Dict[str, str]] = []
    missing_docs: List[str] = []

    # 1. Check required documents
    submitted_docs = extracted_data.get("submitted_documents", [])
    for req_doc in UNDERWRITING_GUIDELINES["required_documents"]:
        if req_doc not in submitted_docs:
            missing_docs.append(req_doc)

    if missing_docs:
        return ToolResult(
            True,
            {"passes_guidelines": False, "failed_rules": [], "missing_critical_docs": missing_docs},
        )

    # 2. Check hard rules
    enriched_data = enriched_data or {}
    loss_history = loss_history or {}

    values = {
        "credit_score": enriched_data.get("credit_score", 0),
        "loss_ratio": loss_history.get("loss_ratio", 0),
        "debt_to_equity": extracted_data.get("debt_to_equity", 0),
        "years_in_business": extracted_data.get("years_in_business", 0),
    }

    comparisons = {
        ">=": lambda v, t: v >= t,
        "<=": lambda v, t: v <= t,
        ">": lambda v, t: v > t,
        "<": lambda v, t: v < t,
        "==": lambda v, t: v == t,
    }

    for rule in UNDERWRITING_GUIDELINES["rules"]:
        cond = rule["condition"]
        value = values.get(cond, 0)
        cmp_fn = comparisons.get(rule["comparison"])
        if cmp_fn and not cmp_fn(value, rule["threshold"]):
            failed_rules.append(
                {
                    "rule_id": rule["rule_id"],
                    "rule_description": rule["name"],
                    "reason": f"{cond}={value} does not meet {rule['comparison']}{rule['threshold']}",
                }
            )

    return ToolResult(
        True,
        {
            "passes_guidelines": len(failed_rules) == 0,
            "failed_rules": failed_rules,
            "missing_critical_docs": [],
        },
    )


# ---------------------------------------------------------------------------
# Risk Assessment Tool  (Code Interpreter / Calculator)
# ---------------------------------------------------------------------------
def calculate_risk_and_price(
    extracted_data: Dict[str, Any],
    enriched_data: Optional[Dict[str, Any]] = None,
    loss_history: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Calculate risk score and annual premium.
    Formula: Base Premium * Credit Modifier * Loss Modifier * Size Modifier
    """
    enriched_data = enriched_data or {}
    loss_history = loss_history or {}

    annual_revenue = extracted_data.get("annual_revenue", 100_000)
    employees = extracted_data.get("employees", 5)
    credit_score = enriched_data.get("credit_score", 650)
    crime_score = enriched_data.get("property_risk", {}).get("crime_score", 50)
    total_losses = loss_history.get("total_losses", 0)

    loss_ratio = (total_losses / annual_revenue) if annual_revenue > 0 else 0
    debt_to_equity = extracted_data.get("debt_to_equity", 1.0)
    risk_score = min(100, max(0, 50 + (loss_ratio * 100) + (crime_score * 0.2)))

    base_premium = annual_revenue * 0.005

    credit_modifier = 1.5 if credit_score < 600 else (1.2 if credit_score < 700 else 1.0)

    if loss_ratio > 0.5:
        loss_modifier = 2.0
    elif loss_ratio > 0.3:
        loss_modifier = 1.5
    elif loss_ratio > 0.1:
        loss_modifier = 1.2
    else:
        loss_modifier = 1.0

    size_modifier = 1.0 + (employees / 100)
    annual_premium = base_premium * credit_modifier * loss_modifier * size_modifier

    rationale = (
        f"Base ${base_premium:.2f} x Credit {credit_modifier:.2f} x "
        f"Loss {loss_modifier:.2f} x Size {size_modifier:.2f} = ${annual_premium:.2f}"
    )

    return ToolResult(
        True,
        {
            "risk_score": round(risk_score, 2),
            "loss_ratio": round(loss_ratio, 4),
            "debt_to_equity": round(debt_to_equity, 2),
            "annual_premium": round(annual_premium, 2),
            "pricing_rationale": rationale,
        },
    )
