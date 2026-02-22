# START HERE

## NorthStar Insurance - Agentic Underwriting System MVP

### What This System Does

Insurance submissions flow through a **LangGraph StateGraph** with **3 phases**:

```
Phase 1: Ingestion & Triage
  -> Ingest & Classify (OCR + NAICS) -> Is Data Complete?
     |-- Missing docs -> Draft missing info email -> END
     |-- Complete -> continue

Phase 2: Qualification
  -> Knockout Rules check -> Enrichment (D&B/HazardHub) -> Risk Assessment

Phase 3: The Workbench (Human-in-the-Loop via Streamlit)
  -> Approve Quote -> Generate PDF -> END
  -> Decline -> Draft letter -> END
  -> Modify -> loops back to Risk Assessment
```

**4 Outcomes:** QUOTED | DECLINED | MISSING_INFO | MANUAL_REVIEW

---

### Quick Commands

```bash
python main.py            # Run CLI demo (no API keys needed)
streamlit run app.py      # Launch Streamlit workbench
python main.py --server   # Start FastAPI server
pytest tests/test_all.py -v  # Run 36 tests
```

---

### Key Files

| File | What It Does |
|------|-------------|
| `main.py` | CLI entry point with demo and server modes |
| `app.py` | Streamlit workbench (Phase 3 human-in-the-loop) |
| `src/orchestration/workflow.py` | LangGraph StateGraph (10 nodes, 3 conditional edges) |
| `src/orchestration/supervisor_agent.py` | Supervisor Agent orchestrator |
| `src/tools/decision_logic.py` | NAICS classifier, guidelines validator, risk calculator |
| `src/tools/document_understanding.py` | OCR extraction, image analysis |
| `src/tools/data_acquisition.py` | Internal claims, external bureaus, web research |
| `src/tools/communication.py` | Email drafts, decline letters, quote PDFs |
| `src/core/state_manager.py` | State CRUD + audit trail + overrides |
| `src/api/handlers.py` | FastAPI app + Lambda-compatible handlers |
| `tests/test_all.py` | 36 tests across all layers |
| `.env` | All credentials (30+ variables, fill for production) |

---

### Documentation Roadmap

| Time | Read | Purpose |
|------|------|---------|
| 5 min | [QUICKSTART.md](QUICKSTART.md) | Get it running |
| 10 min | [README.md](README.md) | Architecture & API reference |
| 15 min | [REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md) | Understand file layout |
| 30 min | [REQUIREMENTS_AND_ARCHITECTURE.md](docs/REQUIREMENTS_AND_ARCHITECTURE.md) | Detailed specs |
| 30 min | [TRACEABILITY_MATRIX.md](docs/TRACEABILITY_MATRIX.md) | FR/NFR -> Code mapping |
| 30 min | [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md) | How to extend |
| 30 min | [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) | Deploy & operate |

---

### What's Implemented

- [x] LangGraph StateGraph with 10 nodes and 3 conditional edges
- [x] 12 tools across 4 modules (document, data, decision, communication)
- [x] 4 agent types (Supervisor, Data Retrievers, Analysts, Broker Liaison)
- [x] Streamlit workbench with human-in-the-loop override
- [x] FastAPI server with 5 endpoints
- [x] State management with audit trail and override support
- [x] 36 tests all passing
- [x] .env with 30+ credential placeholders
- [x] AWS Lambda deployment template

### MVP Stubs (Mock Data)

- [ ] Real LLM calls (currently rule-based extraction)
- [ ] Real external APIs (currently return mock data)
- [ ] Real PDF generation (currently placeholder S3 URLs)
- [ ] Real email sending (currently draft-only)
- [ ] DynamoDB persistence (currently in-memory)

---

**Next Step:** Run `python main.py` to see it work, then `streamlit run app.py` for the full workbench.
