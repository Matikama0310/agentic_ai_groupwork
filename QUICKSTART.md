# Quick Start Guide

## 1. Setup

```bash
python -m venv venv
venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

No API keys needed for MVP testing (uses mock data).

## 2. Run Demo

```bash
python main.py
```

Expected output:
```
NorthStar Insurance - Agentic Underwriting System (MVP Demo)
[1/3] Submitting application: DEMO-20260222-...
[2/3] Processing complete!
      Decision: QUOTED
      Premium:  $2,800.00
      Risk:     58.6/100
[3/3] Audit Trail (7 entries)
```

## 3. Run Tests

```bash
pytest tests/test_all.py -v
# Expected: 36 passed
```

## 4. Launch Streamlit Workbench

```bash
streamlit run app.py
```

This opens the human-in-the-loop UI where you can:
- Submit new applications via the sidebar
- Review extracted data, risk metrics, drafted emails
- Apply human overrides (approve/decline/modify)
- View the full audit trail

## 5. Start API Server

```bash
python main.py --server
# Docs: http://localhost:8000/docs
```

## 6. API Endpoints

```bash
# Submit application
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"email_subject":"Test App","email_body":"Restaurant application...","broker_email":"broker@example.com","broker_name":"John"}'

# Override decision
curl -X POST http://localhost:8000/override \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"SUB-...","user_id":"underwriter-001","override_decision":"DECLINED","override_reason":"Failed inspection"}'

# Query status
curl http://localhost:8000/status/SUB-...

# Health check
curl http://localhost:8000/health
```

## 7. Key Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point (demo + server) |
| `app.py` | Streamlit workbench |
| `src/orchestration/workflow.py` | LangGraph StateGraph |
| `src/tools/` | 12 tools in 4 modules |
| `tests/test_all.py` | 36 tests |
| `.env` | Credentials (fill for production) |

## 8. Key Docs

- **[README.md](README.md)** - Architecture & API reference
- **[docs/REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md)** - File layout
- **[docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** - How to extend
- **[docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md)** - Deploy & operate
