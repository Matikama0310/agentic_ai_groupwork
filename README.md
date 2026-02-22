# NorthStar Insurance - Agentic Underwriting System

![Status](https://img.shields.io/badge/status-MVP-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![LangGraph](https://img.shields.io/badge/langgraph-0.2+-blue)
![Tests](https://img.shields.io/badge/tests-36%20passing-green)

## Overview

An **agentic AI system** for automated insurance underwriting built with **LangGraph StateGraph** and **Streamlit**. Processes insurance applications through a 3-phase workflow with human-in-the-loop decision making.

### Business Problem

NorthStar Insurance underwriters spend 40-65% of time on manual data gathering. This system automates the full pipeline while keeping humans in the loop for final decisions.

### Key Features

- **LangGraph StateGraph** with 10 nodes, 3 conditional edges, and loop-back support
- **4 Agent types**: Supervisor, Data Retrievers (3x parallel), Analysts, Broker Liaison
- **12 specialized tools** across 4 categories (document, data, decision, communication)
- **Streamlit Workbench** for human-in-the-loop review and override
- **FastAPI + Lambda** dual deployment (server or serverless)
- **36 tests** covering tools, state, workflow nodes, conditional edges, and end-to-end

---

## Quick Start

```bash
# 1. Setup
python -m venv venv
venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 2. Run demo (no API keys needed for MVP)
python main.py

# 3. Run Streamlit workbench
streamlit run app.py

# 4. Run tests
pytest tests/test_all.py -v

# 5. Start API server
python main.py --server
```

---

## Architecture

### 3-Phase Workflow (from diagram)

```
Phase 1: Ingestion & Triage
  Submission Received
    -> [Ingest & Classify] (OCR + LLM Schema Mapping)
    -> [Is Data Complete?]
        |-- Missing Critical Docs -> [Draft Missing Info Email] -> END (Wait for Reply)
        |-- Data Complete ---------->

Phase 2: Qualification
    -> [Hard Knock-out Rules?]
        |-- Fail (e.g. Roof > 20yr) -> [Draft Decline Letter] -> END (Auto-Decline)
        |-- Pass -> [Enrichment] (D&B / HazardHub APIs)
            -> [Risk Assessment] (RAG Search + Pricing Calc)

Phase 3: The Workbench
    -> [CHECKPOINT] (Persists State to DB)
    -> [Human Decision] (Via Streamlit)
        |-- Approve Quote -> [Generate Quote Pkg] (PDF Binder) -> END (Sent to Broker)
        |-- Decline       -> [Draft Decline Letter] -> END
        |-- Refer/Modify  -> [Update State] -> loops back to [Risk Assessment]
```

### Agents & Tools

| Agent | Role | Tools Used |
|-------|------|------------|
| **Supervisor Agent** | Orchestrates LangGraph workflow | State Manager |
| **Classification Agent** | OCR extraction + NAICS classification | `extract_structured_data`, `classify_naics_code` |
| **Data Retriever Agents** (3x parallel) | Internal claims, External bureaus, Web research | `internal_claims_history`, `fetch_external_data`, `web_research_applicant` |
| **Gap Analysis Agent** | Validates completeness + knockout rules | `validate_against_guidelines` |
| **Analyst Agent** | Risk scoring + premium calculation | `calculate_risk_and_price` |
| **Broker Liaison Agent** | Drafts all communications | `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf` |

### Key Components

| Component | File | Description |
|-----------|------|-------------|
| **LangGraph Workflow** | `src/orchestration/workflow.py` | 10-node StateGraph with conditional edges |
| **Supervisor Agent** | `src/orchestration/supervisor_agent.py` | Orchestrator wrapping the graph |
| **Document Tools** | `src/tools/document_understanding.py` | OCR extraction, image analysis |
| **Data Tools** | `src/tools/data_acquisition.py` | Internal, external, web data |
| **Decision Tools** | `src/tools/decision_logic.py` | Guidelines, risk scoring, NAICS |
| **Communication Tools** | `src/tools/communication.py` | Email drafts, quote PDFs |
| **State Manager** | `src/core/state_manager.py` | CRUD + audit trail + overrides |
| **API Handlers** | `src/api/handlers.py` | FastAPI app + Lambda handlers |
| **Streamlit UI** | `app.py` | Human-in-the-loop workbench |
| **Tests** | `tests/test_all.py` | 36 tests across all layers |

---

## Running the System

### CLI Demo
```bash
python main.py
# Runs a demo submission through the full LangGraph workflow
# Output: Decision, Premium, Risk Score, Audit Trail
```

### Streamlit Workbench
```bash
streamlit run app.py
# Opens browser with full underwriting workbench
# Submit applications, review decisions, apply overrides
```

### FastAPI Server
```bash
python main.py --server
# API docs at http://localhost:8000/docs
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/submit` | Process new application |
| POST | `/override` | Apply human override |
| GET | `/status/{id}` | Query submission |
| GET | `/status` | List all submissions |
| GET | `/health` | Health check |

---

## Testing

```bash
# Run all 36 tests
pytest tests/test_all.py -v

# With coverage
pytest tests/test_all.py --cov=src --cov-report=term-missing
```

### Test Categories

| Category | Count | What's Tested |
|----------|-------|---------------|
| Document Tools | 4 | OCR extraction, image analysis |
| Decision Tools | 4 | NAICS, guidelines, risk/pricing |
| Data Tools | 3 | Internal, external, web data |
| Communication Tools | 4 | Email drafts, PDF generation |
| State Manager | 7 | CRUD, audit, overrides |
| Workflow Nodes | 3 | Ingest, enrich, risk assessment |
| Conditional Edges | 6 | Data complete, knockout, human |
| End-to-End | 3 | Full workflow, performance, supervisor |
| **Total** | **36** | **All passing** |

---

## Configuration

The `.env` file contains all credentials. For **MVP testing, no credentials are needed** (uses mock data).

See `.env.example` for full list of configurable values including:
- LLM API keys (Anthropic, OpenAI)
- AWS credentials (S3, Lambda)
- Third-party APIs (D&B, HazardHub, Google Maps)
- Document AI (Azure, Textract)
- Email (SMTP, MS Graph)
- RAG (Pinecone, ChromaDB)

---

## Documentation

| Document | Purpose |
|----------|---------|
| [REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md) | File layout & module descriptions |
| [REQUIREMENTS_AND_ARCHITECTURE.md](docs/REQUIREMENTS_AND_ARCHITECTURE.md) | Detailed specs & design decisions |
| [TRACEABILITY_MATRIX.md](docs/TRACEABILITY_MATRIX.md) | Requirements -> Code -> Tests mapping |
| [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md) | How to use, extend, and troubleshoot |
| [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) | Deploy, monitor, operate |

---

**Last Updated:** February 22, 2026
**MVP Status:** All 36 tests passing, LangGraph workflow operational, Streamlit UI ready
