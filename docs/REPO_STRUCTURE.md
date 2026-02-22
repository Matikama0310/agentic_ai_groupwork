# Repository Structure

```
agentic-underwriting-system/
|
|-- main.py                           # CLI entry point (demo + server modes)
|-- app.py                            # Streamlit workbench (human-in-the-loop UI)
|-- requirements.txt                  # Python dependencies
|-- pyproject.toml                    # Project configuration
|-- Makefile                          # Build automation
|-- .env                              # Environment credentials (not committed)
|-- .env.example                      # Environment template (30+ variables)
|-- .gitignore
|-- README.md                         # Overview, architecture, quick start
|-- QUICKSTART.md                     # 5-minute setup guide
|-- START_HERE.md                     # Documentation roadmap
|-- DELIVERABLES.md                   # Deliverables summary
|
|-- src/                              # CORE APPLICATION
|   |-- __init__.py
|   |
|   |-- core/
|   |   |-- __init__.py
|   |   |-- state_manager.py          # State CRUD + audit trail + overrides (350 lines)
|   |
|   |-- tools/                        # 12 tools in 4 categories
|   |   |-- __init__.py               # Re-exports all tools
|   |   |-- decision_logic.py         # ToolResult, NAICS classifier, guidelines validator, risk calculator
|   |   |-- document_understanding.py # OCR extraction, image hazard analysis
|   |   |-- data_acquisition.py       # Internal claims, external bureaus, web research
|   |   |-- communication.py          # Email drafts, decline letters, quote PDFs
|   |   |-- all_tools.py              # (Legacy) original monolithic tools file
|   |
|   |-- orchestration/
|   |   |-- __init__.py
|   |   |-- workflow.py               # LangGraph StateGraph (10 nodes, 3 conditional edges)
|   |   |-- supervisor_agent.py       # SupervisorAgent wrapping the LangGraph workflow
|   |
|   |-- api/
|       |-- __init__.py
|       |-- handlers.py               # FastAPI app factory + Lambda-compatible handlers
|
|-- lambda/                           # AWS Lambda entry points
|   |-- __init__.py
|   |-- submission_handler.py         # POST /submit
|   |-- override_handler.py           # POST /override
|   |-- query_handler.py              # GET /status
|
|-- tests/
|   |-- __init__.py
|   |-- test_all.py                   # 36 tests: tools, state, workflow, E2E
|
|-- docs/
|   |-- REPO_STRUCTURE.md             # This file
|   |-- REQUIREMENTS_AND_ARCHITECTURE.md
|   |-- TRACEABILITY_MATRIX.md
|   |-- IMPLEMENTATION_GUIDE.md
|   |-- OPERATIONS_RUNBOOK.md
|
|-- infrastructure/
|   |-- sam_template.yaml             # AWS SAM deployment template
|
|-- config/
    |-- config.txt                    # Configuration examples
```

---

## Module Descriptions

### `src/orchestration/workflow.py` (Core - LangGraph)
The heart of the system. Defines a `StateGraph` with:
- **10 nodes**: `ingest_and_classify`, `check_data_completeness`, `draft_missing_info`, `enrichment`, `check_knockout_rules`, `risk_assessment`, `human_checkpoint`, `generate_quote`, `draft_decline`, `update_state`
- **3 conditional edges**: `is_data_complete`, `knockout_check`, `human_decision`
- **1 loop-back**: `update_state` -> `risk_assessment` (when human selects Modify)

### `src/orchestration/supervisor_agent.py` (Orchestrator)
Wraps the LangGraph workflow. Handles:
- Creating initial state in the persistence layer
- Invoking the compiled workflow
- Syncing final graph state back to the database
- Audit trail synchronization

### `src/tools/` (4 Tool Modules)
| Module | Tools | Agent |
|--------|-------|-------|
| `decision_logic.py` | `classify_naics_code`, `validate_against_guidelines`, `calculate_risk_and_price` | Analyst |
| `document_understanding.py` | `extract_structured_data`, `analyze_image_hazards` | Classification |
| `data_acquisition.py` | `internal_claims_history`, `fetch_external_data`, `web_research_applicant` | Data Retriever |
| `communication.py` | `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf` | Broker Liaison |

### `src/core/state_manager.py` (Persistence)
- `SubmissionState` dataclass with full lifecycle fields
- `StateManager` singleton with CRUD, audit entries, overrides
- In-memory backend (MVP); DynamoDB-ready interface

### `src/api/handlers.py` (API Layer)
- `create_app()` FastAPI factory with 5 endpoints
- `SubmissionHandler`, `OverrideHandler`, `QueryHandler` for Lambda compatibility

### `app.py` (Streamlit UI)
Human-in-the-loop workbench with 6 tabs:
- Overview, Extracted Data, Risk Assessment, Drafted Email, Audit Trail, Human Override

---

## Dependencies

**Core:** `langgraph>=0.2.0`, `langchain-core>=0.3.0`, `anthropic>=0.7.0`
**Web:** `fastapi>=0.100.0`, `uvicorn>=0.23.0`, `pydantic>=2.0.0`
**UI:** `streamlit>=1.30.0`
**AWS:** `boto3>=1.26.0`
**Utilities:** `python-dotenv>=1.0.0`, `structlog>=22.0.0`, `tenacity>=8.0.0`
**Testing:** `pytest>=7.0.0`, `pytest-cov>=4.0.0`, `pytest-asyncio>=0.20.0`
