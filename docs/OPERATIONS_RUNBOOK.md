# Operations Runbook

How to set up, run, deploy, and troubleshoot the NorthStar Agentic Underwriting System.

---

## Table of Contents

1. [Local Development Setup](#1-local-development-setup)
2. [Running the System](#2-running-the-system)
3. [API Reference](#3-api-reference)
4. [Environment Variables](#4-environment-variables)
5. [AWS Deployment](#5-aws-deployment)
6. [Monitoring Checklist](#6-monitoring-checklist)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Local Development Setup

### Windows (Command Prompt)

```cmd
git clone <repo-url>
cd agentic_ai_groupwork

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
```

### Windows (PowerShell)

```powershell
git clone <repo-url>
cd agentic_ai_groupwork

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env
```

### macOS / Linux

```bash
git clone <repo-url>
cd agentic_ai_groupwork

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

> No API keys are needed for MVP testing. All external services return mock data.

### Optional: Install Graphviz (for workflow diagrams)

```bash
# Windows
winget install graphviz

# macOS
brew install graphviz

# Linux (Debian/Ubuntu)
sudo apt install graphviz
```

---

## 2. Running the System

### CLI Demo

```bash
python main.py
```

Runs a demo submission through the full LangGraph workflow. Expected output:

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

```bash
streamlit run app.py
```

Opens `http://localhost:8501` in your browser. If the port is in use:

```bash
streamlit run app.py --server.port 8502
```

### FastAPI Server

```bash
python main.py --server
```

Starts the API server at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### Tests

```bash
# All 36 tests
pytest tests/test_all.py -v

# With coverage
pytest tests/test_all.py --cov=src --cov-report=term-missing

# Specific category
pytest tests/test_all.py -k "EndToEnd" -v
pytest tests/test_all.py -k "DecisionTools" -v
```

---

## 3. API Reference

Base URL: `http://localhost:8000`

### POST /submit

Process a new insurance application.

**Request (macOS/Linux/Git Bash):**
```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "email_subject": "Application for Acme Restaurant",
    "email_body": "Full-service restaurant, 12 employees, $500K revenue",
    "broker_email": "broker@example.com",
    "broker_name": "John Smith"
  }'
```

**Request (Windows cmd):**
```cmd
curl -X POST http://localhost:8000/submit -H "Content-Type: application/json" -d "{\"email_subject\":\"Application for Acme Restaurant\",\"email_body\":\"Full-service restaurant\",\"broker_email\":\"broker@example.com\",\"broker_name\":\"John Smith\"}"
```

**Request (PowerShell):**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/submit -Method Post -ContentType "application/json" -Body '{"email_subject":"Application for Acme Restaurant","email_body":"Full-service restaurant","broker_email":"broker@example.com","broker_name":"John Smith"}'
```

**Response:**
```json
{
  "submission_id": "SUB-20260223-A1B2",
  "status": "COMPLETED",
  "decision": "QUOTED",
  "premium": 2800.0,
  "risk_score": 58.6
}
```

### POST /override

Apply a human override to an existing submission.

**Request:**
```bash
curl -X POST http://localhost:8000/override \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": "SUB-20260223-A1B2",
    "user_id": "underwriter-001",
    "override_decision": "DECLINED",
    "override_reason": "Failed post-quote inspection"
  }'
```

**Response:**
```json
{
  "submission_id": "SUB-20260223-A1B2",
  "new_decision": "DECLINED",
  "override_by": "underwriter-001"
}
```

### GET /status/{submission_id}

Query a specific submission.

```bash
curl http://localhost:8000/status/SUB-20260223-A1B2
```

### GET /status

List all submissions.

```bash
curl http://localhost:8000/status
```

### GET /health

Health check.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "agentic-underwriting-system"
}
```

---

## 4. Environment Variables

### MVP (no changes needed)

The `.env` file can be empty or contain defaults. All tools return mock data.

```
MOCK_EXTERNAL_APIS=true
STATE_BACKEND=memory
```

### Production

Fill in `.env` with real credentials. See `.env.example` for the full list (30+ variables):

```bash
# LLM
ANTHROPIC_API_KEY=sk-ant-...

# AWS
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=northstar-quotes

# External APIs
DNB_API_KEY=...
DNB_API_URL=https://plus.dnb.com
HAZARDHUB_API_KEY=...

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=underwriting@northstar.com

# State
STATE_BACKEND=dynamodb
DYNAMODB_TABLE=underwriting-submissions

# Disable mocks
MOCK_EXTERNAL_APIS=false
```

---

## 5. AWS Deployment

### Prerequisites

- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed

**Windows:**
```cmd
pip install aws-sam-cli
```

**macOS:**
```bash
brew tap aws/tap
brew install aws-sam-cli
```

**Linux:**
```bash
pip install aws-sam-cli
```

### Deploy

```bash
# Build
sam build

# Deploy (guided first time)
sam deploy --guided --stack-name agentic-underwriting-dev

# Subsequent deployments
sam deploy --stack-name agentic-underwriting-dev
```

### Get API Endpoints

```bash
aws cloudformation describe-stacks \
  --stack-name agentic-underwriting-dev \
  --query 'Stacks[0].Outputs' \
  --region us-east-1
```

### Monitor Lambda Logs

```bash
# Tail submission handler logs
aws logs tail /aws/lambda/submission-handler-dev --follow

# Tail override handler logs
aws logs tail /aws/lambda/override-handler-dev --follow
```

### Infrastructure

The SAM template (`infrastructure/sam_template.yaml`) creates:
- 3 Lambda functions (submission, override, query)
- API Gateway with 3 routes
- CloudWatch log groups (30-day retention)

---

## 6. Monitoring Checklist

| Check | Command | Expected |
|-------|---------|----------|
| All tests pass | `pytest tests/test_all.py -v` | 36 passed |
| Demo runs | `python main.py` | Decision: QUOTED |
| Streamlit loads | `streamlit run app.py` | Browser opens at :8501 |
| API health | `curl http://localhost:8000/health` | `{"status": "healthy"}` |
| Submit works | POST to `/submit` | Returns submission_id |
| Override works | POST to `/override` | Changes decision |
| Audit trail | Check Audit Trail tab in Streamlit | 7 entries for full workflow |

---

## 7. Troubleshooting

### Tests fail on import

Run from the project root directory:

```bash
cd agentic_ai_groupwork
pytest tests/test_all.py -v
```

### `ModuleNotFoundError: langgraph`

Install dependencies:

```bash
pip install langgraph langchain-core
```

Or reinstall all:

```bash
pip install -r requirements.txt
```

### Streamlit port already in use

```bash
streamlit run app.py --server.port 8502
```

### FastAPI port already in use

Kill the process using port 8000:

```bash
# macOS/Linux
lsof -i :8000 | grep LISTEN
kill <PID>

# Windows (cmd)
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Windows (PowerShell)
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

### Lambda timeout

Increase timeout in the SAM template or via CLI:

```bash
aws lambda update-function-configuration \
  --function-name submission-handler-dev \
  --timeout 60
```

### State lost between requests

**Expected for MVP.** The in-memory storage resets on restart. For persistence, set `STATE_BACKEND=dynamodb` in `.env` and configure AWS credentials.

### Streamlit state lost between browser refreshes

The `StateManager` instance is preserved in Streamlit's `session_state` within a single browser session. A full page refresh or new tab creates a new session. This is expected for the MVP.

### `graphviz` not rendering workflow diagrams

Install the Graphviz system package (not just the Python library):

```bash
# Windows
winget install graphviz

# macOS
brew install graphviz

# Linux
sudo apt install graphviz
```

Then restart Streamlit.

### Windows: `cp` command not found

Use the Windows-native copy command:

```cmd
copy .env.example .env
```

Or in PowerShell:

```powershell
Copy-Item .env.example .env
```

### Windows: `make` command not found

Either install Make via `winget install GnuWin32.Make`, use Git Bash, or use WSL. Alternatively, run the underlying commands directly:

```bash
# Instead of: make test
pytest tests/test_all.py -v

# Instead of: make demo
python main.py

# Instead of: make ui
streamlit run app.py

# Instead of: make server
python main.py --server
```
