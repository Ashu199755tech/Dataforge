# DataFlow Enterprise

> Independent, enterprise-grade, low-code/no-code data integration and orchestration platform.

DataFlow Enterprise provides an architectural alternative to proprietary cloud data integration tools (such as Azure Data Factory or AWS Glue). It offers visual pipeline authoring, topological DAG execution, schema discovery, chunked streaming data movement, incremental watermark loading, inline data quality validation, and live execution observability—while maintaining clean-room vendor independence.

---

## Development Governance & Quality Guardrails

All development work on DataForge is strictly governed by mandatory engineering rules, quality controls, and architectural guardrails defined in [GEMINI.md](GEMINI.md). Every development session must comply with these standards.

- **[GEMINI.md](GEMINI.md)**: Mandatory development rules (functionality protection, scope control, code quality, testing pyramid, security, bounded streaming, error handling).
- **[MILESTONE_TRACKER.md](MILESTONE_TRACKER.md)**: Master milestone execution ledger and approval gates.
- **[TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md)**: Architectural Decision Records (ADR 001 – ADR 023).

---

## Key Highlights & Architectural Pillars

- **Visual Pipeline Designer**: Drag-and-drop workflow canvas built with React Flow, supporting infinite pan, zoom, custom activity nodes, dependency routing, and interactive node configuration.
- **Pluggable Connector SDK**: Clean abstraction (`BaseConnector`) with native implementations for PostgreSQL, MySQL, and SQLite. Features live connection testing, schema discovery, and low-memory streaming.
- **Resilient DAG Execution Engine**: Topological sort, cycle detection, conditional edge branching (Succeeded / Failed / Completed), retry policies, and granular status checkpoints.
- **Copy Data Streaming Engine**: High-performance chunked generator streaming (5,000–10,000 rows/batch) with column mapping, upsert/merge logic, and watermark-based delta ingestion.
- **Integrated Data Quality (DQ)**: Built-in data quality validation rules (NotNull, Unique, PositiveNumeric, Range) executed directly in-pipeline with SLA threshold enforcement.
- **Zero-Plaintext Security**: Secrets, database passwords, and API tokens are encrypted at rest using AES-256 Fernet symmetric cryptography and masked across all REST APIs.
- **100% Clean-Room Architecture**: Developed independently with zero proprietary cloud code or trade dress reproduction.

---

## Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── activities/        # Pluggable Activity Framework (CopyData, SqlScript, DQ)
│   │   ├── api/               # REST Endpoints (Auth, Workspaces, Connections, Pipelines, Runs)
│   │   ├── connectors/        # Pluggable Connector SDK (PostgreSQL, MySQL, SQLite)
│   │   ├── core/              # Config, Database Session, AES Encryption, Security
│   │   ├── execution/         # DAG Topological Resolver, Runner, Event Bus
│   │   ├── models/            # Normalized SQLAlchemy 2.0 ORM Models
│   │   ├── schemas/           # Pydantic Request/Response Models
│   │   └── main.py            # FastAPI Entrypoint & Static Frontend Mount
│   ├── tests/                 # Automated Pytest Suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/        # Design System (Navbar, Sidebar)
│   │   ├── features/          # Visual Pipeline Designer (React Flow Canvas, Toolbox, Drawer)
│   │   ├── pages/             # Dashboard, Connections, Pipelines, Runs Monitor, Data Quality
│   │   ├── store/             # Zustand State Stores
│   │   └── types/             # TypeScript Schemas
│   └── package.json
├── docs/                      # Architectural PRD, HLD, LLD, ERD, Threat Model, Roadmap
├── scripts/
│   ├── start_platform.sh      # One-click startup for DBs & Platform
│   ├── stop_platform.sh       # Clean shutdown script
│   └── run_mvp_verification.py# Automated End-to-End MySQL -> PostgreSQL Verification
└── docker-compose.yml
```

---

## Quickstart & Local Execution

### 1. Start the Platform
To start PostgreSQL, MySQL, and the DataFlow Enterprise server:

```bash
./scripts/start_platform.sh
```

- Web UI: [http://localhost:8000](http://localhost:8000)
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Endpoint: [http://localhost:8000/health](http://localhost:8000/health)

### 2. Run Automated Pytest Suite
```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -v
```

### 3. Run the Milestone 1 End-to-End Verification
Executes real ingestion: **MySQL Source (port 3307) -> Copy Data Activity -> PostgreSQL Destination (port 5433)**:

```bash
PYTHONPATH=. ./venv/bin/python3 scripts/run_mvp_verification.py
```

This verification automatically:
1. Validates connection health for both MySQL and PostgreSQL.
2. Discovers schema, tables, and column metadata from MySQL.
3. Assembles a DAG pipeline with `CopyData` and `DataQualityCheck`.
4. Executes **Run #1 (Full Load)**, copying 5 initial order records to PostgreSQL.
5. Runs SQL queries on PostgreSQL to verify row parity and runs Data Quality validations.
6. Inserts 2 new records into MySQL with new timestamps.
7. Executes **Run #2 (Incremental Load)** using a watermark filter, verifying that only the 2 delta records are ingested.
8. Verifies that the PostgreSQL warehouse table contains exactly 7 records.

---

## Architectural Documentation & Governance
Core governance and design documents:
- [`GEMINI.md`](GEMINI.md): Mandatory Project-Level Development Governance & Quality Guardrails
- [`MILESTONE_TRACKER.md`](MILESTONE_TRACKER.md): Master Milestone Execution Ledger
- [`TECHNICAL_DECISIONS.md`](TECHNICAL_DECISIONS.md): Master Architectural Decision Records (ADR 001 – ADR 023)

Detailed design specifications in `docs/`:
- [`01_PRD.md`](docs/architecture/01_PRD.md): Product Requirements Document
- [`02_HLD.md`](docs/architecture/02_HLD.md): High-Level Design & Control/Execution Separation
- [`03_LLD.md`](docs/architecture/03_LLD.md): Low-Level Design & DAG State Machine
- [`04_ARCH_DIAGRAMS.md`](docs/architecture/04_ARCH_DIAGRAMS.md): Mermaid Architecture & Sequence Diagrams
- [`05_ERD_AND_SCHEMA.md`](docs/database/05_ERD_AND_SCHEMA.md): Database Entity-Relationship Specification
- [`06_API_SPECIFICATIONS.md`](docs/api/06_API_SPECIFICATIONS.md): REST API Documentation
- [`07_REPO_STRUCTURE.md`](docs/architecture/07_REPO_STRUCTURE.md): Repository Tree
- [`08_DEVELOPMENT_ROADMAP.md`](docs/architecture/08_DEVELOPMENT_ROADMAP.md): Phases 1 through 4 Roadmap
- [`09_THREAT_MODEL.md`](docs/security/09_THREAT_MODEL.md): STRIDE Threat Model & Mitigations
- [`10_TESTING_STRATEGY.md`](docs/testing/10_TESTING_STRATEGY.md): Testing Pyramid & Test Cases
- [`11_DEPENDENCY_AND_LICENSING.md`](docs/architecture/11_DEPENDENCY_AND_LICENSING.md): Open-source license inventory

---

## Default Credentials
- **Admin Email**: `admin@dataflow.enterprise`
- **Admin Password**: `AdminPass123!`
- **Metadata Database**: PostgreSQL on `localhost:5433` (db: `dataflow_metadata`)
