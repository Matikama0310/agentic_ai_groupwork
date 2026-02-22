# Repository Structure

```
agentic-underwriting-system/
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Environment configuration
│   │   ├── guidelines.json          # Underwriting rules (RAG knowledge base)
│   │   └── prompts.yaml             # LLM prompt templates
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── submission_processor.py  # Email/file parsing
│   │   ├── state_manager.py         # State CRUD + overrides
│   │   ├── audit_logger.py          # Audit trail
│   │   └── errors.py                # Exception classes
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base_tool.py             # Abstract tool class
│   │   ├── data_tools.py            # Data acquisition tools
│   │   ├── document_tools.py        # Document understanding tools
│   │   ├── decision_tools.py        # Decision & logic tools
│   │   ├── comms_tools.py           # Communication tools
│   │   └── output_tools.py          # Output generation tools
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py            # Abstract agent class
│   │   ├── classification_agent.py  # Classification agent
│   │   ├── analyst_agent.py         # Gap analysis + risk assessment
│   │   ├── data_retriever_agent.py  # Parallel data retrieval
│   │   ├── broker_liaison_agent.py  # Email/communication
│   │   └── output_agent.py          # Quote generation
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── supervisor_agent.py      # LanGraph workflow definition
│   │   ├── langgraph_graph.py       # State graph construction
│   │   └── workflow_runner.py       # Execute workflow
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── handlers.py              # API endpoint handlers
│   │   ├── models.py                # Pydantic models
│   │   └── router.py                # FastAPI router
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py                # Structured logging
│   │   ├── retry.py                 # Retry logic
│   │   └── validators.py            # Input validation
│   │
│   └── integrations/
│       ├── __init__.py
│       ├── claude_client.py         # Anthropic API client
│       ├── mock_apis.py             # Mock external services
│       └── secrets_manager.py       # AWS Secrets Manager
│
├── lambda/
│   ├── submission_handler.py        # Lambda entry point for submissions
│   └── override_handler.py          # Lambda entry point for overrides
│
├── tests/
│   ├── conftest.py                  # pytest fixtures
│   ├── __init__.py
│   │
│   ├── unit/
│   │   ├── test_submission_processor.py
│   │   ├── test_document_tools.py
│   │   ├── test_data_tools.py
│   │   ├── test_decision_tools.py
│   │   ├── test_comms_tools.py
│   │   ├── test_output_tools.py
│   │   ├── test_state_manager.py
│   │   ├── test_audit_logger.py
│   │   └── test_config.py
│   │
│   ├── integration/
│   │   ├── test_submission_flow.py
│   │   ├── test_parallel_agents.py
│   │   └── test_api_endpoints.py
│   │
│   ├── performance/
│   │   └── test_latency.py
│   │
│   └── fixtures/
│       ├── complete_submission.json
│       ├── incomplete_submission.json
│       ├── high_risk_submission.json
│       └── blurry_scan.json
│
├── docs/
│   ├── REQUIREMENTS_AND_ARCHITECTURE.md
│   ├── TRACEABILITY_MATRIX.md
│   ├── IMPLEMENTATION_GUIDE.md
│   ├── OPERATIONS_RUNBOOK.md
│   └── API_REFERENCE.md
│
├── infrastructure/
│   ├── sam_template.yaml            # AWS SAM template for Lambda deployment
│   ├── step_functions_definition.json  # Step Functions state machine
│   └── cloudformation_stack.yaml    # CloudFormation template (alternative)
│
└── scripts/
    ├── deploy.sh                    # Deployment script
    ├── test_local.sh                # Local testing script
    └── generate_fixtures.py         # Generate test data
```

---

## File Count: ~35 source files + 20 test files + 10 config/docs files = 65 total files

## Dependencies

**Core:**
- langgraph >= 0.1.0
- anthropic >= 0.7.0
- pydantic >= 2.0.0
- fastapi >= 0.100.0
- boto3 >= 1.26.0

**Testing:**
- pytest >= 7.0.0
- pytest-cov >= 4.0.0
- pytest-asyncio >= 0.20.0
- pytest-mock >= 3.10.0

**Utilities:**
- python-dotenv >= 1.0.0
- structlog >= 22.0.0
- tenacity >= 8.0.0

---

## Configuration Files (MVP Defaults)

### .env.example
```
ANTHROPIC_API_KEY=your_key_here
AWS_REGION=us-east-1
AWS_SECRETS_MANAGER_ENABLED=false
LOG_LEVEL=INFO
MOCK_EXTERNAL_APIS=true
STATE_BACKEND=memory  # or "dynamodb" for production
SUBMISSION_TIMEOUT_SECONDS=30
```

### config/guidelines.json
```json
{
  "rules": [
    {
      "rule_id": "R001",
      "name": "Minimum Financial Health",
      "description": "Applicant must have credit score >= 500",
      "severity": "hard",
      "condition": "extracted_data.credit_score >= 500"
    },
    ...
  ]
}
```

---

## Development Workflow

```bash
# 1. Clone & install
git clone <repo>
cd agentic-underwriting-system
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run tests locally
make test              # all tests
make test-unit         # unit only
make test-integration  # integration only
make test-coverage     # with coverage report

# 3. Deploy to AWS
make deploy ENV=dev    # deploy to dev Lambda

# 4. Monitor
make logs ENV=dev      # tail CloudWatch logs
```
