# Operations Runbook

## NorthStar Agentic Underwriting System

---

## 1. Local Development

### Setup
```bash
# Clone repository
git clone <repo-url>
cd agentic-underwriting-system

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Linux/Mac: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed (MVP works without any changes)
```

### Running

| Command | Purpose |
|---------|---------|
| `python main.py` | Run CLI demo |
| `streamlit run app.py` | Launch Streamlit workbench |
| `python main.py --server` | Start FastAPI server on port 8000 |

### Testing

```bash
# Run all 36 tests
pytest tests/test_all.py -v

# With coverage report
pytest tests/test_all.py --cov=src --cov-report=term-missing

# Run specific test class
pytest tests/test_all.py::TestEndToEnd -v
pytest tests/test_all.py::TestDecisionTools -v
pytest tests/test_all.py::TestWorkflowNodes -v
pytest tests/test_all.py::TestConditionalEdges -v

# Run single test
pytest tests/test_all.py::TestEndToEnd::test_full_workflow_quoted -v -s
```

---

## 2. Project Structure

```
main.py                              # CLI entry point
app.py                               # Streamlit workbench
src/orchestration/workflow.py         # LangGraph StateGraph (core)
src/orchestration/supervisor_agent.py # Supervisor orchestrator
src/tools/decision_logic.py           # NAICS, guidelines, risk
src/tools/document_understanding.py   # OCR, image analysis
src/tools/data_acquisition.py         # Internal, external, web data
src/tools/communication.py            # Emails, PDFs
src/core/state_manager.py             # State + audit + overrides
src/api/handlers.py                   # FastAPI + Lambda handlers
tests/test_all.py                     # 36 tests
.env                                  # Credentials
```

---

## 3. API Server

### Start
```bash
python main.py --server
# Swagger docs: http://localhost:8000/docs
```

### Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Submit application
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "email_subject": "Application for Acme Restaurant",
    "email_body": "Full-service restaurant, 12 employees, $500K revenue",
    "broker_email": "broker@example.com",
    "broker_name": "John Smith"
  }'

# Query status
curl http://localhost:8000/status/{submission_id}

# List all submissions
curl http://localhost:8000/status

# Apply override
curl -X POST http://localhost:8000/override \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": "SUB-...",
    "user_id": "underwriter-001",
    "override_decision": "DECLINED",
    "override_reason": "Failed post-quote inspection"
  }'
```

---

## 4. AWS Deployment

### Prerequisites
- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed (`pip install aws-sam-cli`)

### Deploy
```bash
# Build
sam build

# Deploy to dev
sam deploy --stack-name agentic-underwriting-dev

# Get API endpoint
aws cloudformation describe-stacks \
  --stack-name agentic-underwriting-dev \
  --query 'Stacks[0].Outputs' \
  --region us-east-1
```

### Monitor
```bash
# View Lambda logs
aws logs tail /aws/lambda/submission-handler-dev --follow

# Check Lambda function
aws lambda get-function --function-name submission-handler-dev
```

---

## 5. Environment Variables

### MVP (no changes needed)
```
MOCK_EXTERNAL_APIS=true
STATE_BACKEND=memory
```

### Production (fill in .env)
```
ANTHROPIC_API_KEY=sk-ant-...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
DNB_API_KEY=...
HAZARDHUB_API_KEY=...
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=...
SMTP_PASSWORD=...
MOCK_EXTERNAL_APIS=false
STATE_BACKEND=dynamodb
```

See `.env.example` for the complete list (30+ variables).

---

## 6. Troubleshooting

### Problem: Tests fail on import
**Solution:** Run from project root directory
```bash
cd agentic-underwriting-system
pytest tests/test_all.py -v
```

### Problem: LangGraph not found
**Solution:** Install dependencies
```bash
pip install langgraph langchain-core
```

### Problem: Streamlit port in use
**Solution:** Use different port
```bash
streamlit run app.py --server.port 8502
```

### Problem: Lambda timeout
**Solution:** Increase timeout
```bash
aws lambda update-function-configuration \
  --function-name submission-handler-dev \
  --timeout 60
```

### Problem: State lost between requests
**Expected for MVP** (in-memory storage). For persistence, set `STATE_BACKEND=dynamodb` and configure AWS credentials.

---

## 7. Monitoring Checklist

- [ ] All 36 tests passing (`pytest tests/test_all.py -v`)
- [ ] Demo runs successfully (`python main.py`)
- [ ] Streamlit workbench loads (`streamlit run app.py`)
- [ ] API health check passes (`curl http://localhost:8000/health`)
- [ ] Submission returns QUOTED decision
- [ ] Override changes decision correctly
- [ ] Audit trail captures all 7 workflow steps
