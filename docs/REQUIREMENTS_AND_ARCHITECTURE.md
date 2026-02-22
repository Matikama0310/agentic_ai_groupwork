# Agentic Insurance Underwriting Solution
## Requirements & Architecture Specification

**Version:** 1.0  
**Date:** 2026-02-22  
**Status:** MVP Implementation

---

## 1. REQUIREMENTS EXTRACTION

### 1.1 Functional Requirements

| ID | Requirement | Source |
|---|---|---|
| FR-1 | System shall ingest insurance submissions via email attachments (PDFs, images, text) | Workflow Phase 1 |
| FR-2 | System shall classify submission content (structured vs. unstructured) and split email body from attachments | Ingest & Classify Node |
| FR-3 | System shall extract data from submissions using OCR and LLM-based schema mapping to standard underwriting fields | Extraction Node |
| FR-4 | System shall enrich submission data by calling external APIs (D&B, HazardHub) for credit scores, financial health, property risk, flood zones, fire station distance, crime scores | Enrichment Node |
| FR-5 | System shall perform risk assessment using RAG (Retrieval-Augmented Generation) to look up underwriting rules and guidelines | Risk Assessment Node |
| FR-6 | System shall calculate risk scores and pricing using hard-coded rules and mathematical models (Debt-to-Equity, Loss Ratios) | Risk Assessment Node |
| FR-7 | System shall generate a quote package (PDF binder) if underwriting passes all gates | Generate Quote Pkg Node |
| FR-8 | System shall draft "Missing Info" emails listing specific missing documentation required to proceed | Draft Missing Info Node |
| FR-9 | System shall draft decline letters citing specific underwriting guidelines that were not met | Draft Decline Node |
| FR-10 | System shall support human override/manual state updates to AI-generated decisions (Phase 3: Workbench) | Update State Node |
| FR-11 | System shall maintain an audit trail of all decisions, overrides, and rule applications | Implicit |
| FR-12 | System shall support parallel execution of Data Retriever agents (Internal, External Bureau, Open Source) | Architecture Doc |
| FR-13 | System shall validate submitted data against executable underwriting guidelines before proceeding | Architecture Doc |

### 1.2 Non-Functional Requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-1 | Latency: Initial data retrieval and enrichment shall complete in < 30 seconds | Broker UX; avoid timeouts |
| NFR-2 | Availability: System shall be deployed on AWS serverless (Lambda + SQS) with 99.5% uptime SLA | Cost efficiency; auto-scaling |
| NFR-3 | Scalability: System shall handle 100+ concurrent submissions without degradation | Peak underwriting load |
| NFR-4 | Observability: All agent decisions, tool calls, and errors shall be logged with structured JSON + correlation IDs | Audit + debugging |
| NFR-5 | Testability: Unit test coverage >= 80% for tools and logic; integration tests for agent workflows | Quality assurance |
| NFR-6 | Maintainability: Code shall follow modular architecture (agents, tools, orchestrator as separate modules) | Future enhancements |
| NFR-7 | Security: Secrets (API keys, database credentials) shall be stored in AWS Secrets Manager; no secrets in code | Compliance |
| NFR-8 | Extensibility: New tools and agents shall be pluggable without modifying core orchestrator | Long-term roadmap |

---

## 2. ASSUMPTIONS & OPEN QUESTIONS

### ASSUMPTION-1: LLM Provider
**Assumption:** Use Claude 3.5 Sonnet via Anthropic API (free tier for MVP).  
**Rationale:** Cost-effective, high accuracy for document understanding and rule application.  
**Open Q:** Will this be switched to a local model (Ollama) later? → **Default:** Use Anthropic API for MVP.

### ASSUMPTION-2: Data Sources (Mock for MVP)
**Assumption:** All external data sources (D&B, HazardHub, internal claims systems) will be mocked with synthetic responses.  
**Rationale:** Real APIs require credentials, contracts, and rate limits. MVP focuses on orchestration and agent behavior.  
**Open Q:** How will real API connections be tested in staging? → **Default:** Implement adapter pattern; replace mocks in config.

### ASSUMPTION-3: Underwriting Rules
**Assumption:** Underwriting guidelines are provided as a structured JSON ruleset (simulated for MVP).  
**Rationale:** RAG requires a knowledge base; rules in markdown are easier to version control.  
**Open Q:** Where are the real rules stored? → **Default:** Use `config/guidelines.json` for MVP.

### ASSUMPTION-4: Human Overrides
**Assumption:** For MVP, human overrides are API calls (POST to `/override`) rather than a full UI.  
**Rationale:** Focus on agent orchestration; UI is Phase 3 ("Workbench").  
**Open Q:** Will Phase 3 be a web app or desktop? → **Default:** Not in scope for MVP; API stubs only.

### ASSUMPTION-5: Deployment Scope
**Assumption:** MVP will be deployed as AWS Lambda functions orchestrated by AWS Step Functions (not SQS).  
**Rationale:** Step Functions provide visual workflow monitoring; better for this use case than raw SQS.  
**Open Q:** Should we use SQS for async submission ingestion? → **Default:** Step Functions for synchronous flow; SQS as optional enhancement.

### ASSUMPTION-6: Broker Communication
**Assumption:** Email sending (SMTP) is mocked via a logger; real SMTP integration is Phase 2.  
**Rationale:** Testing email logic without hitting a real mailbox.  
**Open Q:** Will emails be queued or sent synchronously? → **Default:** Synchronous logging for MVP.

### ASSUMPTION-7: PDF Generation
**Assumption:** PDF generation is mocked (returns a placeholder); real PDF construction uses ReportLab.  
**Rationale:** Focus on orchestration; PDF rendering is a separate concern.  
**Open Q:** Will PDFs be stored in S3? → **Default:** S3 path returned; actual file creation mocked.

### ASSUMPTION-8: State Management
**Assumption:** Submission state is stored in a local in-memory dict for MVP; replace with DynamoDB for production.  
**Rationale:** Simplifies MVP; no database setup required.  
**Open Q:** Do we need distributed state for multi-region? → **Default:** Single-region for MVP.

---

## 3. ARCHITECTURE & DESIGN

### 3.1 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     SUBMISSION ENTRY POINT                        │
│                  (Email/File Upload Received)                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT (LanGraph)                    │
│  Role: Traffic Controller + Compliance Officer                   │
│  - Receives submission                                            │
│  - Decomposes into tasks                                          │
│  - Orchestrates workers                                           │
│  - Compiles final recommendation                                  │
│  - Enforces guidelines                                            │
└────────────────────────────┬─────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┬──────────────┐
          │                  │                  │              │
          ▼                  ▼                  ▼              ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐    ┌──────────┐
    │  Data    │      │ Analyst  │      │  Broker  │    │  State   │
    │ Retriever│      │  Agents  │      │ Liaison  │    │ Manager  │
    │ Agents   │      │          │      │  Agent   │    │          │
    │ (3x par) │      │          │      │          │    │          │
    └──────────┘      └──────────┘      └──────────┘    └──────────┘
         │                 │                  │              │
    Parallel:         Sequential:          Async:        In-Memory:
    - Internal        - Classify            - Email       - Stage
    - External        - Gap Analysis        - Calendar    - Rules
    - OpenSource      - Risk Assess         - Templates   - Decisions


                  TOOLS LAYER (Function Calling)
    ┌────────────┬────────────┬────────────┬────────────┐
    │   Data     │  Document  │  Decision  │    Comms   │
    │ Acquisition│Understanding│   Logic   │   Tools    │
    ├────────────┼────────────┼────────────┼────────────┤
    │ - SQL      │ - OCR      │ - RAG      │ - Email    │
    │ - APIs     │ - Vision   │ - Calc     │ - Calendar │
    │ - Web      │ - Parser   │ - Rules    │ - Template │
    └────────────┴────────────┴────────────┴────────────┘
```

### 3.2 Agent Design

#### **Supervisor Agent**
- **Framework:** LanGraph (StateGraph)
- **Memory:** 
  - Input: Submission (JSON with applicant info, attachments, metadata)
  - State: Current stage (ingestion, extraction, enrichment, assessment, output), decisions made, errors
  - Output: Final recommendation (quote, decline, or missing-info request)
- **Tool-Calling Strategy:**
  - Does NOT directly call external APIs; delegates to workers
  - Calls `orchestrate_workflow()` which returns agent decisions
  - Validates each decision against guidelines before proceeding
- **Guardrails:**
  - Rejects submissions that violate hard constraints (e.g., applicant outside service area)
  - Requires all critical documents before generating quote
  - Prevents duplicate processing (check submission ID in state)

#### **Data Retriever Agents** (3 parallel)
- **Internal Claims Agent:** Queries `internal_claims_history()` tool
- **External Bureau Agent:** Calls `fetch_external_data()` tool (D&B, HazardHub)
- **Open Source Agent:** Calls `web_research_applicant()` tool
- **Memory:** Each maintains its own result set; Supervisor aggregates
- **Tool-Calling Strategy:** Each agent calls one primary tool; retries on failure
- **Guardrails:** Rate-limit API calls; timeout after 10s; fail gracefully (null data is OK)

#### **Analyst Agents**
- **Classification Agent:** Calls `classify_naics_code()` and `extract_structured_data()`
- **Gap Analysis Agent:** Calls `validate_against_guidelines()` and `identify_missing_docs()`
- **Memory:** Structured extraction results (JSON schema), gaps list
- **Tool-Calling Strategy:** Sequential; classification must complete before gap analysis
- **Guardrails:** If extraction confidence < 70%, flag for manual review; list gaps explicitly

#### **Broker Liaison Agent**
- **Memory:** Draft email/letter templates, status checks
- **Tool-Calling Strategy:** Calls `draft_missing_info_email()`, `draft_decline_letter()`, `draft_quote_email()`
- **Guardrails:** Emails are drafted but not sent; human review required (unless auto-send flag is true for low-touch accounts)

#### **State Manager (Not an Agent)**
- Maintains submission state in-memory (dict keyed by submission_id)
- Tracks: current stage, data collected, decisions, overrides
- Supports `get_state()`, `update_state()`, `apply_override()`

---

### 3.3 Tool Specifications

#### **DATA ACQUISITION TOOLS**

##### Tool: `internal_claims_history`
```json
{
  "name": "internal_claims_history",
  "description": "Fetch prior loss history and policy details from internal claims systems",
  "input_schema": {
    "type": "object",
    "properties": {
      "applicant_id": {"type": "string", "description": "Applicant/company ID"},
      "applicant_name": {"type": "string", "description": "Business name"},
      "date_range_years": {"type": "integer", "default": 5}
    },
    "required": ["applicant_id"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "loss_runs": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "claim_id": {"type": "string"},
            "loss_date": {"type": "string", "format": "date"},
            "amount": {"type": "number"},
            "description": {"type": "string"}
          }
        }
      },
      "total_losses": {"type": "number"},
      "loss_frequency": {"type": "integer"},
      "policy_history": {
        "type": "array",
        "items": {"type": "object"}
      }
    }
  },
  "error_handling": "If applicant not found, return empty loss_runs; log warning"
}
```

##### Tool: `fetch_external_data`
```json
{
  "name": "fetch_external_data",
  "description": "Fetch external risk data from D&B, HazardHub, or similar providers",
  "input_schema": {
    "type": "object",
    "properties": {
      "applicant_name": {"type": "string"},
      "applicant_address": {"type": "string"},
      "data_sources": {
        "type": "array",
        "items": {"enum": ["dun_bradstreet", "hazardhub", "verisk"]},
        "default": ["dun_bradstreet", "hazardhub"]
      }
    },
    "required": ["applicant_name"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "credit_score": {"type": "number"},
      "financial_health": {"type": "string", "enum": ["strong", "good", "fair", "poor"]},
      "property_risk": {
        "type": "object",
        "properties": {
          "flood_zone": {"type": "string"},
          "distance_to_fire_station_miles": {"type": "number"},
          "crime_score": {"type": "number", "minimum": 0, "maximum": 100}
        }
      }
    }
  },
  "error_handling": "Timeout after 10s; return partial results (nulls for missing fields)"
}
```

##### Tool: `web_research_applicant`
```json
{
  "name": "web_research_applicant",
  "description": "Search applicant's website and public records for operational risk indicators",
  "input_schema": {
    "type": "object",
    "properties": {
      "applicant_name": {"type": "string"},
      "applicant_website": {"type": "string"}
    },
    "required": ["applicant_name"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "website_verified": {"type": "boolean"},
      "business_operations": {"type": "string"},
      "risk_flags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "e.g., ['Health code violations', 'Inconsistent product info']"
      },
      "public_reviews_summary": {"type": "string"}
    }
  },
  "error_handling": "If website not found, return website_verified=false; log search attempt"
}
```

---

#### **DOCUMENT UNDERSTANDING TOOLS**

##### Tool: `extract_structured_data`
```json
{
  "name": "extract_structured_data",
  "description": "Extract structured fields from submission documents (OCR + LLM schema mapping)",
  "input_schema": {
    "type": "object",
    "properties": {
      "document_content": {"type": "string", "description": "Raw text or base64-encoded image"},
      "target_schema": {"type": "string", "enum": ["general_submission", "property_form", "financial_form"]}
    },
    "required": ["document_content"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "extracted_fields": {
        "type": "object",
        "properties": {
          "applicant_name": {"type": "string"},
          "business_type": {"type": "string"},
          "address": {"type": "string"},
          "year_established": {"type": "integer"},
          "employees": {"type": "integer"},
          "annual_revenue": {"type": "number"},
          "square_footage": {"type": "number"}
        }
      },
      "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 1},
      "missing_fields": {"type": "array", "items": {"type": "string"}}
    }
  },
  "error_handling": "If OCR fails, return confidence=0; list all fields as missing"
}
```

##### Tool: `analyze_image_hazards`
```json
{
  "name": "analyze_image_hazards",
  "description": "Analyze inspection report images to detect structural hazards",
  "input_schema": {
    "type": "object",
    "properties": {
      "image_base64": {"type": "string"},
      "hazard_types": {
        "type": "array",
        "items": {"enum": ["electrical", "fire", "structural", "plumbing"]},
        "default": ["electrical", "fire", "structural"]
      }
    },
    "required": ["image_base64"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "hazards_detected": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "type": {"type": "string"},
            "description": {"type": "string"},
            "severity": {"enum": ["low", "medium", "high"]}
          }
        }
      },
      "analysis_confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
  },
  "error_handling": "If image is unreadable, return empty hazards_detected; log error"
}
```

---

#### **DECISION & LOGIC TOOLS**

##### Tool: `classify_naics_code`
```json
{
  "name": "classify_naics_code",
  "description": "Classify business into NAICS code based on business description",
  "input_schema": {
    "type": "object",
    "properties": {
      "business_description": {"type": "string"},
      "business_name": {"type": "string"}
    },
    "required": ["business_description"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "naics_code": {"type": "string", "pattern": "^\\d{6}$"},
      "industry": {"type": "string"},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
  },
  "error_handling": "If business description is ambiguous, return confidence < 0.7 and note ambiguity"
}
```

##### Tool: `validate_against_guidelines`
```json
{
  "name": "validate_against_guidelines",
  "description": "Check submission against underwriting guidelines (hard constraints)",
  "input_schema": {
    "type": "object",
    "properties": {
      "extracted_data": {"type": "object", "description": "Result from extract_structured_data"},
      "enriched_data": {"type": "object", "description": "Result from fetch_external_data"},
      "external_data": {"type": "object", "description": "Result from web_research_applicant"}
    },
    "required": ["extracted_data"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "passes_guidelines": {"type": "boolean"},
      "failed_rules": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "rule_id": {"type": "string"},
            "rule_description": {"type": "string"},
            "reason": {"type": "string"}
          }
        }
      },
      "missing_critical_docs": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  },
  "error_handling": "If guidelines not found, raise exception; system halts until config is fixed"
}
```

##### Tool: `calculate_risk_and_price`
```json
{
  "name": "calculate_risk_and_price",
  "description": "Perform risk scoring and pricing calculations",
  "input_schema": {
    "type": "object",
    "properties": {
      "extracted_data": {"type": "object"},
      "enriched_data": {"type": "object"},
      "loss_history": {"type": "object"}
    },
    "required": ["extracted_data"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "risk_score": {"type": "number", "minimum": 0, "maximum": 100},
      "loss_ratio": {"type": "number"},
      "debt_to_equity": {"type": "number"},
      "annual_premium": {"type": "number"},
      "pricing_rationale": {"type": "string"}
    }
  },
  "error_handling": "If data insufficient for calculation, return null premium; note missing data"
}
```

---

#### **COMMUNICATION TOOLS**

##### Tool: `draft_missing_info_email`
```json
{
  "name": "draft_missing_info_email",
  "description": "Draft email requesting missing documentation",
  "input_schema": {
    "type": "object",
    "properties": {
      "broker_email": {"type": "string"},
      "broker_name": {"type": "string"},
      "applicant_name": {"type": "string"},
      "missing_documents": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["broker_email", "missing_documents"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "subject": {"type": "string"},
      "body": {"type": "string"},
      "ready_to_send": {"type": "boolean", "description": "False for MVP (requires human review)"}
    }
  },
  "error_handling": "Always return draft (never fails)"
}
```

##### Tool: `draft_decline_letter`
```json
{
  "name": "draft_decline_letter",
  "description": "Draft decline letter citing specific guideline violations",
  "input_schema": {
    "type": "object",
    "properties": {
      "broker_email": {"type": "string"},
      "broker_name": {"type": "string"},
      "applicant_name": {"type": "string"},
      "failed_rules": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "rule_id": {"type": "string"},
            "rule_description": {"type": "string"},
            "reason": {"type": "string"}
          }
        }
      }
    },
    "required": ["broker_email", "failed_rules"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "subject": {"type": "string"},
      "body": {"type": "string"},
      "ready_to_send": {"type": "boolean", "description": "False for MVP (requires human review)"}
    }
  },
  "error_handling": "Always return draft (never fails)"
}
```

##### Tool: `draft_quote_email`
```json
{
  "name": "draft_quote_email",
  "description": "Draft email with quote and policy terms",
  "input_schema": {
    "type": "object",
    "properties": {
      "broker_email": {"type": "string"},
      "broker_name": {"type": "string"},
      "applicant_name": {"type": "string"},
      "quote_amount": {"type": "number"},
      "policy_term": {"type": "string"},
      "quote_pdf_url": {"type": "string"}
    },
    "required": ["broker_email", "quote_amount"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "subject": {"type": "string"},
      "body": {"type": "string"},
      "ready_to_send": {"type": "boolean"}
    }
  },
  "error_handling": "Always return draft (never fails)"
}
```

---

### 3.4 Orchestration Plan (Mapped to Workflow Diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1: INGESTION & TRIAGE                                         │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Submission Received
  ▼ Input: Email with attachments (PDFs, images, text body)
  └─► Action: Trigger LanGraph SupervisorAgent
      State: { submission_id, timestamp, email_subject, attachments[] }

Step 2: Ingest & Classify
  ▼ Agent: ClassificationAgent.ingest_and_classify()
      Tool: Splits email body from attachments; identifies document types
      Tool: extract_structured_data() on email body + each attachment
  └─► Output: { extracted_fields, document_types, extraction_confidence }
      State Update: extracted_data = {...}

Step 3: Enrichment (PARALLEL EXECUTION)
  ▼ Agent: DataRetrieverAgent_Internal.fetch()
      Tool: internal_claims_history(applicant_id)
      └─► loss_runs, policy_history
  ▼ Agent: DataRetrieverAgent_External.fetch()
      Tool: fetch_external_data(applicant_name, applicant_address)
      └─► credit_score, financial_health, property_risk
  ▼ Agent: DataRetrieverAgent_OpenSource.fetch()
      Tool: web_research_applicant(applicant_name, website)
      └─► business_operations, risk_flags, reviews_summary
  └─► State Update: internal_data = {...}, external_data = {...}, web_data = {...}

┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: QUALIFICATION                                              │
└─────────────────────────────────────────────────────────────────────┘

Step 4: Gap Analysis
  ▼ Agent: AnalystAgent_GapAnalysis.analyze()
      Tool: validate_against_guidelines(extracted_data, enriched_data)
      └─► passes_guidelines, failed_rules[], missing_critical_docs[]
      
  IF missing_critical_docs.length > 0:
    ▼ Action: Route to "Missing Info" branch
        Tool: draft_missing_info_email(broker_email, missing_documents)
        State Update: decision = "MISSING_INFO", drafted_email = {...}
        ▼ Return: Missing Info Email (for human review + send)
        END (await resubmission)
  
  IF failed_rules.length > 0:
    ▼ Action: Route to "Decline" branch
        Tool: draft_decline_letter(broker_email, failed_rules)
        State Update: decision = "DECLINED", drafted_letter = {...}
        ▼ Return: Decline Letter (for human review + send)
        END (submit decline)
  
  ELSE: Continue to Step 5

Step 5: Risk Assessment
  ▼ Agent: AnalystAgent_RiskAssessment.assess()
      Tool: classify_naics_code(business_description)
      └─► naics_code, industry
      Tool: calculate_risk_and_price(extracted_data, enriched_data, loss_history)
      └─► risk_score, loss_ratio, premium
      State Update: naics_code = {...}, risk_metrics = {...}, premium = {...}

┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: OUTPUT GENERATION                                          │
└─────────────────────────────────────────────────────────────────────┘

Step 6: Generate Quote Package
  ▼ Agent: OutputAgent.generate()
      Tool: generate_quote_pdf(extracted_data, risk_metrics, premium)
      └─► quote_pdf_s3_url
      Tool: draft_quote_email(broker_email, premium, quote_url)
      └─► draft_email
      State Update: decision = "QUOTED", quote_url = {...}, drafted_email = {...}
      
Step 7: Update State (Human Workbench - Phase 3)
  ▼ Endpoint: POST /override/{submission_id}
      Input: { override_decision, override_reason, override_user }
      Action: Apply override to state
      Tool: log_audit_trail(submission_id, override_decision, override_reason)
      State Update: overrides[] += {...}

┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT: Final State                                                  │
└─────────────────────────────────────────────────────────────────────┘

{
  "submission_id": "SUB-2026-00001",
  "status": "QUOTED|DECLINED|MISSING_INFO",
  "decision": {...},
  "drafted_output": {
    "email_subject": "...",
    "email_body": "...",
    "pdf_url": "..."  (if quoted)
  },
  "audit_trail": [
    { timestamp, agent, action, tool, result, rule_applied }
  ],
  "overrides": [
    { timestamp, user, override_decision, override_reason }
  ]
}
```

---

## 4. TOOL ORCHESTRATION TABLE

| Agent | Tool | Purpose | Input | Output | Timeout | Retry |
|-------|------|---------|-------|--------|---------|-------|
| DataRetriever (Internal) | `internal_claims_history` | Fetch loss runs | applicant_id | loss_runs[] | 10s | 2x |
| DataRetriever (External) | `fetch_external_data` | Fetch D&B/HazardHub | applicant_name, address | credit_score, property_risk | 10s | 2x |
| DataRetriever (Web) | `web_research_applicant` | Scrape applicant site | applicant_name, website | risk_flags[] | 15s | 1x |
| Analyst (Classification) | `classify_naics_code` | Map to NAICS | business_desc | naics_code, industry | 5s | 0x (LLM call) |
| Analyst (Gap) | `validate_against_guidelines` | Check rules | extracted_data | passes_guidelines, failed_rules[] | 5s | 0x |
| Analyst (Risk) | `calculate_risk_and_price` | Price submission | extracted_data, enriched_data, losses | risk_score, premium | 5s | 0x |
| Output | `draft_missing_info_email` | Compose email | broker_email, missing_docs | draft_email | 3s | 0x |
| Output | `draft_decline_letter` | Compose decline | broker_email, failed_rules | draft_letter | 3s | 0x |
| Output | `draft_quote_email` | Compose quote | broker_email, premium | draft_email | 3s | 0x |

---

## 5. ERROR HANDLING STRATEGY

### Transient Errors (Retry)
- External API timeouts (D&B, HazardHub): Retry 2x with exponential backoff
- Internal DB unavailable: Retry 2x; fail if persistent
- Network timeouts: Retry 1x; fail if persistent

### Permanent Errors (Fail Fast)
- Invalid guidelines config: Raise SystemError; halt processing
- OCR/extraction confidence < 50%: Flag for manual review; do NOT proceed
- Missing required input fields: Reject submission; return error

### Fallback Behaviors
- External data unavailable: Proceed with internal data only (note in audit)
- Web research fails: Skip risk flags; proceed with other data
- Price calculation fails: Return null premium; mark for manual review

---

## 6. LANGGRAPH STATE SCHEMA

```python
from typing import TypedDict, Optional, List

class SubmissionState(TypedDict):
    """State object passed through LanGraph workflow"""
    
    # Input
    submission_id: str
    email_subject: str
    email_body: str
    attachments: List[dict]  # [{"filename": "...", "content": "...", "type": "..."}]
    broker_email: str
    broker_name: str
    
    # Phase 1: Extraction
    extracted_data: Optional[dict]  # From OCR + schema mapping
    extraction_confidence: Optional[float]
    document_types: Optional[List[str]]
    
    # Phase 2a: Enrichment (parallel)
    internal_data: Optional[dict]  # loss runs, policy history
    external_data: Optional[dict]  # credit_score, property_risk
    web_data: Optional[dict]  # risk_flags, reviews
    
    # Phase 2b: Analysis
    naics_code: Optional[str]
    classification_confidence: Optional[float]
    validation_result: Optional[dict]  # {passes_guidelines, failed_rules, missing_docs}
    risk_metrics: Optional[dict]  # {risk_score, loss_ratio, debt_to_equity, premium}
    
    # Phase 3: Output
    decision: str  # "QUOTED", "DECLINED", "MISSING_INFO", "MANUAL_REVIEW"
    drafted_email: Optional[dict]  # {subject, body, ready_to_send}
    quote_pdf_url: Optional[str]
    
    # Metadata
    status: str
    errors: List[dict]
    audit_trail: List[dict]
    overrides: List[dict]
    created_at: str
    updated_at: str
```

---

## 7. WORKFLOW DECISION TREE

```
START: Submission Received
  │
  ├─► Extract + Classify
  │    │
  │    ├─► Confidence < 50% ? ──► MANUAL_REVIEW
  │    │
  │    └─► Confidence >= 50% ? ──► Continue
  │
  ├─► Enrich (parallel) + Validate Guidelines
  │    │
  │    ├─► Missing Critical Docs ? ──► DRAFT MISSING_INFO_EMAIL ──► END
  │    │
  │    ├─► Failed Hard Rules ? ──► DRAFT DECLINE_LETTER ──► END
  │    │
  │    └─► Passed All Rules ? ──► Continue
  │
  ├─► Risk Assessment + Pricing
  │    │
  │    ├─► Calculation Failed ? ──► MANUAL_REVIEW
  │    │
  │    └─► Success ? ──► Continue
  │
  ├─► Generate Quote + Email
  │    │
  │    └─► DRAFT QUOTE_EMAIL ──► END
  │
  └─► RETURN: Final State (ready for human review/send)
```

---

## END OF SPECIFICATION
