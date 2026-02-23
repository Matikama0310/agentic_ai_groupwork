# Architecture

This document explains how the NorthStar Agentic Underwriting System works: the workflow engine, agents, tools, state management, and how requirements trace to code and tests.

---

## Table of Contents

1. [Business Problem](#1-business-problem)
2. [3-Phase Workflow](#2-3-phase-workflow)
3. [LangGraph StateGraph Implementation](#3-langgraph-stategraph-implementation)
4. [Agent Architecture](#4-agent-architecture)
5. [Tool Reference](#5-tool-reference)
6. [State Management](#6-state-management)
7. [Underwriting Rules](#7-underwriting-rules)
8. [Decision Outcomes](#8-decision-outcomes)
9. [API Layer](#9-api-layer)
10. [Streamlit Workbench](#10-streamlit-workbench)
11. [Requirements & Traceability](#11-requirements--traceability)
12. [Technology Stack](#12-technology-stack)

---

## 1. Business Problem

NorthStar Insurance underwriters spend 40-65% of their time on manual data gathering. The current process has:
- Inconsistent risk assessments across underwriters
- 6-hour average quote turnaround time
- Broker complaints about slow response times
- Manual copy-paste between systems

**Goal:** Automate the underwriting workflow end-to-end while keeping humans in the loop for final decisions.

---

## 2. 3-Phase Workflow

Insurance submissions flow through three phases:

```
PHASE 1: INGESTION & TRIAGE
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  START                                                       │
│    │                                                         │
│    ▼                                                         │
│  ┌─────────────────────┐                                     │
│  │ ingest_and_classify  │  OCR extraction + NAICS code       │
│  │ (Classification Agent│  classification from email/docs    │
│  └─────────┬───────────┘                                     │
│            ▼                                                 │
│  ┌─────────────────────────┐                                 │
│  │ check_data_completeness │  Are all required documents     │
│  │ (Underwriting Analyst)    │  present?                       │
│  └─────────┬───────────────┘                                 │
│            ▼                                                 │
│     ┌──────────────┐                                         │
│     │ is_data_      │                                        │
│     │ complete?     │                                        │
│     └──┬────────┬──┘                                         │
│    NO  │        │ YES                                        │
│        ▼        └──────────────────────────── to Phase 2     │
│  ┌──────────────┐                                            │
│  │draft_missing_ │  Email broker requesting                  │
│  │info           │  missing documents                        │
│  │(Broker Liaison│                                           │
│  └──────┬───────┘                                            │
│         ▼                                                    │
│       END (awaiting broker reply)                            │
└──────────────────────────────────────────────────────────────┘

PHASE 2: QUALIFICATION
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌───────────────┐                                           │
│  │ enrichment     │  3x parallel data retrieval:             │
│  │ (Data Retrieval│  - Internal claims history               │
│  │  Agent)        │  - External bureaus (D&B, HazardHub)     │
│  └───────┬───────┘  - Web research                           │
│          ▼                                                   │
│  ┌────────────────────┐                                      │
│  │check_knockout_rules │  Validate hard underwriting rules   │
│  │(Underwriting Analyst) │  (credit, loss ratio, D/E, years)   │
│  └────────┬───────────┘                                      │
│           ▼                                                  │
│    ┌──────────────┐                                          │
│    │ knockout_     │                                         │
│    │ check?        │                                         │
│    └──┬────────┬──┘                                          │
│  FAIL │        │ PASS                                        │
│       ▼        ▼                                             │
│  ┌──────────┐ ┌────────────────┐                             │
│  │draft_    │ │risk_assessment  │  Risk score (0-100)        │
│  │decline   │ │(Underwriting Analyst)  │  + premium calculation     │
│  │(Broker   │ └────────┬───────┘                             │
│  │ Liaison) │          └──────────────────── to Phase 3      │
│  └────┬─────┘                                                │
│       ▼                                                      │
│     END (auto-decline with rule citations)                   │
└──────────────────────────────────────────────────────────────┘

PHASE 3: THE WORKBENCH (Human-in-the-Loop)
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────────────┐                                        │
│  │ human_checkpoint  │  Persists state to DB,                │
│  │ (Streamlit UI)    │  awaits human decision                │
│  └────────┬─────────┘                                        │
│           ▼                                                  │
│    ┌──────────────┐                                          │
│    │ human_        │                                         │
│    │ decision?     │                                         │
│    └─┬──────┬───┬─┘                                          │
│ APPROVE  DECLINE  MODIFY                                     │
│      │      │      │                                         │
│      ▼      │      ▼                                         │
│ ┌──────────┐│ ┌──────────────┐                               │
│ │generate_ ││ │update_state   │  Apply human modifications   │
│ │quote     ││ │               │                              │
│ │(Broker   ││ └──────┬───────┘                               │
│ │ Liaison) ││        │                                       │
│ └────┬─────┘│        ▼                                       │
│      │      │   LOOP BACK to risk_assessment (Phase 2)       │
│      ▼      ▼                                                │
│    END    draft_decline -> END                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. LangGraph StateGraph Implementation

**File:** `src/orchestration/workflow.py`

The workflow is built using `langgraph.graph.StateGraph` with a `TypedDict` state schema.

### State Schema (`UnderwritingState`)

```
Input Fields:
  submission_id, email_subject, email_body, broker_email,
  broker_name, attachments

Phase 1 Fields:
  extracted_data, extraction_confidence, naics_code,
  naics_industry, naics_confidence

Phase 2 Fields:
  internal_data, external_data, web_data,
  validation_result, risk_metrics

Phase 3 Fields:
  decision, drafted_email, quote_pdf_url

Metadata:
  status, errors, audit_trail
```

### 10 Nodes

| # | Node Function | Phase | What It Does |
|---|---------------|-------|--------------|
| 1 | `ingest_and_classify` | 1 | Calls `extract_structured_data()` and `classify_naics_code()` |
| 2 | `check_data_completeness` | 1 | Checks for required documents in extracted data |
| 3 | `draft_missing_info` | 1 | Calls `draft_missing_info_email()` to request docs from broker |
| 4 | `enrichment` | 2 | Calls 3 data tools: `internal_claims_history()`, `fetch_external_data()`, `web_research_applicant()` |
| 5 | `check_knockout_rules` | 2 | Calls `validate_against_guidelines()` against hard rules |
| 6 | `risk_assessment` | 2 | Calls `calculate_risk_and_price()` for risk score + premium |
| 7 | `human_checkpoint` | 3 | Persists state to DB, marks as awaiting human decision |
| 8 | `generate_quote` | 3 | Calls `generate_quote_pdf()` and `draft_quote_email()` |
| 9 | `draft_decline` | 3 | Calls `draft_decline_letter()` with failed rule citations |
| 10 | `update_state_node` | 3 | Applies human modifications, routes back to risk_assessment |

### 3 Conditional Edges

| Edge Function | After Node | Condition | Routes To |
|---------------|-----------|-----------|-----------|
| `is_data_complete` | `check_data_completeness` | Missing critical docs? | `"missing_docs"` -> `draft_missing_info` / `"data_complete"` -> `enrichment` |
| `knockout_check` | `check_knockout_rules` | Any hard rule fails? | `"fail"` -> `draft_decline` / `"pass"` -> `risk_assessment` |
| `human_decision` | `human_checkpoint` | Human override decision | `"approve"` -> `generate_quote` / `"decline"` -> `draft_decline` / `"modify"` -> `update_state_node` |

### Loop-back

When the human selects "Modify", the workflow routes to `update_state_node` which applies modifications then edges back to `risk_assessment`, creating a re-evaluation loop.

### Graph Construction

`build_underwriting_graph()` wires all nodes and edges, then `compile_workflow()` compiles it into a runnable LangGraph application.

---

## 4. Agent Architecture

The system uses 5 agents, each mapped to LangGraph nodes:

### Supervisor Agent
- **File:** `src/orchestration/supervisor_agent.py`
- **Class:** `SupervisorAgent`
- **Role:** Orchestrates the entire workflow
- **How it works:**
  1. Creates initial state in `StateManager`
  2. Builds `UnderwritingState` input dict from submission data
  3. Calls `workflow.invoke(graph_input)` to run the full LangGraph
  4. Syncs final graph state back to `StateManager` (decision, premium, risk, emails)
  5. Syncs audit trail entries

### Classification Agent
- **Node:** `ingest_and_classify`
- **Tools:** `extract_structured_data`, `classify_naics_code`
- **Role:** Extracts structured fields from documents (OCR) and classifies the business by NAICS industry code
- **Output:** `extracted_data`, `naics_code`, `naics_industry`, `extraction_confidence`

### Data Retrieval Agent
- **Node:** `enrichment`
- **Tools:** `internal_claims_history`, `fetch_external_data`, `web_research_applicant`
- **Role:** Gathers data from three sources in parallel: internal claims history, external credit/property bureaus, and web presence research
- **Output:** `internal_data`, `external_data`, `web_data`

### Underwriting Analyst Agent
- **Nodes:** `check_data_completeness`, `check_knockout_rules`, `risk_assessment`
- **Tools:** `validate_against_guidelines`, `calculate_risk_and_price`
- **Role:** Handles all application evaluation: validates document completeness, checks hard underwriting rules (knockout), and calculates risk score + premium pricing
- **Output:** `validation_result` (with `passes_guidelines`, `failed_rules`, `missing_critical_docs`), `risk_metrics` (with `risk_score`, `annual_premium`, `loss_ratio`, `pricing_rationale`)

### Broker Liaison Agent
- **Nodes:** `draft_missing_info`, `draft_decline`, `generate_quote`
- **Tools:** `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf`
- **Role:** Drafts all outbound communications to brokers (missing info requests, decline letters, quote packages)
- **Output:** `drafted_email`, `quote_pdf_url`

---

## 5. Tool Reference

All tools return a `ToolResult(success: bool, data: dict, error: str | None)`.

### Document Understanding (`src/tools/document_understanding.py`)

| Tool | Inputs | Output Data | MVP Behavior | Production Target |
|------|--------|-------------|-------------|-------------------|
| `extract_structured_data` | `document_content`, `target_schema` | `extracted_fields`, `extraction_confidence`, `document_types`, `missing_fields` | Returns mock extracted fields | AWS Textract / Claude Vision |
| `analyze_image_hazards` | `image_base64`, `hazard_types` | `hazards_detected`, `analysis_confidence` | Returns mock hazard list | Claude Vision API |

### Data Acquisition (`src/tools/data_acquisition.py`)

| Tool | Inputs | Output Data | MVP Behavior | Production Target |
|------|--------|-------------|-------------|-------------------|
| `internal_claims_history` | `applicant_id`, `applicant_name`, `date_range_years` | `loss_runs`, `total_losses`, `loss_frequency`, `loss_ratio`, `policy_history` | Returns mock loss run data | Internal SQL/CRM API |
| `fetch_external_data` | `applicant_name`, `applicant_address`, `data_sources` | `credit_score`, `financial_health`, `duns_number`, `property_risk` | Returns mock D&B/HazardHub data | D&B, HazardHub, Verisk APIs |
| `web_research_applicant` | `applicant_name`, `applicant_website` | `website_verified`, `public_reviews_summary`, `risk_flags` | Returns mock web research | Headless browser / search API |

### Decision Logic (`src/tools/decision_logic.py`)

| Tool | Inputs | Output Data | MVP Behavior | Production Target |
|------|--------|-------------|-------------|-------------------|
| `classify_naics_code` | `business_description`, `business_name` | `naics_code`, `industry`, `confidence` | Keyword-based classification | LLM classification |
| `validate_against_guidelines` | `extracted_data`, `enriched_data`, `web_data`, `internal_data` | `passes_guidelines`, `failed_rules`, `missing_critical_docs` | Evaluates 4 hard rules + required docs | Same logic, real data inputs |
| `calculate_risk_and_price` | `extracted_data`, `external_data`, `internal_data` | `annual_premium`, `risk_score`, `loss_ratio`, `pricing_rationale` | Formula: base * credit * loss * size modifiers | Enhanced model with actuarial tables |

### Communication (`src/tools/communication.py`)

| Tool | Inputs | Output Data | MVP Behavior | Production Target |
|------|--------|-------------|-------------|-------------------|
| `draft_missing_info_email` | `broker_email`, `broker_name`, `applicant_name`, `missing_documents` | `subject`, `body`, `to`, `ready_to_send` | Generates email text | Same + SES/SMTP send |
| `draft_decline_letter` | `broker_email`, `broker_name`, `applicant_name`, `failed_rules` | `subject`, `body`, `to`, `ready_to_send` | Generates decline text with rule citations | Same + SES/SMTP send |
| `draft_quote_email` | `broker_email`, `broker_name`, `applicant_name`, `quote_amount`, `policy_term`, `quote_pdf_url` | `subject`, `body`, `to` | Generates quote email text | Same + SES/SMTP send |
| `generate_quote_pdf` | `extracted`, `risk_metrics`, `premium`, `applicant_name` | `quote_pdf_s3_url` | Returns placeholder S3 URL | ReportLab PDF + S3 upload |

---

## 6. State Management

**File:** `src/core/state_manager.py`

### Data Model

```
SubmissionState (dataclass):
├── submission_id         # Unique ID (SUB-YYYYMMDD-XXXX)
├── status                # SubmissionStatus enum (see below)
├── created_at            # Timestamp
├── updated_at            # Timestamp
├── email_subject         # Original email subject
├── email_body            # Original email body
├── broker_email          # Broker contact
├── broker_name           # Broker name
├── attachments           # List of attachment metadata
├── extracted_data        # OCR results
├── naics_code            # Industry classification
├── naics_industry        # Industry name
├── enrichment_data       # Combined external data
├── validation_result     # Guidelines check result
├── risk_metrics          # Risk score + premium
├── decision              # DecisionType enum
├── drafted_email         # Email draft content
├── quote_pdf_url         # PDF URL
├── audit_trail           # List[AuditEntry]
└── overrides             # List[Override]
```

### Status Lifecycle

```
INGESTION -> EXTRACTION -> ENRICHMENT -> ANALYSIS -> DECISION -> COMPLETED
                                                              -> FAILED
```

### Key Operations

| Method | Description |
|--------|-------------|
| `create_state(submission_id, ...)` | Creates a new submission record |
| `get_state(submission_id)` | Retrieves submission by ID |
| `update_state(submission_id, **kwargs)` | Updates any fields |
| `add_audit_entry(submission_id, component, action, details, result)` | Appends to audit trail |
| `apply_override(submission_id, user_id, decision, reason)` | Records human override |
| `list_submissions()` | Returns all submissions |
| `get_submission_summary(submission_id)` | Returns summary dict |

### Storage

- **MVP:** In-memory Python dict (resets on restart)
- **Production:** DynamoDB (same interface, swap storage layer)

---

## 7. Underwriting Rules

Defined in `UNDERWRITING_GUIDELINES` in `src/tools/decision_logic.py`:

| Rule ID | Name | Field | Threshold | Severity |
|---------|------|-------|-----------|----------|
| R001 | Minimum Credit Score | `credit_score` | >= 500 | Hard |
| R002 | Maximum Loss Ratio | `loss_ratio` | < 80% | Hard |
| R003 | Debt to Equity | `debt_to_equity` | < 3.0 | Hard |
| R004 | Minimum Years in Business | `years_in_business` | >= 2 | Hard |

**Required Documents:** `application_form`, `financial_statements`, `loss_history`

If any hard rule fails, the submission is auto-declined with the specific rule citation in the decline letter.

---

## 8. Decision Outcomes

| Decision | Trigger | Workflow Path | Output |
|----------|---------|---------------|--------|
| **QUOTED** | All rules pass + human approves | Phase 1 -> 2 -> 3 -> `generate_quote` | Quote PDF + email |
| **DECLINED** | Hard rule fails OR human declines | Phase 2 -> `draft_decline` OR Phase 3 -> `draft_decline` | Decline letter citing specific rules |
| **MISSING_INFO** | Critical documents absent | Phase 1 -> `draft_missing_info` | Request email to broker |
| **MANUAL_REVIEW** | Human selects Modify | Phase 3 -> `update_state` -> loop to Phase 2 | Re-runs risk assessment |

---

## 9. API Layer

**File:** `src/api/handlers.py`

`create_app()` returns a FastAPI application with 5 endpoints. Each endpoint also has a Lambda-compatible handler class (`SubmissionHandler`, `OverrideHandler`, `QueryHandler`) for serverless deployment.

**Lambda entry points** in `lambda/` wrap these handlers for AWS Lambda + API Gateway.

**Infrastructure** is defined in `infrastructure/sam_template.yaml` (AWS SAM template with 3 Lambda functions + API Gateway + CloudWatch).

---

## 10. Streamlit Workbench

**File:** `app.py`

The human-in-the-loop UI provides 7 tabs:

| Tab | Content |
|-----|---------|
| Overview | Applicant info, external data summary, validation results |
| Workflow | Graphviz diagram with dynamic node highlighting |
| Extracted Data | OCR results, claims history, document inventory |
| Risk Assessment | Risk score, premium, loss ratio, pricing rationale |
| Drafted Email | Email preview (missing info, decline, or quote) |
| Audit Trail | Timestamped log of every component action |
| Human Override | Form to change decision (approve/decline/modify) with reason |

The sidebar provides a submission form to create new applications.

---

## 11. Requirements & Traceability

### Functional Requirements

| FR ID | Requirement | Agent(s) | Code Module | Test(s) |
|-------|-------------|----------|-------------|---------|
| FR-1 | Ingest email submissions | Classification | `workflow.py::ingest_and_classify` | `TestWorkflowNodes::test_ingest_and_classify` |
| FR-2 | Classify content (NAICS) | Classification | `decision_logic.py::classify_naics_code` | `TestDecisionTools::test_classify_naics_*` |
| FR-3 | Extract data via OCR | Classification | `document_understanding.py::extract_structured_data` | `TestDocumentTools::test_extract_*` |
| FR-4 | Enrich with external APIs | Data Retrieval | `data_acquisition.py::*` | `TestDataTools::*` |
| FR-5 | Validate against guidelines | Underwriting Analyst | `decision_logic.py::validate_against_guidelines` | `TestDecisionTools::test_validate_*` |
| FR-6 | Calculate risk + pricing | Underwriting Analyst | `decision_logic.py::calculate_risk_and_price` | `TestDecisionTools::test_calculate_*` |
| FR-7 | Generate quote package | Broker Liaison | `communication.py::generate_quote_pdf` | `TestCommsTools::test_generate_*` |
| FR-8 | Draft missing info emails | Broker Liaison | `communication.py::draft_missing_info_email` | `TestCommsTools::test_draft_missing_*` |
| FR-9 | Draft decline letters | Broker Liaison | `communication.py::draft_decline_letter` | `TestCommsTools::test_draft_decline_*` |
| FR-10 | Human overrides | Supervisor + UI | `state_manager.py::apply_override` | `TestStateManager::test_apply_override` |
| FR-11 | Audit trail | State Manager | `state_manager.py::add_audit_entry` | `TestStateManager::test_audit_entry` |
| FR-12 | Parallel data retrieval | Data Retrieval | `workflow.py::enrichment` | `TestWorkflowNodes::test_enrichment` |
| FR-13 | 3-phase workflow | Supervisor | `workflow.py::build_underwriting_graph` | `TestEndToEnd::test_full_workflow_*` |

### Non-Functional Requirements

| NFR ID | Requirement | Target | Implementation |
|--------|-------------|--------|----------------|
| NFR-1 | End-to-end latency | < 30s | Tool timeouts; async-ready |
| NFR-2 | Uptime SLA | 99.5% | AWS Lambda + SAM |
| NFR-3 | Concurrent submissions | 100+ | Lambda auto-scaling |
| NFR-4 | Structured logging | JSON logs | Python logging + audit trail |
| NFR-5 | Test coverage | >= 80% | 36 tests across all layers |
| NFR-6 | Modular architecture | Separated concerns | 4 tool modules + workflow + state |
| NFR-7 | Secrets externalized | .env | python-dotenv + Secrets Manager |
| NFR-8 | Human-in-the-loop | Streamlit | Workbench + override API |

### Conditional Edge Test Coverage

| Edge Function | Tests | Scenarios Covered |
|---------------|-------|-------------------|
| `is_data_complete` | 2 | Missing docs -> draft email; Complete -> enrichment |
| `knockout_check` | 2 | Rule fails -> decline; All pass -> risk assessment |
| `human_decision` | 2 | Approve -> quote; Decline -> decline letter |

---

## 12. Technology Stack

| Component | Technology |
|-----------|-----------|
| Workflow Engine | LangGraph StateGraph (langgraph >= 0.2.0) |
| LLM (production) | Anthropic Claude / OpenAI |
| UI | Streamlit >= 1.30.0 |
| API | FastAPI + Uvicorn |
| Serverless | AWS Lambda + API Gateway (SAM) |
| State | In-memory dict (DynamoDB-ready) |
| Testing | pytest + pytest-cov |
| Config | python-dotenv |
| Logging | structlog |
| Retries | tenacity |
| Visualization | graphviz |
