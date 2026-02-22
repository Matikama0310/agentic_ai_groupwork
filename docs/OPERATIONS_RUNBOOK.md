# FILE: docs/OPERATIONS_RUNBOOK.md
# Operations Runbook

## Table of Contents
1. [Local Development](#local-development)
2. [Testing](#testing)
3. [Deployment](#deployment)
4. [Monitoring & Logging](#monitoring--logging)
5. [Troubleshooting](#troubleshooting)
6. [Common Failure Modes](#common-failure-modes)

---

## Local Development

### Prerequisites
- Python 3.12+
- AWS CLI v2 configured
- Git

### Setup

```bash
# Clone repository
git clone <repo-url>
cd agentic-underwriting-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your settings
# ANTHROPIC_API_KEY=sk-...
# MOCK_EXTERNAL_APIS=true
# LOG_LEVEL=INFO
```

### Running Locally

```bash
# Option 1: Direct Python invocation
python -c "
from src.orchestration.supervisor_agent import SupervisorAgent
from src.api.handlers import SubmissionHandler

handler = SubmissionHandler()
result = handler.handle_submission({
    'email_subject': 'Test Application',
    'email_body': 'Please review this application...',
    'broker_email': 'broker@example.com',
    'broker_name': 'John Broker',
    'attachments': []
})
print(result)
"

# Option 2: Use test script
python scripts/test_local.sh

# Option 3: Run FastAPI server (when implemented)
# uvicorn src.api.main:app --reload
```

### IDE Setup
- VSCode: Install Python, Pylance extensions
- PyCharm: Mark `src/` as Sources Root
- Use pytest for test discovery

---

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_tools.py -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html
# View coverage report: open htmlcov/index.html

# Run single test function
pytest tests/unit/test_tools.py::TestDocumentTools::test_extract_structured_data_success -v
```

### Integration Tests

```bash
# Run integration tests (end-to-end workflow)
pytest tests/integration/ -v

# Run with detailed output
pytest tests/integration/test_submission_flow.py -v -s

# Run specific scenario
pytest tests/integration/test_submission_flow.py::TestEndToEndWorkflow::test_happy_path_quoted -v
```

### Performance Tests

```bash
# Run latency tests
pytest tests/performance/test_latency.py -v

# Test with profiling
pytest tests/performance/test_latency.py --profile
```

### Test Coverage Target

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80

# Expected output: coverage >= 80%
```

### Golden Test Cases

Golden test cases validate end-to-end behavior:

| Test ID | Scenario | Command |
|---------|----------|---------|
| GTC-001 | Happy path (quote) | `pytest tests/integration/test_submission_flow.py::TestEndToEndWorkflow::test_happy_path_quoted` |
| GTC-002 | Missing docs | `pytest tests/integration/test_submission_flow.py::TestEndToEndWorkflow::test_missing_critical_docs` |
| GTC-003 | Failed rules | Manual test (requires mock data setup) |
| GTC-004 | Low confidence | `pytest tests/integration/test_submission_flow.py::TestEndToEndWorkflow::test_low_confidence_extraction` |
| GTC-005 | Human override | `pytest tests/unit/test_state_manager.py::TestStateManager::test_apply_override` |
| GTC-007 | Parallel execution | `pytest tests/integration/test_submission_flow.py::TestEndToEndWorkflow::test_parallel_data_retrieval_completes` |

---

## Deployment

### Prerequisites

- AWS account with appropriate permissions
- AWS CLI configured: `aws configure`
- AWS SAM CLI: `pip install aws-sam-cli`

### Pre-Deployment Checklist

```bash
# 1. Run full test suite
make test

# 2. Verify coverage
make test-coverage

# 3. Check for hardcoded secrets
grep -r "ANTHROPIC_API_KEY\|password\|secret" src/ --exclude-dir=.git

# 4. Lint code
pylint src/ --disable=C0114,C0115

# 5. Build artifacts
sam build

# 6. Validate template
sam validate --template template.yaml
```

### Deployment Steps

#### Option A: Using SAM (Recommended)

```bash
# 1. Build
sam build

# 2. Package (creates S3 bucket for code)
sam package \
  --output-template-file packaged.yaml \
  --s3-bucket my-sam-bucket-<region>-<account>

# 3. Deploy to DEV
sam deploy \
  --template-file packaged.yaml \
  --stack-name agentic-underwriting-dev \
  --parameter-overrides \
      Environment=dev \
      ANTHROPICAPIKey=sk-xxx \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# 4. Deploy to PROD (with approval)
sam deploy \
  --template-file packaged.yaml \
  --stack-name agentic-underwriting-prod \
  --parameter-overrides \
      Environment=prod \
      ANTHROPICAPIKey=sk-yyy \
  --capabilities CAPABILITY_IAM \
  --confirm-changeset
```

#### Option B: Using CloudFormation directly

```bash
# Create stack
aws cloudformation create-stack \
  --stack-name agentic-underwriting-dev \
  --template-body file://infrastructure/cloudformation_stack.yaml \
  --parameters \
      ParameterKey=Environment,ParameterValue=dev \
      ParameterKey=ANTHROPICAPIKey,ParameterValue=sk-xxx \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Monitor stack creation
aws cloudformation wait stack-create-complete \
  --stack-name agentic-underwriting-dev \
  --region us-east-1
```

### Post-Deployment Verification

```bash
# 1. Get Lambda function ARN
aws lambda get-function --function-name submission-handler-dev

# 2. Test submission endpoint
aws lambda invoke \
  --function-name submission-handler-dev \
  --payload '{"email_subject":"Test","email_body":"Body","broker_email":"test@example.com","broker_name":"Test"}' \
  response.json
cat response.json

# 3. Check CloudWatch logs
aws logs tail /aws/lambda/submission-handler-dev --follow

# 4. Monitor API Gateway
aws apigateway get-stages \
  --rest-api-id <api-id>
```

### Rollback

```bash
# If deployment fails, rollback to previous version
aws cloudformation cancel-update-stack \
  --stack-name agentic-underwriting-dev \
  --region us-east-1

# Or restore from previous template
aws cloudformation update-stack \
  --stack-name agentic-underwriting-dev \
  --template-body file://infrastructure/cloudformation_stack_v1.yaml \
  --region us-east-1
```

---

## Monitoring & Logging

### CloudWatch Logs

```bash
# Stream logs for submission handler
aws logs tail /aws/lambda/submission-handler-dev --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/submission-handler-dev \
  --filter-pattern "ERROR"

# Get logs for specific submission
aws logs filter-log-events \
  --log-group-name /aws/lambda/submission-handler-dev \
  --filter-pattern "SUB-20260222-123456"
```

### CloudWatch Metrics

Expected custom metrics (MVP doesn't emit yet):
- `SubmissionCount` (Per minute)
- `AverageProcessingTime` (Seconds)
- `DecisionDistribution` (QUOTED, DECLINED, MISSING_INFO)
- `ErrorRate` (Percentage)

### X-Ray Tracing (Optional)

```bash
# View service map
aws xray get-service-graph \
  --start-time 2026-02-22T00:00:00Z \
  --end-time 2026-02-22T23:59:59Z

# Get trace details
aws xray get-trace-summaries \
  --start-time 2026-02-22T00:00:00Z \
  --filtering-expression "service(\"submission-handler\")"
```

### Local Log Viewing

```bash
# View logs directory (when running locally)
tail -f /tmp/agentic-underwriting.log

# Search logs
grep "ERROR\|WARNING" /tmp/agentic-underwriting.log
grep "SUB-20260222" /tmp/agentic-underwriting.log
```

---

## Troubleshooting

### Issue: "Lambda Timeout" (30s limit exceeded)

**Cause:** Enrichment phase taking too long  
**Solution:**
1. Check external API calls: Do they timeout?
2. Increase Lambda timeout: 60 seconds recommended
3. Implement caching for external data

```bash
# Update Lambda timeout
aws lambda update-function-configuration \
  --function-name submission-handler-dev \
  --timeout 60
```

### Issue: "State not found" error in override handler

**Cause:** Submission ID doesn't exist or state expired  
**Solution:**
1. Verify submission_id is correct
2. For MVP (in-memory state), state is lost on Lambda restart
3. Migrate to DynamoDB for persistence

```bash
# Check if submission exists
curl -X POST https://api-gateway-url/query \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"SUB-20260222-123456"}'
```

### Issue: "Low extraction confidence" (< 0.5)

**Cause:** Document quality too poor  
**Solution:**
1. Request better quality scan from broker
2. Manually extract and resubmit via API
3. Lower confidence threshold (if acceptable risk)

### Issue: "API rate limit exceeded"

**Cause:** External API calls hitting rate limits  
**Solution:**
1. Implement request batching
2. Add exponential backoff retries (already implemented)
3. Request higher rate limit from provider
4. Use different data provider

---

## Common Failure Modes

### Failure Mode 1: External API Unavailable

| Symptom | Root Cause | Handling |
|---------|-----------|----------|
| `fetch_external_data` returns null | D&B/HazardHub API down | Graceful degradation; log warning; proceed with internal data |
| Enrichment phase slow (10+ seconds) | Network timeout | Retry 2x with backoff; fail fast after timeout |

**Recovery:**
```python
# Tools already implement fallback behavior
# But you can manually retry:
aws lambda invoke \
  --function-name override-handler-dev \
  --payload '{"submission_id":"SUB-xxx","user_id":"manual","override_decision":"QUOTED","override_reason":"API recovery"}' \
  response.json
```

### Failure Mode 2: Guidelines Config Missing

| Symptom | Root Cause | Handling |
|---------|-----------|----------|
| `GuidelinesNotFoundError` | Config file not loaded | System halts; requires restart |

**Prevention:**
- Load guidelines at Lambda cold start (not in handler)
- Validate guidelines config on deployment
- Use parameter store instead of file

### Failure Mode 3: Invalid Submission Input

| Symptom | Root Cause | Handling |
|---------|-----------|----------|
| 400 error, "Missing required fields" | Client didn't provide email_subject, email_body, broker_email | Return clear error message; client retries |

**Client Guidance:**
```json
// Required fields:
{
  "email_subject": "string (required)",
  "email_body": "string (required)",
  "broker_email": "string (required)",
  "broker_name": "string (optional)",
  "attachments": "array[{filename, content, type}] (optional)"
}
```

### Failure Mode 4: Human Override with Invalid Decision

| Symptom | Root Cause | Handling |
|---------|-----------|----------|
| 400 error, "Invalid override_decision" | Client sent "APPROVED" instead of "QUOTED" | Reject; list valid values |

**Valid Decisions:** QUOTED, DECLINED, MISSING_INFO, MANUAL_REVIEW

---

## Quick Reference

### Common Commands

```bash
# Test locally
make test

# Deploy to DEV
make deploy ENV=dev

# View logs
make logs ENV=dev

# Run integration test
make test-integration

# Check coverage
make test-coverage

# Generate fixture data
python scripts/generate_fixtures.py
```

### Environment Variables (Required)

```bash
ANTHROPIC_API_KEY          # Required for Claude API calls
AWS_REGION                 # AWS region (default: us-east-1)
MOCK_EXTERNAL_APIS         # true for MVP (default: true)
LOG_LEVEL                  # DEBUG, INFO, WARNING, ERROR (default: INFO)
SUBMISSION_TIMEOUT_SECONDS # Max processing time (default: 30)
```

### Key File Locations

```
- Lambda handlers: lambda/
- Core logic: src/
- Tests: tests/
- Infrastructure: infrastructure/
- Docs: docs/
```

---

## END OF RUNBOOK
