# Agentic Insurance Underwriting Solution
## Requirements & Architecture Specification

**Version:** 2.0
**Date:** 2026-02-22

---

## 1. Business Problem

NorthStar Insurance Group underwriters spend 40-65% of their time on manual data gathering. The current process suffers from:
- Inconsistent risk assessments across underwriters
- 6-hour average quote turnaround time
- Broker complaints about slow response times
- Manual copy-paste between systems

**Goal:** Automate the underwriting workflow while keeping humans in the loop for final decisions.

---

## 2. Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-1 | Ingest email submissions with attachments | Must |
| FR-2 | Classify content (NAICS/SIC code) | Must |
| FR-3 | Extract structured data via OCR + LLM schema mapping | Must |
| FR-4 | Enrich with external APIs (D&B, HazardHub, web) | Must |
| FR-5 | Validate against underwriting guidelines (hard rules) | Must |
| FR-6 | Calculate risk scores and premium pricing | Must |
| FR-7 | Generate quote package (PDF + email) | Must |
| FR-8 | Draft missing information request emails | Must |
| FR-9 | Draft decline letters with specific guideline citations | Must |
| FR-10 | Support human overrides with audit logging | Must |
| FR-11 | Maintain comprehensive audit trail | Must |
| FR-12 | Parallel execution of data retriever agents | Should |
| FR-13 | 3-phase workflow with conditional edges and loop-back | Must |

## 3. Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-1 | End-to-end latency | < 30 seconds |
| NFR-2 | Uptime SLA | 99.5% (Lambda) |
| NFR-3 | Concurrent submissions | 100+ |
| NFR-4 | Structured logging + traceability | JSON logs + audit trail |
| NFR-5 | Test coverage | >= 80% |
| NFR-6 | Modular architecture | Separated tools, agents, state |
| NFR-7 | Secrets externalized | .env + Secrets Manager |
| NFR-8 | Human-in-the-loop | Streamlit workbench + override API |

---

## 4. Architecture

### 4.1 Workflow (LangGraph StateGraph)

The system implements a 3-phase workflow using `langgraph.graph.StateGraph`:

```
Phase 1: Ingestion & Triage
  START -> ingest_and_classify -> check_data_completeness
    -> [is_data_complete?]
        |-- missing_docs -> draft_missing_info -> END
        |-- data_complete -> (continue to Phase 2)

Phase 2: Qualification
  -> enrichment (3x parallel data retrieval)
    -> check_knockout_rules
    -> [knockout_check?]
        |-- fail -> draft_decline -> END
        |-- pass -> risk_assessment -> (continue to Phase 3)

Phase 3: The Workbench
  -> human_checkpoint (persists state)
    -> [human_decision?]
        |-- approve -> generate_quote -> END
        |-- decline -> draft_decline -> END
        |-- modify  -> update_state -> risk_assessment (loop back)
```

**Implementation:** `src/orchestration/workflow.py`

### 4.2 Agent Architecture

| Agent | Role | LangGraph Node(s) | Tools |
|-------|------|-------------------|-------|
| **Supervisor Agent** | Orchestrates full workflow | Graph entry point | State Manager |
| **Classification Agent** | OCR + NAICS classification | `ingest_and_classify` | `extract_structured_data`, `classify_naics_code` |
| **Data Retriever Agents** | Parallel data acquisition | `enrichment` | `internal_claims_history`, `fetch_external_data`, `web_research_applicant` |
| **Gap Analysis Agent** | Completeness + hard rules | `check_data_completeness`, `check_knockout_rules` | `validate_against_guidelines` |
| **Analyst Agent** | Risk scoring + pricing | `risk_assessment` | `calculate_risk_and_price` |
| **Broker Liaison Agent** | All broker communications | `draft_missing_info`, `draft_decline`, `generate_quote` | `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf` |

### 4.3 Tools (12 total, 4 modules)

**Document Understanding** (`src/tools/document_understanding.py`):
- `extract_structured_data()` - OCR + schema mapping (MVP: mock; prod: AWS Textract / Claude Vision)
- `analyze_image_hazards()` - Inspection photo analysis (MVP: mock; prod: Claude Vision)

**Data Acquisition** (`src/tools/data_acquisition.py`):
- `internal_claims_history()` - Prior loss history (MVP: mock; prod: SQL/CRM API)
- `fetch_external_data()` - Credit + property risk (MVP: mock; prod: D&B, HazardHub, Verisk)
- `web_research_applicant()` - Digital footprint (MVP: mock; prod: headless browser)

**Decision Logic** (`src/tools/decision_logic.py`):
- `classify_naics_code()` - Industry classification (keyword matching -> LLM lookup)
- `validate_against_guidelines()` - 4 hard rules: credit >= 500, loss ratio < 80%, D/E < 3.0, years >= 2
- `calculate_risk_and_price()` - Risk 0-100, premium = base * credit * loss * size modifiers

**Communication** (`src/tools/communication.py`):
- `draft_missing_info_email()` - Request missing documents
- `draft_decline_letter()` - Cite specific failed rules
- `draft_quote_email()` - Quote with terms
- `generate_quote_pdf()` - PDF package (MVP: placeholder S3 URL)

### 4.4 State Management

`src/core/state_manager.py` provides:
- `SubmissionState` dataclass tracking full lifecycle
- `StateManager` singleton with CRUD operations
- `AuditEntry` for component-level action logging
- `Override` tracking for human decisions
- In-memory backend (MVP); DynamoDB-ready interface

### 4.5 API Layer

`src/api/handlers.py` provides:
- `create_app()` FastAPI factory with 5 endpoints (submit, override, status, list, health)
- `SubmissionHandler`, `OverrideHandler`, `QueryHandler` for Lambda compatibility

### 4.6 Human-in-the-Loop UI

`app.py` Streamlit workbench with 6 tabs:
- Overview (applicant info + external data + validation)
- Extracted Data (OCR results + claims history)
- Risk Assessment (metrics, premium, rationale)
- Drafted Email (preview before sending)
- Audit Trail (timestamped component actions)
- Human Override (change decision with reason)

---

## 5. Underwriting Guidelines (Hard Rules)

| Rule ID | Name | Condition | Threshold |
|---------|------|-----------|-----------|
| R001 | Minimum Credit Score | credit_score | >= 500 |
| R002 | Maximum Loss Ratio | loss_ratio | < 80% |
| R003 | Debt to Equity | debt_to_equity | < 3.0 |
| R004 | Minimum Years in Business | years_in_business | >= 2 |

**Required Documents:** application_form, financial_statements, loss_history

---

## 6. Decision Outcomes

| Decision | Trigger | Output |
|----------|---------|--------|
| QUOTED | All rules pass + risk assessed | Quote PDF + email |
| DECLINED | Any hard rule fails | Decline letter with citations |
| MISSING_INFO | Critical documents absent | Request email to broker |
| MANUAL_REVIEW | Human selects Modify | Loops back for re-assessment |

---

## 7. Assumptions

1. **Mock APIs (MVP):** All external data returns mock responses. Swap to real APIs with no architecture changes.
2. **In-Memory State:** Dict-based storage. 1-hour migration to DynamoDB.
3. **Sequential Enrichment (MVP):** 3 data retrievers run sequentially. Code is async-ready via `asyncio.gather()`.
4. **No Real PDF/Email:** Placeholder URLs and draft-only emails. 2-3 hours to add ReportLab + SES.
5. **LangGraph StateGraph:** Fully implemented with conditional edges and loop-back support.

---

## 8. Technology Stack

| Component | Technology |
|-----------|-----------|
| Workflow Engine | LangGraph StateGraph |
| LLM (production) | Anthropic Claude / OpenAI |
| UI | Streamlit |
| API | FastAPI + Uvicorn |
| Serverless | AWS Lambda + SAM |
| State | In-memory (DynamoDB-ready) |
| Testing | pytest |
| Config | python-dotenv |
