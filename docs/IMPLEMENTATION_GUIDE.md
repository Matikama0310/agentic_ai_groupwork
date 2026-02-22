# Implementation Guide

## NorthStar Agentic Underwriting System

---

## 1. System Overview

The system processes insurance applications through a **LangGraph StateGraph** with 10 nodes, 3 conditional edges, and human-in-the-loop checkpoint.

### Entry Points

| Command | Purpose |
|---------|---------|
| `python main.py` | CLI demo (runs one submission through full workflow) |
| `streamlit run app.py` | Streamlit workbench (submit, review, override) |
| `python main.py --server` | FastAPI server (REST API at localhost:8000) |
| `pytest tests/test_all.py -v` | Run all 36 tests |

---

## 2. Architecture

### 2.1 LangGraph Workflow (`src/orchestration/workflow.py`)

The core of the system. `build_underwriting_graph()` constructs a `StateGraph` with:

**Nodes (10):**
1. `ingest_and_classify` - OCR extraction + NAICS classification
2. `check_data_completeness` - Validates critical documents present
3. `draft_missing_info` - Drafts email requesting missing docs
4. `enrichment` - Parallel data retrieval (internal, external, web)
5. `check_knockout_rules` - Validates hard underwriting rules
6. `draft_decline` - Drafts decline letter with citations
7. `risk_assessment` - Calculates risk score + premium
8. `human_checkpoint` - Persists state, awaits human decision
9. `generate_quote` - Creates quote PDF + email
10. `update_state` - Applies human modifications, loops back

**Conditional Edges (3):**
- `is_data_complete` -> missing_docs | data_complete
- `knockout_check` -> fail | pass
- `human_decision` -> approve | decline | modify

**State Type:** `UnderwritingState` (TypedDict) with fields for all phases.

### 2.2 Supervisor Agent (`src/orchestration/supervisor_agent.py`)

Wraps the LangGraph workflow:
1. Creates initial state in `StateManager`
2. Builds `UnderwritingState` input dict
3. Calls `workflow.invoke(graph_input)`
4. Syncs final state back to `StateManager`
5. Syncs audit trail entries

### 2.3 Tools (`src/tools/`)

4 modules, 12 tools total. All return `ToolResult(success, data, error)`.

| Module | File | Tools |
|--------|------|-------|
| Decision Logic | `decision_logic.py` | `classify_naics_code`, `validate_against_guidelines`, `calculate_risk_and_price` |
| Document Understanding | `document_understanding.py` | `extract_structured_data`, `analyze_image_hazards` |
| Data Acquisition | `data_acquisition.py` | `internal_claims_history`, `fetch_external_data`, `web_research_applicant` |
| Communication | `communication.py` | `draft_missing_info_email`, `draft_decline_letter`, `draft_quote_email`, `generate_quote_pdf` |

### 2.4 State Manager (`src/core/state_manager.py`)

- `SubmissionState` dataclass with 20+ fields
- `StateManager` singleton with `create_state`, `get_state`, `update_state`, `add_audit_entry`, `apply_override`, `get_submission_summary`, `list_submissions`
- In-memory dict backend (swap to DynamoDB by changing the storage layer)

---

## 3. How to Extend

### 3.1 Add a New Tool

1. Create function in the appropriate `src/tools/` module
2. Return `ToolResult(success=True, data={...})`
3. Call it from the relevant workflow node in `workflow.py`
4. Add tests in `tests/test_all.py`

### 3.2 Add a New Underwriting Rule

Edit `UNDERWRITING_GUIDELINES` in `src/tools/decision_logic.py`:
```python
{
    "rule_id": "R005",
    "name": "Maximum Building Age",
    "condition": "building_age",
    "threshold": 50,
    "comparison": "<",
    "severity": "hard",
}
```

### 3.3 Add a New Workflow Node

1. Define node function in `workflow.py` (takes `state: dict`, returns `dict`)
2. Add to graph: `graph.add_node("new_node", new_node_function)`
3. Wire edges: `graph.add_edge("previous_node", "new_node")`
4. Add tests

### 3.4 Switch to Real External APIs

Replace mock implementations in `src/tools/data_acquisition.py`:
```python
def fetch_external_data(applicant_name, applicant_address):
    # Replace mock with real API call
    response = requests.get(f"{DNB_API_URL}/lookup", params={...}, headers={...})
    return ToolResult(True, response.json())
```

### 3.5 Switch to DynamoDB

Replace the in-memory dict in `StateManager` with `boto3.resource('dynamodb')` calls. The interface (`create_state`, `get_state`, `update_state`) stays the same.

---

## 4. Testing Strategy

### Unit Tests
- Each tool function tested independently
- State manager CRUD operations tested
- Individual workflow nodes tested with mock state

### Conditional Edge Tests
- Each conditional function tested with both branches
- 6 tests covering all 3 edges x 2 outcomes each

### End-to-End Tests
- Full workflow invoked with `compile_workflow().invoke()`
- SupervisorAgent integration test
- Performance test (< 10 seconds)

### Running Tests
```bash
pytest tests/test_all.py -v              # All 36 tests
pytest tests/test_all.py -k "EndToEnd"   # E2E only
pytest tests/test_all.py -k "Decision"   # Decision tools only
pytest tests/test_all.py --cov=src       # With coverage
```

---

## 5. Troubleshooting

### LangGraph import errors
```bash
pip install langgraph langchain-core
```

### Streamlit port conflict
```bash
streamlit run app.py --server.port 8502
```

### Tests failing on import
Ensure you're running from the project root:
```bash
cd agentic-underwriting-system
pytest tests/test_all.py -v
```

### State not persisting between Streamlit reruns
This is expected with in-memory state. The Streamlit session state preserves the `StateManager` instance within a browser session.
