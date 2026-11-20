OpsResolve AI
AI-Powered Operations Assistance and Incident Resolution

OpsResolve AI is a Python-based enterprise AI application that helps operations users diagnose application concerns, identify evidence-backed root causes, follow self-service resolution steps, and raise incidents only when investigation or controlled changes are required.

The current portfolio demonstration uses a fully synthetic billing-operations knowledge base. The architecture also includes a disabled-by-default, read-only integration layer for an Oracle-based IMS DPT1 operational database.

Portfolio project: All business rules, operational records, incidents, identifiers, database views, and examples included in this repository are synthetic.

Business Problem
Enterprise application users often depend on support teams for routine operational questions such as:

Why an invoice batch cannot be exported
Why a D2021 file remains unprocessed
Which workflow status is required before an action
Which role can authorize an invoice
Why a file-processing step failed
Which operational report contains a required value
Whether a concern can be resolved by the user
Whether an incident must be raised for investigation or data correction
This dependency increases support workload and can delay routine operations.

OpsResolve AI provides a self-service operations experience by retrieving applicable rules and known incident evidence, producing a concise root cause, and recommending ordered resolution steps.

If the concern requires a permission change, configuration investigation, infrastructure investigation, or production-data correction, the user can raise an incident directly from the AI-assisted response.

User-Facing Capabilities
1. Operations Assistant
Users provide:

Operational question
Application area
Current workflow status
Attempted action
Visible error, if available
Batch, invoice, or file reference, if available
OpsResolve AI returns:

A concise response
The most likely root cause
Ordered resolution steps
Supporting business-rule and incident evidence
A Resolved My Issue action
A Raise Incident action
The interface intentionally does not expose:

AI provider names
Model names
Confidence percentages
Vector scores
Reranker scores
Token usage
Estimated API cost
These details are retained in backend telemetry rather than presented to operations users.

2. Incident Management
When self-service resolution is not sufficient, the user can raise an incident from the Operations Assistant response.

The incident is prefilled with:

Incident title
Issue description
Application area
Current status
Attempted action
Visible error
Operational reference
AI-identified root cause
Steps already attempted
Business impact
Priority
Contact or reference information
Users can also view incident history, including:

Incident reference
Title
Priority
Status
Root cause
Created date
Last updated date
Resolution notes
3. Resolution Workspace
The Resolution Workspace supports incidents that require additional investigation or controlled changes.

Capabilities include:

Investigation tracking
Root-cause confirmation
Resolution-note capture
Incident-status updates
Resolution history
Validated resolution storage
Reuse of confirmed resolutions as future case memory
4. Knowledge and Evidence
Users can browse synthetic operational guidance covering:

Invoice lifecycle
Batch operations
D2021 processing
Access and authorization
Operational runbooks
Reports
Known incident patterns
AI governance rules
End-to-End Workflow
User Operational Concern
          |
          v
Input Validation and Identifier Masking
          |
          v
Intent Classification
          |
          v
Read-Only IMS DPT1 Context, when enabled
          +
Synthetic Business Rules and Runbooks
          |
          v
Intent-Aware Hybrid Retrieval
          |
          v
Evidence Deduplication and Validation
          |
          v
Grounded Root-Cause Generation
          |
          v
Ordered Resolution Steps
          |
          v
Can the user resolve the concern?
          |
          +---- Yes ----> Record Self-Service Resolution
          |
          +---- No -----> Prefill and Raise Incident
                              |
                              v
                     Resolution Workspace
                              |
                              v
                     Confirmed Resolution Memory
AI and Retrieval Architecture
OpsResolve AI uses a multi-stage retrieval and generation pipeline.

Synthetic Knowledge Sources
Business Rules | Runbooks | Incident Patterns | Report Definitions
                              |
                              v
Document Validation and Incremental Ingestion
                              |
                              v
Structure-Aware and Incident-Aware Chunking
                              |
                              v
Dense Semantic Retrieval + Lexical Retrieval
                              |
                              v
Reciprocal Rank Fusion
                              |
                              v
Intent-Aware Ranking and Parent Deduplication
                              |
                              v
Evidence Sufficiency and Citation Validation
                              |
                              v
Grounded Root-Cause Response
                              |
                              v
Human-Readable Resolution or Incident Escalation
System Architecture
flowchart LR
    U[Operations User] --> UI[OpsResolve AI Web Application]

    UI --> G[Input Guardrails]
    G --> I[Intent Classification]

    I --> DB[Read-Only IMS DPT1 Context]
    I --> R[Hybrid Knowledge Retrieval]

    DB --> V[Evidence Validation]
    R --> V

    V --> L[Grounded Root-Cause Generation]
    L --> S[Self-Service Resolution]

    S -->|Resolved| M[Validated Resolution Memory]
    S -->|Investigation Required| INC[Incident Management]

    INC --> W[Resolution Workspace]
    W --> M
AI Processing Pipeline
flowchart TD
    Q[Operational Question] --> MASK[Identifier and Secret Masking]
    MASK --> CLASSIFY[Intent Classification]

    CLASSIFY --> SEM[Gemini Semantic Retrieval]
    CLASSIFY --> LEX[TF-IDF Lexical Retrieval]

    SEM --> RRF[Reciprocal Rank Fusion]
    LEX --> RRF

    RRF --> RANK[Intent-Aware Ranking]
    RANK --> DEDUP[Parent-Document Deduplication]
    DEDUP --> VALIDATE[Evidence Sufficiency Validation]

    VALIDATE --> GEN[Groq or OpenRouter]
    GEN --> FALLBACK[Deterministic Evidence Fallback]
    FALLBACK --> RESPONSE[Root Cause and Resolution Steps]
Incident Resolution Flow
flowchart TD
    A[User Submits Operational Concern] --> B[OpsResolve AI Response]
    B --> C{Issue Resolved?}

    C -->|Yes| D[Record Self-Service Resolution]
    C -->|No| E[Prefill Incident]

    E --> F[User Adds Impact and Priority]
    F --> G[Raise Incident]
    G --> H[Resolution Workspace]

    H --> I[Confirm Root Cause]
    I --> J[Record Resolution]
    J --> K[Store Validated Case Memory]
Retrieval Components
Gemini embeddings for semantic retrieval
TF-IDF lexical retrieval for exact operational terminology
Reciprocal Rank Fusion for combining retrieval methods
Intent-aware document boosting and suppression
Parent-document deduplication
Cross-domain evidence selection
Context-window budgeting
Evidence-sufficiency validation
Citation allow-listing
Generation Components
Groq as a primary generation provider
OpenRouter as a provider fallback
Deterministic evidence-based fallback when external providers are unavailable
Structured JSON response validation
Unsupported-citation removal
Safe refusal when evidence is insufficient
Agentic Investigation Workflow
OpsResolve AI uses a controlled investigation workflow rather than an unrestricted autonomous agent.

Classify Issue
      |
      v
Build Investigation Plan
      |
      v
Retrieve Operational Evidence
      |
      v
Validate Evidence Sufficiency
      |
      v
Generate Root-Cause Diagnosis
      |
      v
Search Similar Validated Cases
      |
      v
Persist Conversation and Case Memory
      |
      v
Respond or Escalate
The agent does not:

Execute arbitrary SQL
Update production records
Modify invoices
Change application permissions
Bypass approval processes
Execute generated scripts against production systems
IMS DPT1 Database Integration
The project contains a read-only Oracle integration layer for future IMS DPT1 connectivity.

Database access is disabled by default:

IMS_DB_ENABLED=false
When approved access is available, OpsResolve AI can retrieve operational context through predefined parameterized queries.

Planned read-only views include:

ims_ai_batch_status_v
ims_ai_invoice_status_v
ims_ai_file_status_v
ims_ai_incident_history_v
Database Security Design
Read-only database user
Approved operational views only
Parameterized queries
No arbitrary SQL from users
No arbitrary SQL generated by the LLM
No insert, update, delete, truncate, or DDL operations
Database access is optional and not required for application startup
Database credentials are supplied through environment variables and never committed
Example configuration:

IMS_DB_ENABLED=false
IMS_DB_HOST=dpt1-database-host
IMS_DB_PORT=1521
IMS_DB_SERVICE_NAME=DPT1
IMS_DB_USERNAME=READ_ONLY_AI_USER
IMS_DB_PASSWORD=SET_LOCALLY_ONLY
Engineering Capabilities
The project implements the following production-oriented AI engineering capabilities:

Data Ingestion and Chunking
Synthetic-document enforcement
JSON, Markdown, TXT, and CSV ingestion
Content hashing
Incremental change detection
Document version metadata
Parent-child chunks
Incident symptom, cause, and resolution chunking
Token estimates
Ingestion audit history
Retrieval
Dense semantic retrieval
Lexical retrieval
Reciprocal Rank Fusion
Intent-aware ranking
Exact operational-term handling
Metadata filtering
Parent-document deduplication
Cross-domain evidence coverage
Dynamic evidence depth
Guardrails
Prompt-injection detection
Production-write instruction blocking
Identifier masking
Email masking
API-key pattern masking
Evidence-content validation
Citation allow-listing
Evidence-sufficiency scoring
Safe refusal
Human escalation for controlled changes
Memory and Persistence
Conversation memory
Investigation memory
Incident history
Validated resolution memory
Self-service resolution records
Query-response cache
Operational request telemetry
Context and Cost Engineering
Context deduplication
Token-budget enforcement
Dynamic evidence limits
Query caching
Input-token estimates
Context-token estimates
Output-token estimates
Estimated API-cost tracking
Stage-level latency measurement
Production Engineering
Health endpoint
Readiness endpoint
Automated tests
Sensitive-file validation
Docker image build
GitHub Actions CI/CD
Environment-based configuration
Technology Stack
Area	Technology
Programming language	Python 3.13
Web framework	Starlette
Application server	Uvicorn
Data processing	pandas and NumPy
Lexical retrieval	scikit-learn TF-IDF
Semantic retrieval	Gemini embeddings
AI generation	Groq and OpenRouter
Enterprise database integration	OracleDB
Local persistence	SQLite
Testing	pytest
Containerization	Docker
CI/CD	GitHub Actions
Version control	Git and GitHub
Project Structure
.
├── opsresolve_ai_app.py
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── .dockerignore
├── .env.example
├── README.md
├── app/
│   ├── ai/
│   │   ├── investigation_agent.py
│   │   ├── opsresolve_service.py
│   │   ├── relevance.py
│   │   └── support_engine.py
│   ├── analytics/
│   │   └── service.py
│   ├── cases/
│   │   └── service.py
│   ├── chunking/
│   │   └── strategies.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging_config.py
│   ├── database/
│   │   └── repository.py
│   ├── guardrails/
│   │   ├── pipeline.py
│   │   └── safety.py
│   ├── health/
│   │   └── service.py
│   ├── incidents/
│   │   └── service.py
│   ├── ingestion/
│   │   ├── loaders.py
│   │   ├── models.py
│   │   └── pipeline.py
│   ├── memory/
│   │   └── case_memory.py
│   ├── operations/
│   │   ├── context_budget.py
│   │   ├── optimized_pipeline.py
│   │   └── store.py
│   ├── repository/
│   │   └── metadata.py
│   └── retrieval/
├── evaluation/
│   └── rag_evaluation_set.json
├── knowledge_base/
│   └── source/
│       └── domain_corpus.json
├── scripts/
│   ├── run_ingestion.py
│   ├── run_chunking.py
│   └── run_rag_evaluation.py
├── tests/
│   ├── conftest.py
│   ├── test_incidents.py
│   └── test_opsresolve.py
└── .github/
    └── workflows/
        └── ci.yml
Measured RAG Evaluation Results
The retrieval evaluation uses a labelled synthetic operational-question set.

Metric	Result
Recall@5	93.75%
Precision@5	47.08%
Mean Reciprocal Rank	1.00
Intent accuracy	100%
Guardrail accuracy	100%
Forbidden-document rate	0%
Average retrieval latency	1,601 ms
Quality gate	Passed
Interpretation
Recall@5 of 93.75% means almost all expected evidence was present in the first five retrieved documents.
Mean Reciprocal Rank of 1.00 means the first relevant document ranked first for every evaluated retrieval question.
Intent accuracy of 100% means the evaluation questions were classified into the correct operational intent.
Guardrail accuracy of 100% means the tested prompt-injection and unsafe-write requests were blocked.
Forbidden-document rate of 0% means explicitly irrelevant evidence was not retrieved for the labelled questions.
Precision@5 of 47.08% remains an optimization area because the first five results sometimes include supporting documents beyond the narrowly labelled expected-document set.
The evaluation results are synthetic and should not be interpreted as production accuracy.

Automated Testing
The current automated test suite reports:

9 passed
The tests cover:

Incident creation
Incident-history persistence
Incident-resolution validation
Health-service response
Readiness-component validation
IMS DPT1 disabled-by-default behavior
Prevention of arbitrary SQL execution
Prompt-injection blocking
Sensitive identifier masking
Run the tests with:

python -m pytest -v
On the restricted development VM, the configured Python installation can be used:

& "Q:\Rajkumar\Python313\python.exe" -m pytest -v
Health and Readiness
OpsResolve AI provides two operational endpoints.

Health
GET /health
Example:

{
  "status": "UP",
  "application": "OpsResolve AI"
}
Readiness
GET /ready
The readiness response checks:

Synthetic knowledge availability
Incident-store availability
Optional IMS DPT1 configuration state
IMS DPT1 is not required for application startup.

Local Setup
1. Create a virtual environment
python -m venv .venv
Activate:

& ".\.venv\Scripts\Activate.ps1"
2. Install dependencies
python -m pip install -r requirements.txt
3. Configure environment variables
Use .env.example as the configuration reference.

Do not commit a real .env file.

4. Prepare the synthetic knowledge base
Run ingestion:

python ".\scripts\run_ingestion.py"
Run chunking:

python ".\scripts\run_chunking.py" `
    --max-words 220 `
    --overlap 1
5. Start the application
python -m uvicorn `
    opsresolve_ai_app:application `
    --host 127.0.0.1 `
    --port 8610
Open:

http://127.0.0.1:8610
Docker
Build the image:

docker build -t opsresolve-ai:1.0 .
Run the container:

docker run --rm -p 8610:8610 opsresolve-ai:1.0
The image exposes:

8610
The Docker health check calls:

http://127.0.0.1:8610/health
A local Docker installation is not required for development in the restricted client VM because the image build is validated through GitHub Actions.

CI/CD
The GitHub Actions workflow runs on every push and pull request to main.

The pipeline performs:

Repository checkout
Python 3.13 setup
Dependency installation
Python source compilation
Automated tests
Sensitive-file validation
Docker image build
Current CI result:

Python tests and security checks: Passed
Docker build: Passed
Security and Privacy Controls
Synthetic knowledge only
Prompt-injection detection
Production-write instruction blocking
Identifier masking
Email-address masking
API-key pattern masking
No arbitrary SQL execution
Parameterized read-only Oracle queries
Evidence-based citations
Unsupported-citation removal
Evidence-sufficiency validation
Safe refusal for unsupported requests
Human escalation for controlled changes
Secrets excluded from Git
Runtime databases excluded from Git
No autonomous production updates
Files Excluded from Git
The repository excludes:

.venv/
__pycache__/
*.pyc
.streamlit/secrets.toml
.env
data/*.db
data/*.db-shm
data/*.db-wal
data/cache/
logs/
Current Limitations
IMS DPT1 integration is prepared but disabled.
Demonstration knowledge and incidents are synthetic.
Precision@5 requires further optimization.
Authentication and role-based access control are not yet implemented.
External AI-provider behavior depends on network and API availability.
The deterministic evidence fallback produces grounded responses when AI providers are unavailable.
The project is a portfolio prototype and not a production deployment.
Planned Enhancements
Enable approved read-only IMS DPT1 integration
Add enterprise authentication using Microsoft Entra ID
Add role-based access control
Add production-grade secret management
Add dynamic metadata filters by application area and user role
Add retrieval reranking regression tests
Improve Precision@5 without reducing Recall@5
Add incident assignment and notification integration
Add ServiceNow or Jira incident integration
Add PostgreSQL persistence for multi-user deployment
Add centralized application tracing and monitoring
Add user-feedback evaluation loops
Resume-Ready Project Description
OpsResolve AI
Python | Starlette | Uvicorn | scikit-learn | Gemini Embeddings | Groq | OpenRouter | OracleDB | SQLite | pytest | Docker | GitHub Actions

Built a Python enterprise AI application for self-service operational support and incident resolution. Implemented intent-aware hybrid retrieval using Gemini embeddings, TF-IDF, and Reciprocal Rank Fusion; grounded root-cause generation with Groq/OpenRouter failover; prompt-injection and privacy guardrails; persistent incident history; read-only Oracle integration; automated RAG evaluation; Docker deployment; and GitHub Actions CI/CD.

Achieved:

93.75% Recall@5
1.00 Mean Reciprocal Rank
100% intent accuracy
100% guardrail accuracy
0% forbidden-document rate
9 automated tests passed
Successful Docker build through CI/CD
Disclaimer
OpsResolve AI is an independently developed portfolio project.

The repository does not contain:

Client source code
Production IMS documentation
Real incidents
Real invoices
Real MPANs
Production database credentials
Production SQL
Internal screenshots
Confidential operational data
All included business rules, records, database-view names, incidents, and identifiers are synthetic.