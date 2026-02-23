# NorthStar Insurance - Agentic Underwriting System

![Status](https://img.shields.io/badge/status-MVP-green)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![LangGraph](https://img.shields.io/badge/langgraph-0.2+-blue)
![Tests](https://img.shields.io/badge/tests-36_passing-green)

An **agentic AI system** for automated insurance underwriting built with **LangGraph StateGraph** and **Streamlit**. Insurance applications flow through a 3-phase workflow (Ingestion, Qualification, Human Review) powered by 5 specialized agents and 12 tools, with human-in-the-loop decision making via a Streamlit workbench.

**Business Problem:** NorthStar Insurance underwriters spend 40-65% of their time on manual data gathering. This system automates the full pipeline while keeping humans in the loop for final decisions.

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

### 4. Configure environment

**Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

> No API keys are needed for MVP testing. All external services use mock data. See [PRODUCTION_CONSIDERATIONS.md](docs/PRODUCTION_CONSIDERATIONS.md) for what's needed to go live.

---

## Running the System

| Mode | Command | Description |
|------|---------|-------------|
| CLI Demo | `python main.py` | Runs one submission through the full workflow |
| Streamlit UI | `streamlit run app.py` | Human-in-the-loop workbench (submit, review, override) |
| API Server | `python main.py --server` | FastAPI REST API at `http://localhost:8000/docs` |
| Tests | `pytest tests/test_all.py -v` | All 36 tests (runs in < 1 second) |

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
# Run all 36 tests
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
| Document Tools | 4 | OCR extraction, image analysis |
| Decision Tools | 4 | NAICS classification, guidelines, risk/pricing |
| Data Tools | 3 | Internal claims, external bureaus, web research |
| Communication Tools | 4 | Email drafts, decline letters, PDF generation |
| State Manager | 7 | CRUD, audit trail, overrides |
| Workflow Nodes | 3 | Ingest, enrich, risk assessment nodes |
| Conditional Edges | 6 | Data completeness, knockout, human decision |
| End-to-End | 3 | Full workflow, performance, supervisor integration |
| **Total** | **36** | **All passing** |

---

## Project Structure

```
agentic_ai_groupwork/
├── main.py                              # CLI entry point (demo + server modes)
├── app.py                               # Streamlit workbench (human-in-the-loop UI)
├── requirements.txt                     # Python dependencies
├── pyproject.toml                       # Project config (pytest, black, isort)
├── Makefile                             # Build automation shortcuts
├── .env.example                         # Environment variable template
│
├── src/
│   ├── orchestration/
│   │   ├── workflow.py                  # LangGraph StateGraph (10 nodes, 3 edges)
│   │   └── supervisor_agent.py          # Supervisor agent orchestrator
│   ├── tools/
│   │   ├── decision_logic.py            # NAICS classifier, guidelines, risk/pricing
│   │   ├── document_understanding.py    # OCR extraction, image hazard analysis
│   │   ├── data_acquisition.py          # Internal claims, external APIs, web research
│   │   └── communication.py             # Email drafts, decline letters, quote PDFs
│   ├── core/
│   │   └── state_manager.py             # State CRUD + audit trail + overrides
│   └── api/
│       └── handlers.py                  # FastAPI app factory + Lambda handlers
│
├── lambda/                              # AWS Lambda entry points
│   ├── submission_handler.py            # POST /submit
│   ├── override_handler.py              # POST /override
│   └── query_handler.py                 # GET /status
│
├── tests/
│   └── test_all.py                      # 36 tests across all layers
│
├── docs/
│   ├── ARCHITECTURE.md                  # Workflow, agents, tools, state, traceability
│   ├── IMPLEMENTATION_GUIDE.md          # Mock vs production, how to extend, testing
│   ├── OPERATIONS_RUNBOOK.md            # Deployment, API reference, troubleshooting
│   └── PRODUCTION_CONSIDERATIONS.md     # What's needed for real deployment
│
├── infrastructure/
│   └── sam_template.yaml                # AWS SAM template (3 Lambda + API Gateway)
│
└── config/
    └── config.txt                       # Configuration reference
```

---

## Architecture at a Glance

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

### 5 Agents, 12 Tools

| Agent | Role | Tools |
|-------|------|-------|
| **Supervisor** | Orchestrates LangGraph workflow | State Manager |
| **Classification** | OCR extraction + NAICS classification | `extract_structured_data`, `classify_naics_code` |
| **Data Retrieval** | Parallel data acquisition (internal, external, web) | `internal_claims_history`, `fetch_external_data`, `web_research_applicant` |
| **Underwriting Analyst** | Data completeness, knockout rules, risk scoring + pricing | `validate_against_guidelines`, `calculate_risk_and_price` |
| **Broker Liaison** | Drafts all broker communications | `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf` |

### 4 Decision Outcomes

| Decision | When | Output |
|----------|------|--------|
| **QUOTED** | All rules pass, risk assessed, human approves | Quote PDF + email to broker |
| **DECLINED** | Hard rule fails or human declines | Decline letter citing specific rules |
| **MISSING_INFO** | Critical documents absent | Email requesting missing docs |
| **MANUAL_REVIEW** | Human selects Modify | Loops back for re-assessment |

---

## Configuration

The `.env` file holds all credentials. **For MVP, no configuration is needed** (all external services return mock data).

For production, fill in `.env` with real API keys. See `.env.example` for the full list (30+ variables) organized by service:
- LLM (Anthropic, OpenAI)
- AWS (S3, Lambda, DynamoDB)
- Third-party APIs (D&B, HazardHub, Google Maps)
- Document AI (Azure, AWS Textract)
- Email (SMTP, MS Graph)
- RAG (Pinecone, ChromaDB)

---

## Documentation

| Document | What You'll Learn |
|----------|-------------------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | How the workflow, agents, tools, and state management work together. Includes traceability matrix (requirements to code to tests). |
| **[IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** | What's mock vs production, how to swap to real APIs, how to add tools/nodes/rules, testing strategy. |
| **[OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md)** | API reference with curl examples, AWS deployment, monitoring, troubleshooting. |
| **[PRODUCTION_CONSIDERATIONS.md](docs/PRODUCTION_CONSIDERATIONS.md)** | Everything needed to move from MVP to real deployment: LLM integration, APIs, infrastructure, costs, testing. |
