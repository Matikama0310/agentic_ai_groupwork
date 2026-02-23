# NorthStar Insurance - Agentic Underwriting System (MVP)

![Status](https://img.shields.io/badge/status-MVP-green)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![LangGraph](https://img.shields.io/badge/langgraph-0.2+-blue)
![Tests](https://img.shields.io/badge/tests-34_passing-green)

An **agentic AI system** for automated insurance underwriting built with **LangGraph StateGraph** and **Streamlit**. Insurance applications flow through a 3-phase workflow (Ingestion, Qualification, Human Review) powered by 5 specialized agents and 11 tools, with human-in-the-loop decision making via a Streamlit workbench.

**Business Problem:** NorthStar Insurance underwriters spend 40-65% of their time on manual data gathering, quote turnaround has slipped from 2 to 6 hours, and risk assessments vary between underwriters. This system automates the full pipeline while keeping humans in the loop for final decisions.

> **Note:** This is a fully functional MVP. All external data sources use deterministic mock data — no API keys or LLMs are required to run.

---

## Prerequisites

- **Python 3.12+** ([python.org/downloads](https://www.python.org/downloads/))
- **Git** ([git-scm.com](https://git-scm.com/))
- **Graphviz** (optional, for workflow diagrams in Streamlit)
  - Windows: `winget install graphviz` or download from [graphviz.org](https://graphviz.org/download/)
  - macOS: `brew install graphviz`
  - Linux: `sudo apt install graphviz`

---

## Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd agentic_ai_groupwork
```

### 2. Create a virtual environment

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

No additional configuration is needed. The MVP runs entirely with mock data.

---

## Running the System

| Mode | Command | Description |
|------|---------|-------------|
| CLI Demo | `python main.py` | Runs one submission through the full workflow |
| Streamlit UI | `streamlit run app.py` | Human-in-the-loop workbench (submit, review, override) |
| API Server | `python main.py --server` | FastAPI REST API at `http://localhost:8000/docs` |
| Tests | `pytest tests/test_all.py -v` | All 34 tests (runs in < 1 second) |

### CLI Demo Output

```
NorthStar Insurance - Agentic Underwriting System (MVP Demo)
[1/3] Submitting application: DEMO-20260222-...
[2/3] Processing complete!
      Decision: QUOTED
      Premium:  $2,800.00
      Risk:     58.6/100
[3/3] Audit Trail (7 entries)
```

### Streamlit Workbench

The workbench provides 7 tabs: Overview, Workflow Diagram, Extracted Data, Risk Assessment, Drafted Email, Audit Trail, and Human Override. Submit applications via the sidebar, review all data, and apply override decisions.

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/submit` | Process new insurance application |
| POST | `/override` | Apply human override to a submission |
| GET | `/status/{id}` | Query a specific submission |
| GET | `/status` | List all submissions |
| GET | `/health` | Health check |

---

## Testing

```bash
# Run all 34 tests
pytest tests/test_all.py -v

# With coverage report
pytest tests/test_all.py --cov=src --cov-report=term-missing

# Run specific test category
pytest tests/test_all.py -k "EndToEnd" -v
pytest tests/test_all.py -k "DecisionTools" -v
pytest tests/test_all.py -k "ConditionalEdges" -v
```

| Category | Tests | What's Tested |
|----------|-------|---------------|
| Document Tools | 2 | OCR extraction (high/low confidence) |
| Decision Tools | 4 | NAICS classification, guidelines validation, risk/pricing |
| Data Tools | 3 | Internal claims, external bureaus, web research |
| Communication Tools | 4 | Email drafts, decline letters, PDF generation |
| State Manager | 7 | CRUD, audit trail, overrides |
| Workflow Nodes | 3 | Ingest, enrich, risk assessment nodes |
| Conditional Edges | 6 | Data completeness, knockout, human decision |
| End-to-End | 3 | Full workflow, performance, supervisor integration |
| **Total** | **34** | **All passing** |

---

## Project Structure

```
agentic_ai_groupwork/
├── main.py                              # CLI entry point (demo + server modes)
├── app.py                               # Streamlit workbench (human-in-the-loop UI)
├── requirements.txt                     # Python dependencies
├── pyproject.toml                       # Project config (pytest, black, isort)
├── Makefile                             # Build automation shortcuts
│
├── src/
│   ├── orchestration/
│   │   ├── workflow.py                  # LangGraph StateGraph (10 nodes, 3 edges)
│   │   └── supervisor_agent.py          # Supervisor agent orchestrator
│   ├── tools/
│   │   ├── decision_logic.py            # NAICS classifier, guidelines, risk/pricing
│   │   ├── document_understanding.py    # OCR extraction
│   │   ├── data_acquisition.py          # Internal claims, external APIs, web research
│   │   └── communication.py             # Email drafts, decline letters, quote PDFs
│   ├── core/
│   │   └── state_manager.py             # State CRUD + audit trail + overrides
│   └── api/
│       └── handlers.py                  # FastAPI app factory
│
└── tests/
    └── test_all.py                      # 34 tests across all layers
```

---

## Architecture

### 3-Phase Workflow

```
Phase 1: Ingestion & Triage
  START -> Ingest & Classify (OCR + NAICS)
       -> Data Complete?
            ├── No  -> Draft Missing Info Email -> END
            └── Yes -> continue

Phase 2: Qualification
       -> Enrichment (3x data retrieval)
       -> Knockout Rules?
            ├── Fail -> Draft Decline Letter -> END
            └── Pass -> Risk Assessment -> continue

Phase 3: The Workbench (Human-in-the-Loop)
       -> Human Checkpoint (persists state)
       -> Human Decision?
            ├── Approve -> Generate Quote Package -> END
            ├── Decline -> Draft Decline Letter  -> END
            └── Modify  -> Update State -> loop back to Risk Assessment
```

### 4 Decision Outcomes

| Decision | When | Output |
|----------|------|--------|
| **QUOTED** | All rules pass, risk assessed, human approves | Quote PDF + email to broker |
| **DECLINED** | Hard rule fails or human declines | Decline letter citing specific rules |
| **MISSING_INFO** | Critical documents absent | Email requesting missing docs |
| **MANUAL_REVIEW** | Human selects Modify | Loops back for re-assessment |

---

## Agents

The system uses **5 specialized agents**, each mapped to specific nodes in the LangGraph workflow. Agents are logical roles — they share a single `UnderwritingState` (TypedDict) that flows through the graph.

### 1. Supervisor Agent

**File:** `src/orchestration/supervisor_agent.py` (class `SupervisorAgent`)

The top-level orchestrator and the only agent implemented as a standalone Python class. All other agents are logical groupings of LangGraph node functions.

- Instantiates the compiled LangGraph workflow at startup
- `process_submission()` is the single public entry point: creates initial state in the `StateManager`, builds the `UnderwritingState` input dict, calls `workflow.invoke()`, then syncs the final graph state back to persistence
- Handles exceptions and marks submissions as `FAILED` if the workflow errors

### 2. Classification Agent

**Graph node:** `ingest_and_classify`

Handles the first step of every submission: converting raw broker email + attachments into structured, machine-readable data.

- Combines email subject, body, and attachment content into a single document string
- Calls `extract_structured_data()` to extract applicant name, address, revenue, employees, coverage type, and submitted documents
- Calls `classify_naics_code()` to map the business description to a NAICS industry code (e.g., "Restaurant" -> `722110`)
- **Outputs:** `extracted_data`, `extraction_confidence`, `naics_code`, `classification_confidence`

### 3. Data Retrieval Agent

**Graph node:** `enrichment`

Pulls data from three independent sources to build a complete risk picture. In production these would run in parallel via `asyncio.gather()`.

- `internal_claims_history()` -- prior loss runs, total losses, loss ratio, policy history from internal CRM/claims systems
- `fetch_external_data()` -- credit score, financial health, property risk (flood zone, crime score, roof condition) from third-party bureaus (D&B, HazardHub)
- `web_research_applicant()` -- web presence verification, public reviews, health inspections, risk flags from open-source research
- **Outputs:** `internal_data`, `external_data`, `web_data`

### 4. Underwriting Analyst Agent

**Graph nodes:** `check_data_completeness`, `check_knockout_rules`, `risk_assessment`

The decision-making core. Handles three distinct steps:

1. **Data completeness check** -- verifies that all 3 required documents (application form, financial statements, loss history) are present. If missing, sets `decision=MISSING_INFO` and routes to the Broker Liaison Agent.

2. **Knockout rule validation** -- evaluates the submission against 4 hard underwriting rules using enriched data. If any rule fails, sets `decision=DECLINED` and routes to decline.

3. **Risk assessment & pricing** -- calculates a risk score (0-100) and annual premium using a formula-based approach:
   - Risk score: `50 + (loss_ratio * 100) + (crime_score * 0.2)`
   - Premium: `base_premium * credit_modifier * loss_modifier * size_modifier`
   - Where `base_premium = annual_revenue * 0.005`

### 5. Broker Liaison Agent

**Graph nodes:** `draft_missing_info`, `draft_decline`, `generate_quote`

Handles all outbound communications to the broker. Every drafted email has `ready_to_send: False` -- the human must explicitly send in production.

- `draft_missing_info_email()` -- professional email listing the specific missing documents
- `draft_decline_letter()` -- decline letter citing the exact rules that failed (by ID and reason)
- `draft_quote_email()` -- quote summary with premium, policy term, and PDF link
- `generate_quote_pdf()` -- produces a quote document (placeholder S3 URL in MVP)

---

## Tools

All 11 tools return a standardized `ToolResult(success: bool, data: dict, error: str | None)`. In the MVP, all tools return deterministic mock data. The tool interface is designed so that only the function body needs to change when swapping to real APIs -- the signature and return type stay the same.

### Document Understanding Tools

**File:** `src/tools/document_understanding.py`

| Tool | Description | MVP Behavior |
|------|-------------|-------------|
| `extract_structured_data(document_content, target_schema)` | Extract structured fields (name, address, revenue, employees, etc.) from submission text | Returns mock applicant data; confidence = 0.85 for docs >100 chars, 0.5 otherwise |

### Data Acquisition Tools

**File:** `src/tools/data_acquisition.py`

| Tool | Description | MVP Behavior |
|------|-------------|-------------|
| `internal_claims_history(applicant_id, applicant_name)` | Fetch prior loss runs from internal claims/CRM systems | Returns 2 mock loss runs, total_losses=$8,000, loss_ratio=0.016 |
| `fetch_external_data(applicant_name, applicant_address)` | Fetch credit score and property risk from third-party bureaus | Returns credit_score=720, flood_zone="X", crime_score=35 |
| `web_research_applicant(applicant_name, applicant_website)` | Research web presence, reviews, and risk flags | Returns website_verified=True, 4.5/5 stars, no risk flags |

### Decision Logic Tools

**File:** `src/tools/decision_logic.py`

| Tool | Description | MVP Behavior |
|------|-------------|-------------|
| `classify_naics_code(business_description, business_name)` | Classify business into NAICS industry code | Keyword-based mapping to 8 industry buckets |
| `validate_against_guidelines(extracted, enriched, web, internal)` | Check required documents + evaluate 4 hard knockout rules | Deterministic rule evaluation |
| `calculate_risk_and_price(extracted, external, internal)` | Calculate risk score (0-100) and annual premium | Formula-based calculation |

### Communication Tools

**File:** `src/tools/communication.py`

| Tool | Description | MVP Behavior |
|------|-------------|-------------|
| `draft_missing_info_email(broker_email, broker_name, applicant_name, missing_documents)` | Draft email requesting missing documents | f-string template listing missing docs |
| `draft_decline_letter(broker_email, broker_name, applicant_name, failed_rules)` | Draft decline letter citing specific failed rules | f-string template with rule citations |
| `draft_quote_email(broker_email, broker_name, applicant_name, quote_amount, policy_term, pdf_url)` | Draft email with quote summary | f-string template with quote details |
| `generate_quote_pdf(extracted_data, risk_metrics, quote_amount, applicant_name)` | Generate quote PDF document | Returns placeholder S3 URL |

---

## Underwriting Rules

The MVP enforces 4 hard knockout rules. If any rule fails, the submission is automatically declined.

| Rule ID | Name | Field | Comparison | Threshold |
|---------|------|-------|-----------|-----------|
| R001 | Minimum Credit Score | `credit_score` | >= | 500 |
| R002 | Maximum Loss Ratio | `loss_ratio` | < | 0.80 |
| R003 | Debt to Equity | `debt_to_equity` | < | 3.0 |
| R004 | Minimum Years in Business | `years_in_business` | >= | 2 |

**Required Documents:** `application_form`, `financial_statements`, `loss_history`

Rules are defined in the `UNDERWRITING_GUIDELINES` dict in `src/tools/decision_logic.py` and can be extended by appending to the `rules` list.

---

## State Management

**File:** `src/core/state_manager.py`

The `StateManager` class provides an in-memory state store (Python dict) for submission lifecycle tracking.

**Key data structures:**
- `SubmissionState` -- complete record: input fields, extraction results, enrichment data, risk metrics, decision, drafted communications, audit trail, and overrides
- `AuditEntry(timestamp, component, action, details, result, error)` -- immutable log of every agent/tool action
- `Override(timestamp, user_id, override_decision, override_reason, previous_decision)` -- record of human decision changes

**Status lifecycle:** `INGESTION -> EXTRACTION -> ENRICHMENT -> ANALYSIS -> DECISION -> COMPLETED` (or `FAILED`)

**Singleton access:** `get_state_manager()` returns the global instance, shared between the Supervisor Agent, Streamlit UI, and FastAPI endpoints.

---

## Workflow Graph

**File:** `src/orchestration/workflow.py`

The LangGraph `StateGraph` contains **10 nodes** and **3 conditional routing edges**:

| Node | Phase | Agent | Function |
|------|-------|-------|----------|
| `ingest_and_classify` | 1 | Classification | OCR extraction + NAICS classification |
| `check_data_completeness` | 1 | Underwriting Analyst | Validates required documents are present |
| `draft_missing_info` | 1 | Broker Liaison | Drafts missing-info email to broker |
| `enrichment` | 2 | Data Retrieval | Calls 3 data sources (internal, external, web) |
| `check_knockout_rules` | 2 | Underwriting Analyst | Evaluates 4 hard rules against enriched data |
| `risk_assessment` | 2 | Underwriting Analyst | Calculates risk score and premium |
| `human_checkpoint` | 3 | Supervisor | Passthrough; waits for human input via Streamlit |
| `generate_quote` | 3 | Broker Liaison | Creates quote PDF + email |
| `draft_decline` | 3 | Broker Liaison | Creates decline letter |
| `update_state` | 3 | Human | Applies override, loops back to `risk_assessment` |

**Conditional edges:**

| After Node | Condition Function | Routes |
|------------|-------------------|--------|
| `check_data_completeness` | `is_data_complete()` | `missing_docs` -> `draft_missing_info` / `data_complete` -> `enrichment` |
| `check_knockout_rules` | `knockout_check()` | `fail` -> `draft_decline` / `pass` -> `risk_assessment` |
| `human_checkpoint` | `human_decision()` | `approve` -> `generate_quote` / `decline` -> `draft_decline` / `modify` -> `update_state` |
