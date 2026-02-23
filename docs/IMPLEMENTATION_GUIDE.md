# Implementation Guide

How to work with the MVP mock system, swap to real production services, extend the system with new tools/nodes/rules, and run the test suite.

---

## Table of Contents

1. [MVP vs Production](#1-mvp-vs-production)
2. [Swapping Mock to Real Services](#2-swapping-mock-to-real-services)
3. [How to Add a New Tool](#3-how-to-add-a-new-tool)
4. [How to Add a New Workflow Node](#4-how-to-add-a-new-workflow-node)
5. [How to Add a New Underwriting Rule](#5-how-to-add-a-new-underwriting-rule)
6. [Testing Strategy](#6-testing-strategy)
7. [Cross-Platform Notes](#7-cross-platform-notes)

---

## 1. MVP vs Production

The MVP runs fully offline with zero configuration. Every external dependency returns mock data so you can test the complete workflow, UI, and API without API keys or cloud services.

| Component | MVP (Mock) | Production (Real) | Effort to Swap |
|-----------|-----------|-------------------|----------------|
| Document extraction | Returns mock fields from `extract_structured_data()` | AWS Textract or Claude Vision API | Replace function body |
| Image analysis | Returns mock hazard list | Claude Vision API | Replace function body |
| Internal claims | Returns mock loss runs from `internal_claims_history()` | SQL/CRM API query | Replace function body |
| External data | Returns mock D&B/HazardHub data from `fetch_external_data()` | D&B, HazardHub, Verisk API calls | Replace function body |
| Web research | Returns mock web results from `web_research_applicant()` | Headless browser or search API | Replace function body |
| NAICS classification | Keyword-based matching in `classify_naics_code()` | LLM-based classification | Replace function body |
| PDF generation | Returns placeholder S3 URL from `generate_quote_pdf()` | ReportLab + S3 upload | Replace function body |
| Email sending | Draft-only (not sent) | SES or SMTP send after drafting | Add send step after draft |
| State storage | In-memory Python dict | DynamoDB | Swap `StateManager` storage backend |
| Risk/pricing | Formula: base * credit * loss * size modifiers | Enhanced actuarial model | Update `calculate_risk_and_price()` |

### What stays the same

The workflow graph, conditional edges, state schema, API endpoints, Streamlit UI, and test structure all remain identical. Only the tool function bodies change.

---

## 2. Swapping Mock to Real Services

Every tool follows the same pattern: a function that returns `ToolResult(success, data, error)`. To swap mock to real, replace the function body while keeping the same return signature.

### Example: External Data (D&B API)

**Current mock** in `src/tools/data_acquisition.py`:

```python
def fetch_external_data(applicant_name, applicant_address, data_sources=None):
    # MVP: returns mock data
    return ToolResult(True, {
        "credit_score": 720,
        "financial_health": "Good",
        ...
    })
```

**Production replacement:**

```python
import requests
import os

def fetch_external_data(applicant_name, applicant_address, data_sources=None):
    try:
        dnb_response = requests.get(
            f"{os.getenv('DNB_API_URL')}/v1/match",
            params={"name": applicant_name, "address": applicant_address},
            headers={"Authorization": f"Bearer {os.getenv('DNB_API_KEY')}"},
            timeout=10,
        )
        dnb_response.raise_for_status()
        dnb_data = dnb_response.json()

        return ToolResult(True, {
            "credit_score": dnb_data["creditScore"],
            "financial_health": dnb_data["financialStrength"],
            "duns_number": dnb_data["dunsNumber"],
            "property_risk": {"flood_zone": "X", "fire_score": 3},  # from HazardHub
        })
    except Exception as e:
        return ToolResult(False, {}, str(e))
```

### Example: DynamoDB State Backend

Replace the in-memory dict in `StateManager.__init__()` with DynamoDB calls. The method signatures (`create_state`, `get_state`, `update_state`, `add_audit_entry`, `apply_override`) stay the same.

```python
import boto3

class StateManager:
    def __init__(self):
        self.table = boto3.resource('dynamodb').Table(os.getenv('DYNAMODB_TABLE'))

    def create_state(self, submission_id, **kwargs):
        item = {"submission_id": submission_id, **kwargs}
        self.table.put_item(Item=item)
        return item

    def get_state(self, submission_id):
        response = self.table.get_item(Key={"submission_id": submission_id})
        return response.get("Item")
```

### Example: PDF Generation

Replace `generate_quote_pdf()` in `src/tools/communication.py`:

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import boto3
import tempfile

def generate_quote_pdf(extracted, risk_metrics, premium, applicant_name):
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            c = canvas.Canvas(tmp.name, pagesize=letter)
            c.drawString(100, 750, f"Quote for {applicant_name}")
            c.drawString(100, 730, f"Annual Premium: ${premium:,.2f}")
            c.drawString(100, 710, f"Risk Score: {risk_metrics['risk_score']}/100")
            c.save()

            s3 = boto3.client("s3")
            key = f"quotes/{applicant_name.replace(' ', '_')}.pdf"
            s3.upload_file(tmp.name, os.getenv("S3_BUCKET"), key)
            url = f"s3://{os.getenv('S3_BUCKET')}/{key}"

        return ToolResult(True, {"quote_pdf_s3_url": url})
    except Exception as e:
        return ToolResult(False, {}, str(e))
```

### Example: Email Sending

Add a send step after drafting in the workflow node:

```python
import smtplib
from email.mime.text import MIMEText

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["To"] = to
    msg["From"] = os.getenv("SMTP_FROM")

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)
```

---

## 3. How to Add a New Tool

1. **Create the function** in the appropriate `src/tools/` module (or create a new module).
2. **Return `ToolResult`:**
   ```python
   from src.tools.decision_logic import ToolResult

   def my_new_tool(param1, param2):
       # your logic
       return ToolResult(success=True, data={"key": "value"})
   ```
3. **Export it** from `src/tools/__init__.py` if needed.
4. **Call it** from the relevant workflow node in `src/orchestration/workflow.py`.
5. **Add tests** in `tests/test_all.py`:
   ```python
   class TestMyNewTool(unittest.TestCase):
       def test_my_new_tool_success(self):
           result = my_new_tool("input1", "input2")
           self.assertTrue(result.success)
           self.assertIn("key", result.data)
   ```

---

## 4. How to Add a New Workflow Node

1. **Define the node function** in `src/orchestration/workflow.py`:
   ```python
   def my_new_node(state: dict) -> dict:
       # Read from state, call tools, return updates
       result = my_new_tool(state["some_field"])
       return {"new_field": result.data}
   ```
2. **Add to the graph** in `build_underwriting_graph()`:
   ```python
   graph.add_node("my_new_node", my_new_node)
   ```
3. **Wire edges:**
   ```python
   graph.add_edge("previous_node", "my_new_node")
   graph.add_edge("my_new_node", "next_node")
   ```
4. **For conditional routing**, add a conditional edge function:
   ```python
   def my_condition(state: dict) -> str:
       if state.get("some_field"):
           return "branch_a"
       return "branch_b"

   graph.add_conditional_edges("my_new_node", my_condition, {
       "branch_a": "node_a",
       "branch_b": "node_b",
   })
   ```
5. **Update `UnderwritingState`** TypedDict if the node adds new fields.
6. **Add tests** for both the node function and any conditional edge.

---

## 5. How to Add a New Underwriting Rule

Edit `UNDERWRITING_GUIDELINES` in `src/tools/decision_logic.py`:

```python
UNDERWRITING_GUIDELINES = [
    # ... existing rules ...
    {
        "rule_id": "R005",
        "name": "Maximum Building Age",
        "condition": "building_age",
        "threshold": 50,
        "comparison": "<",
        "severity": "hard",
    },
]
```

The `validate_against_guidelines()` function automatically evaluates all rules in this list. No other code changes are needed unless the field (`building_age`) is not yet in the extracted or enriched data.

To add the field to data:
1. Include it in the mock data returned by the relevant tool (e.g., `fetch_external_data`)
2. Ensure the extraction or enrichment step populates it in the state

---

## 6. Testing Strategy

### Test Structure

All tests are in `tests/test_all.py` with 8 test classes:

| Test Class | Tests | Scope |
|------------|-------|-------|
| `TestDocumentTools` | 4 | Each document tool function in isolation |
| `TestDecisionTools` | 4 | NAICS classification, guidelines validation, risk/pricing |
| `TestDataTools` | 3 | Each data acquisition tool in isolation |
| `TestCommsTools` | 4 | Email drafts, PDF generation |
| `TestStateManager` | 7 | CRUD, audit entries, overrides, listing |
| `TestWorkflowNodes` | 3 | Individual node functions with mock state |
| `TestConditionalEdges` | 6 | Each conditional edge with both branches |
| `TestEndToEnd` | 3 | Full workflow, performance, supervisor integration |

### Running Tests

All commands work on Windows, macOS, and Linux:

```bash
# Run all 36 tests
pytest tests/test_all.py -v

# With coverage report
pytest tests/test_all.py --cov=src --cov-report=term-missing

# Run a specific test class
pytest tests/test_all.py::TestEndToEnd -v
pytest tests/test_all.py::TestDecisionTools -v
pytest tests/test_all.py::TestWorkflowNodes -v
pytest tests/test_all.py::TestConditionalEdges -v

# Run a single test
pytest tests/test_all.py::TestEndToEnd::test_full_workflow_quoted -v -s

# Filter by keyword
pytest tests/test_all.py -k "Decision" -v
pytest tests/test_all.py -k "EndToEnd" -v
```

### Writing Tests for New Tools

Follow the existing pattern:

```python
class TestMyNewTool(unittest.TestCase):
    def test_success_case(self):
        result = my_new_tool("valid_input")
        self.assertTrue(result.success)
        self.assertIn("expected_key", result.data)

    def test_edge_case(self):
        result = my_new_tool("")
        # Assert expected behavior for edge case
```

### Writing Tests for New Conditional Edges

Test both branches:

```python
class TestMyConditionalEdge(unittest.TestCase):
    def test_branch_a(self):
        state = {"field": "value_triggering_branch_a"}
        result = my_condition(state)
        self.assertEqual(result, "branch_a")

    def test_branch_b(self):
        state = {"field": "value_triggering_branch_b"}
        result = my_condition(state)
        self.assertEqual(result, "branch_b")
```

---

## 7. Cross-Platform Notes

The project runs on Windows, macOS, and Linux. Here are the key differences:

### Virtual Environment Activation

| Platform | Command |
|----------|---------|
| Windows (cmd) | `venv\Scripts\activate` |
| Windows (PowerShell) | `.\venv\Scripts\Activate.ps1` |
| macOS / Linux | `source venv/bin/activate` |

### File Copy

| Platform | Command |
|----------|---------|
| Windows (cmd) | `copy .env.example .env` |
| Windows (PowerShell) | `Copy-Item .env.example .env` |
| macOS / Linux | `cp .env.example .env` |

### Path Separators

Python handles path separators automatically via `os.path` and `pathlib`. All file paths in the codebase use forward slashes or `os.path.join()`, so no changes are needed across platforms.

### Makefile

The `Makefile` uses Unix-style commands. On Windows:
- Use **Git Bash** or **WSL** to run `make` commands, or
- Run the underlying Python commands directly (e.g., `pytest tests/test_all.py -v` instead of `make test`)

### Line Endings

The `.gitignore` and project files use LF line endings. Git handles conversion automatically. If you encounter issues:
```bash
git config core.autocrlf true   # Windows
git config core.autocrlf input  # macOS/Linux
```

### Streamlit and FastAPI

Both work identically across all platforms. The URLs (`http://localhost:8501` for Streamlit, `http://localhost:8000` for FastAPI) are the same.
