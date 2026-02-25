# NorthStar Underwriting - Tools Documentation

This document describes every tool in the system, its purpose, parameters, and the guardrails that protect against invalid input and runtime failures.

---

## Table of Contents

1. [Document Understanding](#1-document-understanding)
2. [Decision & Logic](#2-decision--logic)
3. [Data Acquisition](#3-data-acquisition)
4. [Communication](#4-communication)
5. [Shared Infrastructure](#5-shared-infrastructure)
6. [Workflow Nodes & Orchestration Guardrails](#6-workflow-nodes--orchestration-guardrails)

---

## 1. Document Understanding

**File:** `src/tools/document_understanding.py`
**Agent:** Classification Agent

### `extract_structured_data(document_content, target_schema)`

**Description:** Extracts structured fields from free-text submission documents (emails and attachments). Uses regex and keyword matching to parse applicant name, business type, address, employees, revenue, years in business, coverage details, and more.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `document_content` | `str` | *(required)* | Raw text of the email/document |
| `target_schema` | `str` | `"general_submission"` | Schema hint (reserved for future use) |

**Guardrails:**
- **Type check:** Rejects non-string `document_content` with `ToolResult(False, ...)`
- **Empty input check:** Rejects blank/whitespace-only content
- **Max length cap:** Truncates input to `100,000` characters to prevent memory issues
- **Try/except wrapper:** Catches all exceptions and returns a `ToolResult` with error details instead of crashing
- **Confidence scoring:** Returns `0.85` confidence for substantive text (>100 chars), `0.5` for short text
- **Safe defaults:** Every extracted field has a fallback value (e.g., `"Unknown Applicant"`, `5` employees, `$100,000` revenue)
- **Safe applicant ID generation:** Strips non-alphanumeric characters from names before building IDs

---

## 2. Decision & Logic

**File:** `src/tools/decision_logic.py`
**Agent:** Underwriting Analyst Agent

### `classify_naics_code(business_description, business_name)`

**Description:** Classifies a business into a NAICS industry code using keyword matching against a predefined map. Returns the NAICS code, industry name, and confidence score.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `business_description` | `str` | *(required)* | Business type or description |
| `business_name` | `str` | `""` | Business name (optional, aids matching) |

**Guardrails:**
- **Type check:** Rejects non-string `business_description`; coerces bad `business_name` to `""`
- **Input truncation:** Both inputs capped at `50,000` characters
- **Safe fallback:** Unrecognized businesses return NAICS `"999999"` / `"Unknown"` with `0.5` confidence
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `validate_against_guidelines(extracted_data, enriched_data, web_data, loss_history)`

**Description:** Validates a submission against hard-coded underwriting rules (credit score >= 500, loss ratio < 80%, debt-to-equity < 3.0, years in business >= 2) and checks for required documents (application form, financial statements, loss history).

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `extracted_data` | `dict` | *(required)* | Parsed submission fields |
| `enriched_data` | `dict` | `None` | External bureau data |
| `web_data` | `dict` | `None` | Web research results |
| `loss_history` | `dict` | `None` | Internal claims history |

**Guardrails:**
- **Type check:** Rejects non-dict `extracted_data`; coerces `None` dicts to `{}`
- **Submitted docs validation:** Ensures `submitted_documents` is a list before iterating
- **Safe numeric conversion:** All rule values go through `_safe_numeric()` to handle `None`, strings, and type mismatches
- **Missing docs short-circuit:** Returns immediately with `passes_guidelines=False` if required documents are absent
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `calculate_risk_and_price(extracted_data, enriched_data, loss_history)`

**Description:** Calculates a risk score (0-100) and annual premium using the formula: `Base Premium * Credit Modifier * Loss Modifier * Size Modifier`. Base premium is 0.5% of annual revenue.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `extracted_data` | `dict` | *(required)* | Parsed submission fields |
| `enriched_data` | `dict` | `None` | External bureau data |
| `loss_history` | `dict` | `None` | Internal claims history |

**Guardrails:**
- **Type check:** Rejects non-dict `extracted_data`; coerces `None` dicts to `{}`
- **Safe numeric conversion:** All values go through `_safe_numeric(value, default)` which returns a sensible default on `None`/bad types
- **Value clamping via `_clamp()`:**
  - `annual_revenue`: 0 to $10B
  - `employees`: 0 to 100,000
  - `credit_score`: 0 to 850
  - `crime_score`: 0 to 100
  - `total_losses`: floor of 0
  - `risk_score`: 0 to 100
- **Premium bounds:** Final premium clamped between `$50` (floor) and `$50,000,000` (ceiling)
- **Division-by-zero protection:** `loss_ratio` defaults to `0` when `annual_revenue` is `0`
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### Helper Functions

| Helper | Description |
|---|---|
| `_safe_numeric(value, default)` | Converts any value to `float`; returns `default` on `None`/`TypeError`/`ValueError` |
| `_clamp(value, lo, hi)` | Constrains a numeric value between `lo` and `hi` bounds |

---

## 3. Data Acquisition

**File:** `src/tools/data_acquisition.py`
**Agent:** Data Retrieval Agent (Internal, External Bureau, Open Source)

### `internal_claims_history(applicant_id, applicant_name, date_range_years)`

**Description:** Fetches prior loss history from internal claims/CRM systems. MVP returns mock data (2 sample claims totaling $8,000). Production version would query SQL or use RPA bridges.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `applicant_id` | `str` | *(required)* | Unique applicant identifier |
| `applicant_name` | `str` | `""` | Applicant business name |
| `date_range_years` | `int` | `5` | How many years of history to fetch |

**Guardrails:**
- **Required field validation:** `applicant_id` must be a non-empty string
- **Auto-correction:** Invalid `date_range_years` (non-int or < 1) silently defaults to `5`
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `fetch_external_data(applicant_name, applicant_address, data_sources)`

**Description:** Fetches external risk data from third-party bureaus (D&B, HazardHub, Verisk). MVP returns mock data including credit score, financial health, and property risk details.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `applicant_name` | `str` | *(required)* | Business name to look up |
| `applicant_address` | `str` | `""` | Business address |
| `data_sources` | `list` | `None` | Specific sources to query |

**Guardrails:**
- **Required field validation:** `applicant_name` must be a non-empty string
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `web_research_applicant(applicant_name, applicant_website)`

**Description:** Researches applicant's web presence for risk flags. Checks business operations, reviews, health inspections, and alcohol service. MVP returns mock data.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `applicant_name` | `str` | *(required)* | Business name to research |
| `applicant_website` | `str` | `""` | Business website URL |

**Guardrails:**
- **Required field validation:** `applicant_name` must be a non-empty string
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

## 4. Communication

**File:** `src/tools/communication.py`
**Agent:** Broker Liaison Agent

### `draft_missing_info_email(broker_email, broker_name, applicant_name, missing_documents)`

**Description:** Drafts a professional email requesting missing documentation from the broker. Lists each missing document as a bullet point.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `broker_email` | `str` | *(required)* | Recipient email address |
| `broker_name` | `str` | `""` | Broker's display name |
| `applicant_name` | `str` | `""` | Applicant business name |
| `missing_documents` | `list` | `None` | List of missing document names |

**Guardrails:**
- **Email validation:** `_validate_email()` checks RFC 5322 simplified format; rejects invalid addresses
- **String sanitization:** `_sanitize()` strips control characters (`\x00-\x08`, `\x0b`, etc.) and truncates to 200 chars
- **Empty list check:** Rejects empty `missing_documents` list
- **Safe defaults:** Missing `broker_name` defaults to `"Broker"`, missing `applicant_name` to `"the applicant"`
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `draft_decline_letter(broker_email, broker_name, applicant_name, failed_rules)`

**Description:** Drafts a decline letter citing specific guideline violations. Each failed rule is listed with its description and reason.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `broker_email` | `str` | *(required)* | Recipient email address |
| `broker_name` | `str` | `""` | Broker's display name |
| `applicant_name` | `str` | `""` | Applicant business name |
| `failed_rules` | `list[dict]` | `None` | List of dicts with `rule_description` and `reason` |

**Guardrails:**
- **Email validation:** Rejects structurally invalid email addresses
- **String sanitization:** All user-facing text is sanitized (control chars removed, length capped)
- **Dict type check:** Skips non-dict entries in `failed_rules`
- **Fallback text:** If no valid rules provided, uses generic "Underwriting guidelines not met"
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `draft_quote_email(broker_email, broker_name, applicant_name, quote_amount, policy_term, quote_pdf_url)`

**Description:** Drafts an email with the quote summary including premium amount, policy term, and link to the quote PDF.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `broker_email` | `str` | *(required)* | Recipient email address |
| `broker_name` | `str` | `""` | Broker's display name |
| `applicant_name` | `str` | `""` | Applicant business name |
| `quote_amount` | `float` | `0` | Annual premium amount |
| `policy_term` | `str` | `"1 year"` | Policy duration |
| `quote_pdf_url` | `str` | `""` | URL to the generated PDF |

**Guardrails:**
- **Email validation:** Rejects structurally invalid email addresses
- **Amount validation:** Rejects non-numeric or negative `quote_amount`
- **String sanitization:** All text fields sanitized
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### `generate_quote_pdf(extracted_data, risk_metrics, quote_amount, applicant_name)`

**Description:** Generates a quote PDF document. MVP returns a placeholder S3 URL. Production would use ReportLab or wkhtmltopdf.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `extracted_data` | `dict` | *(required)* | Parsed submission fields |
| `risk_metrics` | `dict` | *(required)* | Risk scoring results |
| `quote_amount` | `float` | *(required)* | Annual premium |
| `applicant_name` | `str` | `""` | Applicant business name |

**Guardrails:**
- **Type checks:** Both `extracted_data` and `risk_metrics` must be dicts
- **Amount validation:** Rejects non-numeric or negative `quote_amount`
- **S3 key sanitization:** Applicant name stripped to alphanumeric + hyphens only, duplicate hyphens collapsed, capped at 60 chars
- **Try/except wrapper:** Returns `ToolResult` with error on any exception

---

### Helper Functions

| Helper | Description |
|---|---|
| `_validate_email(email)` | RFC 5322 simplified regex check: `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| `_sanitize(text, max_len)` | Strips control characters and truncates to `max_len` (default 200) |

---

## 5. Shared Infrastructure

### `ToolResult` (in `decision_logic.py`)

**Description:** Standard return object for all tools. Provides a uniform interface with `success`, `data`, `error`, and `timestamp` fields.

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Whether the tool call succeeded |
| `data` | `dict` | Result payload |
| `error` | `str or None` | Error message if failed |
| `timestamp` | `str` | ISO 8601 timestamp (UTC) |

### `StateManager` (in `src/core/state_manager.py`)

**Description:** In-memory state store managing submission lifecycle. Handles CRUD operations, audit trails, and human overrides.

**Key Guardrails:**
- **Duplicate submission prevention:** `create_state()` raises `ValueError` if `submission_id` already exists
- **Empty ID rejection:** Rejects empty or whitespace-only `submission_id`
- **Field allowlist:** `update_state()` only permits updates to a defined set of fields; rejects unknown fields with `ValueError`
- **Decision validation:** Warns on non-standard decision values not in the `DecisionType` enum
- **Status validation:** Warns on non-standard status values not in the `SubmissionStatus` enum
- **Override validation:** `apply_override()` requires non-empty `user_id`, valid decision from enum, and non-empty `override_reason`
- **Audit trail:** Every override automatically generates an audit entry
- **UTC timestamps:** All timestamps use `datetime.now(UTC)` (no deprecated `utcnow()`)

---

## 6. Workflow Nodes & Orchestration Guardrails

**File:** `src/orchestration/workflow.py`

The LangGraph StateGraph orchestrates 10 nodes across 3 phases. Every node is wrapped in a try/except block to prevent a single failure from crashing the entire workflow.

### Graceful Degradation Strategy

| Failure Location | Behavior |
|---|---|
| `ingest_and_classify` | Sets `status=FAILED`, logs error, appends to error list |
| `check_data_completeness` | Sets `status=FAILED`, logs error |
| `draft_missing_info` | Completes with `decision=MISSING_INFO`, logs error |
| `enrichment` | Returns empty dicts `{}` for all data sources so downstream nodes can still run |
| `check_knockout_rules` | Falls back to `decision=MANUAL_REVIEW` instead of crashing |
| `risk_assessment` | Falls back to `decision=MANUAL_REVIEW` with empty risk metrics |
| `draft_decline` | Completes with `decision=DECLINED`, logs error |
| `generate_quote` | Completes with `decision=QUOTED`, logs error |

### Helper Functions

| Helper | Description |
|---|---|
| `_audit(state, component, action, result)` | Appends a timestamped entry to the audit trail |
| `_append_error(state, phase, error)` | Returns a new error list with an additional error entry for the given phase |

### Conditional Edge Functions

| Function | Purpose | Outcomes |
|---|---|---|
| `is_data_complete` | Checks for missing required documents | `"missing_docs"` or `"data_complete"` |
| `knockout_check` | Checks if hard rules failed | `"fail"` or `"pass"` |
| `human_decision` | Routes based on human/AI decision | `"approve"`, `"decline"`, or `"modify"` |

---

## Constants Reference

| Constant | Value | Location |
|---|---|---|
| `MAX_DOCUMENT_LENGTH` | 100,000 chars | `document_understanding.py` |
| `MAX_INPUT_LENGTH` | 50,000 chars | `decision_logic.py` |
| `MAX_EMPLOYEES` | 100,000 | `decision_logic.py` |
| `MAX_ANNUAL_REVENUE` | $10,000,000,000 | `decision_logic.py` |
| `MIN_PREMIUM` | $50.00 | `decision_logic.py` |
| `MAX_PREMIUM` | $50,000,000.00 | `decision_logic.py` |
