# Quick Start Guide

## 1. Setup

```bash
python -m venv venv
venv\Scripts\activate # or: source venv/bin/activate 
pip install -r requirements.txt  
cp .env.example .env
```

Edit `.env` with your Anthropic API key.

## 2. Run Tests

```bash
pytest tests/ -v
# or use make:
make test-coverage
```

## 3. Test Locally

```python
from src.api.handlers import SubmissionHandler

handler = SubmissionHandler()
result = handler.handle_submission({
    'email_subject': 'Test Application',
    'email_body': 'Applying for coverage...',
    'broker_email': 'broker@example.com',
    'broker_name': 'John'
})

print(f"Decision: {result['decision']}")
print(f"Premium: ${result['data']['risk_metrics']['annual_premium']}")
```

## 4. Deploy

```bash
sam build
sam deploy --stack-name agentic-underwriting-dev
```

## 5. Golden Test Cases

These cover the main workflows:

| Test | Scenario |
|------|----------|
| GTC-001 | Happy path (→ QUOTED) |
| GTC-002 | Missing documents (→ MISSING_INFO) |
| GTC-004 | Low confidence (→ MANUAL_REVIEW) |
| GTC-005 | Human override applied |
| GTC-007 | Parallel enrichment completes |

Run:
```bash
pytest tests/test_all.py::TestEndToEndWorkflow -v
```

## 6. Key Docs

- **README.md** - Overview & API reference
- **docs/REQUIREMENTS_AND_ARCHITECTURE.md** - Detailed specs
- **docs/IMPLEMENTATION_GUIDE.md** - How to use & extend
- **docs/OPERATIONS_RUNBOOK.md** - Deploy & operate

## 7. API Endpoints

```bash
# Submit
curl -X POST http://localhost/submit \
  -H "Content-Type: application/json" \
  -d '{"email_subject":"...","email_body":"...","broker_email":"..."}'

# Override
curl -X POST http://localhost/override \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"...","user_id":"...","override_decision":"QUOTED"}'

# Query status
curl -X GET "http://localhost/status?submission_id=..."
```

See README.md for full API documentation.
