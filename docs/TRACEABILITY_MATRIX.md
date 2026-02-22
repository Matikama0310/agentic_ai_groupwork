# Traceability Matrix

## Mapping: Requirements -> Components -> Code Modules -> Tests

### Functional Requirements

| FR ID | Requirement | Agent(s) | Code Module(s) | Test(s) |
|-------|-------------|----------|-----------------|---------|
| FR-1 | Ingest email submissions with attachments | Classification Agent | `orchestration/workflow.py::ingest_and_classify` | `test_all.py::TestWorkflowNodes::test_ingest_and_classify` |
| FR-2 | Classify content (NAICS code) | Classification Agent | `tools/decision_logic.py::classify_naics_code` | `test_all.py::TestDecisionTools::test_classify_naics_restaurant` |
| FR-3 | Extract data via OCR + LLM schema mapping | Classification Agent | `tools/document_understanding.py::extract_structured_data` | `test_all.py::TestDocumentTools::test_extract_structured_data_success` |
| FR-4 | Enrich with external APIs (D&B, HazardHub) | Data Retriever Agents (3x) | `tools/data_acquisition.py::fetch_external_data`, `internal_claims_history`, `web_research_applicant` | `test_all.py::TestDataTools::*` |
| FR-5 | Validate against underwriting guidelines | Gap Analysis Agent | `tools/decision_logic.py::validate_against_guidelines` | `test_all.py::TestDecisionTools::test_validate_guidelines_*` |
| FR-6 | Calculate risk scores and pricing | Analyst Agent | `tools/decision_logic.py::calculate_risk_and_price` | `test_all.py::TestDecisionTools::test_calculate_risk_and_price` |
| FR-7 | Generate quote package (PDF) | Broker Liaison Agent | `tools/communication.py::generate_quote_pdf`, `draft_quote_email` | `test_all.py::TestCommsTools::test_generate_quote_pdf` |
| FR-8 | Draft missing info emails | Broker Liaison Agent | `tools/communication.py::draft_missing_info_email` | `test_all.py::TestCommsTools::test_draft_missing_info_email` |
| FR-9 | Draft decline letters | Broker Liaison Agent | `tools/communication.py::draft_decline_letter` | `test_all.py::TestCommsTools::test_draft_decline_letter` |
| FR-10 | Support human overrides | Supervisor + Streamlit UI | `core/state_manager.py::apply_override`, `app.py` | `test_all.py::TestStateManager::test_apply_override` |
| FR-11 | Maintain audit trail | State Manager | `core/state_manager.py::add_audit_entry` | `test_all.py::TestStateManager::test_audit_entry` |
| FR-12 | Parallel data retrieval | Data Retriever Agents | `orchestration/workflow.py::enrichment` | `test_all.py::TestWorkflowNodes::test_enrichment` |
| FR-13 | 3-phase workflow with conditional edges | Supervisor Agent | `orchestration/workflow.py::build_underwriting_graph` | `test_all.py::TestEndToEnd::test_full_workflow_quoted` |

---

### Non-Functional Requirements

| NFR ID | Requirement | Implementation | Test(s) |
|--------|-------------|----------------|---------|
| NFR-1 | Latency < 30s | All tools have timeouts; sequential MVP, async-ready | `test_all.py::TestEndToEnd::test_full_workflow_performance` |
| NFR-2 | 99.5% uptime | AWS Lambda + SAM deployment | `infrastructure/sam_template.yaml` |
| NFR-3 | 100+ concurrent submissions | Lambda auto-scaling | Load test (manual) |
| NFR-4 | Structured logging + traceability | Python logging + audit trail | `test_all.py::TestStateManager::test_audit_entry` |
| NFR-5 | Test coverage >= 80% | pytest with 36 tests | `pytest --cov=src` |
| NFR-6 | Modular architecture | Separated tools, agents as graph nodes | 4 tool modules + workflow |
| NFR-7 | Secrets externalized | `.env` + `python-dotenv` | `.env.example` |
| NFR-8 | Human-in-the-loop | Streamlit workbench + override API | `app.py`, `test_all.py::TestStateManager::test_apply_override` |

---

### Code Module Ownership Map

```
src/
|-- orchestration/
|   |-- workflow.py                    [FR-1, 2, 12, 13] LangGraph StateGraph
|   |-- supervisor_agent.py            [FR-1, 13]        Orchestrator
|
|-- tools/
|   |-- decision_logic.py              [FR-2, 5, 6, 13]  NAICS, guidelines, risk
|   |-- document_understanding.py      [FR-3]             OCR, image analysis
|   |-- data_acquisition.py            [FR-4, 12]         Internal, external, web
|   |-- communication.py               [FR-7, 8, 9]       Emails, PDFs
|
|-- core/
|   |-- state_manager.py               [FR-10, 11]        State + audit + overrides
|
|-- api/
    |-- handlers.py                    [FR-10, 13]        FastAPI + Lambda

tests/
|-- test_all.py                        [All FRs]          36 tests across all layers

app.py                                 [FR-10, NFR-8]     Streamlit workbench
main.py                                [FR-13]            CLI entry point
```

---

### Conditional Edge Mapping

| Edge Function | Source Node | Condition | Target Nodes |
|---------------|------------|-----------|--------------|
| `is_data_complete` | `check_data_completeness` | Missing critical docs? | `draft_missing_info` (yes) / `enrichment` (no) |
| `knockout_check` | `check_knockout_rules` | Decision = DECLINED? | `draft_decline` (yes) / `risk_assessment` (no) |
| `human_decision` | `human_checkpoint` | Human override decision | `generate_quote` / `draft_decline` / `update_state` (loop) |

Tests: `test_all.py::TestConditionalEdges::*` (6 tests)

---

### Golden Test Cases

| Test ID | Scenario | Input | Expected Decision | Test |
|---------|----------|-------|-------------------|------|
| GTC-001 | Happy path | Complete restaurant application | QUOTED, premium > 0 | `TestEndToEnd::test_full_workflow_quoted` |
| GTC-002 | Performance | Any application | Completes < 10s | `TestEndToEnd::test_full_workflow_performance` |
| GTC-003 | Supervisor integration | Via SupervisorAgent class | QUOTED with full state sync | `TestEndToEnd::test_supervisor_agent_integration` |

---

## END OF TRACEABILITY MATRIX
