# Traceability Matrix
## Mapping Requirements → Components → Code Modules → Tests

### FUNCTIONAL REQUIREMENTS TRACEABILITY

| FR ID | Requirement | Component(s) | Code Module(s) | Test(s) |
|-------|-------------|--------------|-----------------|---------|
| FR-1 | Ingest email submissions with attachments | SubmissionProcessor | `core/submission_processor.py` | `tests/test_submission_processor.py::test_parse_email_with_attachments` |
| FR-2 | Classify content (structured vs unstructured) | ClassificationAgent | `agents/classification_agent.py` | `tests/test_agents.py::test_classification_agent` |
| FR-3 | Extract data via OCR + LLM schema mapping | AnalystAgent + extract_structured_data tool | `agents/analyst_agent.py`, `tools/document_tools.py` | `tests/test_document_tools.py::test_extract_structured_data` |
| FR-4 | Enrich with external APIs (D&B, HazardHub) | DataRetrieverAgent (3x) | `agents/data_retriever_agent.py`, `tools/data_tools.py` | `tests/test_data_tools.py::test_fetch_external_data_mocked` |
| FR-5 | RAG lookup of underwriting rules | AnalystAgent + validate_against_guidelines tool | `agents/analyst_agent.py`, `tools/decision_tools.py` | `tests/test_decision_tools.py::test_validate_against_guidelines` |
| FR-6 | Calculate risk scores and pricing | AnalystAgent + calculate_risk_and_price tool | `agents/analyst_agent.py`, `tools/decision_tools.py` | `tests/test_decision_tools.py::test_calculate_risk_and_price` |
| FR-7 | Generate quote package (PDF) | OutputAgent + generate_quote_pdf tool | `agents/output_agent.py`, `tools/output_tools.py` | `tests/test_output_tools.py::test_generate_quote_pdf_mocked` |
| FR-8 | Draft missing info emails | BrokerLiaisonAgent + draft_missing_info_email tool | `agents/broker_liaison_agent.py`, `tools/comms_tools.py` | `tests/test_comms_tools.py::test_draft_missing_info_email` |
| FR-9 | Draft decline letters | BrokerLiaisonAgent + draft_decline_letter tool | `agents/broker_liaison_agent.py`, `tools/comms_tools.py` | `tests/test_comms_tools.py::test_draft_decline_letter` |
| FR-10 | Support human overrides | StateManager + API handler | `core/state_manager.py`, `api/handlers.py` | `tests/test_state_manager.py::test_apply_override` |
| FR-11 | Maintain audit trail | StateManager + AuditLogger | `core/state_manager.py`, `core/audit_logger.py` | `tests/test_audit_logger.py::test_audit_trail_logged` |
| FR-12 | Parallel execution of Data Retrievers | SupervisorAgent (LanGraph) | `orchestration/supervisor_agent.py`, `langgraph/graph.py` | `tests/integration_test.py::test_parallel_data_retrieval` |
| FR-13 | Validate against executable guidelines | AnalystAgent + validate_against_guidelines tool | `agents/analyst_agent.py`, `tools/decision_tools.py` | `tests/test_decision_tools.py::test_validate_against_guidelines` |

---

### NON-FUNCTIONAL REQUIREMENTS TRACEABILITY

| NFR ID | Requirement | Component(s) | Implementation Strategy | Test(s) |
|--------|-------------|--------------|------------------------|---------|
| NFR-1 | Latency < 30s (data retrieval + enrichment) | DataRetrieverAgent, Tool timeouts | All tools have 10-15s timeout; parallel execution; async where possible | `tests/performance_test.py::test_enrichment_latency_30s` |
| NFR-2 | 99.5% uptime SLA (AWS serverless) | Lambda + Step Functions | Deployment via SAM/CloudFormation; DLQ for failed invocations | `tests/deployment_test.py::test_lambda_deployment_config` |
| NFR-3 | Handle 100+ concurrent submissions | Step Functions + Lambda concurrency | Step Functions scales horizontally; Lambda concurrency limit set to 100 | Load test (manual) |
| NFR-4 | Structured logging + traceability | Logger + AuditLogger | JSON logging with correlation_id; all tool calls logged | `tests/test_logging.py::test_structured_logging_json` |
| NFR-5 | Unit test coverage >= 80% | All modules | pytest with coverage tracking | `make test-coverage` target |
| NFR-6 | Modular architecture | Agent, Tool, StateManager separation | LanGraph for separation; pluggable tools | `tests/architecture_test.py::test_tool_pluggability` |
| NFR-7 | Secrets in AWS Secrets Manager | All config with credentials | Credentials loaded from boto3 secrets; no hardcoding | `tests/test_config.py::test_no_hardcoded_secrets` |
| NFR-8 | Extensible tool/agent system | Tool registry + agent factory | Tool class inheritance; agent registration pattern | `tests/test_extensibility.py::test_new_tool_registration` |

---

### CODE MODULE OWNERSHIP MAP

```
src/
├── orchestration/
│   ├── supervisor_agent.py           [FR-1, 2, 12, 13]
│   ├── langgraph_graph.py             [FR-12]
│
├── agents/
│   ├── base_agent.py                  [NFR-6, 8]
│   ├── classification_agent.py        [FR-2]
│   ├── analyst_agent.py               [FR-3, 5, 6, 13]
│   ├── data_retriever_agent.py        [FR-4, 12]
│   ├── broker_liaison_agent.py        [FR-8, 9]
│   └── output_agent.py                [FR-7]
│
├── tools/
│   ├── base_tool.py                   [NFR-6, 8]
│   ├── data_tools.py                  [FR-4]
│   ├── document_tools.py              [FR-2, 3]
│   ├── decision_tools.py              [FR-5, 6, 13]
│   ├── comms_tools.py                 [FR-8, 9]
│   └── output_tools.py                [FR-7]
│
├── core/
│   ├── submission_processor.py        [FR-1]
│   ├── state_manager.py               [FR-10, 11]
│   ├── audit_logger.py                [FR-11, NFR-4]
│   └── config.py                      [NFR-7]
│
├── api/
│   ├── handlers.py                    [FR-10]
│   └── models.py                      (input/output schemas)
│
└── utils/
    ├── logger.py                      [NFR-4]
    └── errors.py                      (exception hierarchy)

tests/
├── unit/
│   ├── test_document_tools.py         [FR-2, 3]
│   ├── test_data_tools.py             [FR-4]
│   ├── test_decision_tools.py         [FR-5, 6, 13]
│   ├── test_comms_tools.py            [FR-8, 9]
│   ├── test_output_tools.py           [FR-7]
│   ├── test_state_manager.py          [FR-10, 11]
│   ├── test_audit_logger.py           [FR-11, NFR-4]
│   └── test_config.py                 [NFR-7]
│
├── integration/
│   ├── test_submission_flow.py        [FR-1 through FR-13]
│   ├── test_parallel_agents.py        [FR-12]
│   └── test_api_endpoints.py          [FR-10]
│
└── performance/
    └── test_latency.py                [NFR-1, 3]
```

---

### TEST EXECUTION MATRIX

| Test Module | Component | Coverage | Execution Time | Mock/Real |
|-------------|-----------|----------|-----------------|-----------|
| test_document_tools.py | OCR, extraction | extract_structured_data, analyze_image_hazards | ~5s | Mock (no real API calls) |
| test_data_tools.py | External APIs | fetch_external_data, internal_claims_history, web_research | ~5s | Mock (responses hardcoded) |
| test_decision_tools.py | Rules, pricing | classify_naics_code, validate_against_guidelines, calculate_risk_and_price | ~5s | Mock (guidelines from JSON) |
| test_comms_tools.py | Email drafting | draft_missing_info_email, draft_decline_letter, draft_quote_email | ~3s | Always mocked (no SMTP) |
| test_output_tools.py | PDF generation | generate_quote_pdf | ~3s | Mock (returns placeholder URL) |
| test_state_manager.py | State management | get_state, update_state, apply_override | ~2s | In-memory dict |
| test_audit_logger.py | Audit trail | log_decision, log_override | ~2s | File logging |
| integration_test.py | End-to-end workflow | Full submission → output | ~30s | All mocked |
| performance_test.py | Latency SLA | Enrichment + assessment | < 30s | All mocked |

---

### REQUIREMENT DEPENDENCIES

```
FR-1 (Ingest)
  └─► FR-2 (Classify)
       └─► FR-3 (Extract)
            ├─► FR-4 (Enrich) [parallel]
            ├─► FR-5 (RAG Validate)
            │    └─► FR-13 (Validate Guidelines)
            │         ├─► FR-8 (Missing Info Draft)
            │         ├─► FR-9 (Decline Draft)
            │         └─► FR-6 (Risk & Price)
            │              └─► FR-7 (Generate Quote)
            │
            └─► FR-11 (Audit Trail)
                 └─► FR-10 (Human Overrides)
                      └─► FR-12 (Parallel Execution)
```

---

### GOLDEN TEST CASES (Regression Harness)

These test cases define expected behavior for the entire workflow:

| Test ID | Scenario | Input | Expected Output | Assertion |
|---------|----------|-------|------------------|-----------|
| GTC-001 | Happy path: Complete submission | `fixtures/complete_submission.json` | `decision="QUOTED"`, premium calculated | status="QUOTED", premium > 0 |
| GTC-002 | Missing critical doc | `fixtures/incomplete_submission.json` | `decision="MISSING_INFO"`, email drafted | status="MISSING_INFO", missing_docs.length > 0 |
| GTC-003 | Failed guideline rule | `fixtures/high_risk_submission.json` | `decision="DECLINED"`, decline letter drafted | status="DECLINED", failed_rules.length > 0 |
| GTC-004 | Low extraction confidence | `fixtures/blurry_scan.json` | `decision="MANUAL_REVIEW"` | status="MANUAL_REVIEW", extraction_confidence < 0.5 |
| GTC-005 | Human override | GTC-002 with override | `decision` changes to new value | audit_trail logs override |
| GTC-006 | External API timeout | Data retrieval fails | Proceeds with fallback data | internal_data only, no error |
| GTC-007 | Parallel data retrieval | All 3 retriever agents fire | All complete within 30s | completed in < 30s |
| GTC-008 | Guidelines not found | Config is missing | Raises SystemError | exception raised, processing halted |

---

## END OF TRACEABILITY MATRIX
