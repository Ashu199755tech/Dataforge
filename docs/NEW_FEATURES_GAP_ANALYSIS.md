# DataForge — Six New Enterprise Features: Gap Analysis

## 1. Executive Summary

This document performs an exhaustive audit of the existing DataForge codebase against the six newly requested enterprise features:
1. **Integration Runtime Manager**
2. **Reusable Dataset Management**
3. **Advanced Trigger Management**
4. **Git Integration and CI/CD**
5. **Data Lineage and Impact Analysis**
6. **Advanced Monitoring and Observability**

The analysis classifies existing capabilities, identifies missing functionality, and details the exact integration points within the current application architecture.

---

## 2. Feature-by-Feature Gap Analysis Matrix

| Feature | Existing Capabilities in Codebase | Missing Capabilities | Complexity & Integration Scope |
| :--- | :--- | :--- | :--- |
| **1. Integration Runtime Manager** | Local worker thread pool (`backend/app/execution/worker.py`), basic process telemetry (`get_worker_telemetry`), `PipelineRunner.execute_sync()`. | • Cloud, Self-Hosted (Linux/Windows), and Local Dev runtime entities.<br>• Secure agent registration via token exchange.<br>• Heartbeat, capacity, and online/offline detection daemon.<br>• Runtime task queue with dispatch, recovery, and retry.<br>• Pipeline & activity runtime assignment.<br>• Runtime Manager frontend page and activity selector. | High. Requires new runtime agent daemon, secure polling protocol, and scheduler decoupling. |
| **2. Reusable Dataset Management** | Multi-cloud connectors (Azure, AWS, GCS, PostgreSQL, MySQL, SQLite, Local), 8 file format engines (`backend/app/formats/`), low-memory preview API, schema discovery (`discover_schema()`). | • First-class `Dataset` and `DatasetVersion` models.<br>• Parameterized locations and dynamic expression resolution.<br>• Schema drift detection and drift alerting.<br>• Dataset preview API and usage dependency tracking.<br>• Copy Data activity integration with dataset references.<br>• Dataset Management frontend page (wizard, viewer, preview). | Medium-High. Reuses format framework & connectors; requires Copy Data activity refactoring to accept dataset references. |
| **3. Advanced Trigger Management** | Basic CRON trigger scheduler (`scheduler.py`) using `croniter`, simple `Trigger` model, basic CRUD API (`triggers.py`), simple schedule modal in `TriggersPage.tsx`. | • Manual Trigger execution mode.<br>• Schedule Triggers with timezones, start/end boundaries, and visual recurrence.<br>• Storage Event Triggers (file arrival in S3/ADLS/GCS, prefix/suffix filters, deduplication).<br>• Tumbling Window Triggers (fixed windows, dependencies, retry missed windows).<br>• Pipeline Dependency Triggers (downstream pipeline triggered on upstream status).<br>• Trigger execution run history and recovery.<br>• Complete frontend Trigger Management page overhaul. | High. Requires event listener engine, tumbling window state machine, and dependency hooks. |
| **4. Git Integration and CI/CD** | Immutable pipeline versioning (`PipelineVersion`), initial environment promotion (`promotion.py`, `environments.py`), audit trail. | • GitHub & GitLab repository connection and token management.<br>• Git provider abstraction (`BaseGitProvider`, `GitHubProvider`).<br>• Resource serialization (pipelines, datasets, triggers, dataflows to canonical JSON).<br>• Branch switching, change diffing, commit/push/pull via API.<br>• Multi-stage CI/CD promotion (Dev $\to$ Test $\to$ Staging $\to$ Prod).<br>• Deployment approval gates and deployment history.<br>• GitHub Actions workflow generator.<br>• Source control & branch UI widgets. | High. Requires Git provider integration, canonical serialization, and visual diff viewer. |
| **5. Data Lineage and Impact Analysis** | Pipeline DAG activity graph (`PipelineDAG`), DataFlow transformation graph (`DataFlowEngine`), column mapping configurations in Copy Data. | • Automated pipeline-level lineage extractor.<br>• Column-level lineage parser for Copy Data and DataFlows.<br>• Lineage graph data model and REST API.<br>• Downstream/upstream impact analysis engine.<br>• Interactive Lineage Explorer frontend using React Flow graph. | Medium-High. Requires static analysis of pipeline JSON, column mapping graph resolution, and React Flow UI. |
| **6. Advanced Monitoring & Observability** | Execution Gantt timeline, error classification, basic metrics summary, basic alert rules (failure, success, duration, DQ score), `RunsMonitorPage.tsx`. | • Copy Data transfer analytics (rejected rows, throughput MB/s, file/partition count).<br>• Integration Runtime fleet metrics (CPU/RAM telemetry, active executions, queue depth).<br>• Multi-channel alert adapters (Email/SMTP, Microsoft Teams, Slack, Webhook).<br>• Prometheus `/metrics` endpoint.<br>• OpenTelemetry distributed tracing & correlation IDs.<br>• Searchable structured log viewer with sensitive data masking. | Medium. Builds upon existing `alert_engine.py` and `metrics.py`; adds notification adapters and Prometheus exporter. |

---

## 3. Detailed Component-by-Component Audit

### 3.1 Backend Architecture
- **Framework:** FastAPI with SQLAlchemy 2.0 ORM and Pydantic v2 schemas.
- **Database:** PostgreSQL 16 (with SQLite support for local dev and testing).
- **Execution Engine:** `PipelineRunner` coordinates execution of activities sequentially or concurrently based on `PipelineDAG`.
- **Connector Framework:** `BaseStorageConnector` and `BaseConnector` provide clean separation for AWS S3, Azure ADLS/Blob, GCP Storage, PostgreSQL, MySQL, SQLite, and Local storage.
- **File Formats:** `FormatRegistry` provides streaming reader/writers for CSV, JSON, JSONL, Parquet, Avro, ORC, Excel, and Text.
- **Security:** Fernet AES-256 encryption (`encrypt_secret`, `decrypt_secret`) and recursive sanitization (`mask_secret_dict`).

### 3.2 Frontend Architecture
- **Framework:** React 18 with TypeScript, Vite 6, Tailwind CSS, and Lucide icons.
- **State Management:** Zustand (`useAppStore.ts`).
- **Graph Visualization:** `@xyflow/react` (React Flow) used in Pipeline Designer and Data Flow Designer.
- **Navigation:** Single-page shell with top `Navbar` and side `Sidebar` switching views via `currentTab`.

---

## 4. Preservation & Backward Compatibility Strategy

1. **Existing Pipelines:** Existing pipeline definitions storing inline connection references will continue to function seamlessly. `CopyDataActivity` will support both `source_dataset_id` (new) and inline `source.connection_id` (existing).
2. **Existing Connections:** Existing connection configurations remain unchanged. Datasets reference existing connection records by ID.
3. **Existing Triggers:** Existing CRON triggers will be migrated transparently with default timezone `UTC`.
4. **Existing Monitoring:** The existing `RunsMonitorPage.tsx` will be extended with tabs/panels rather than replaced.
