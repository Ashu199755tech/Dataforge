# DataFlow Enterprise — Existing Architecture Audit

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-05  
**Platform Status:** Operational (Milestone 1 & 2 Completed)

---

## 1. Executive Summary

DataFlow Enterprise is an independent, vendor-agnostic, enterprise-grade data integration and workflow orchestration platform inspired by modern cloud data factories. The platform is architected with a strict clean-room design, utilizing 100% permissively licensed open-source technologies without any proprietary cloud SDKs, trade dress, or assets.

The platform is organized as a decoupled monorepo comprising:
1. **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, `@xyflow/react` (React Flow), Zustand, and Lucide icons.
2. **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Alembic migrations, and croniter.
3. **Metadata Database:** PostgreSQL 16 (port 5433).
4. **Target / Source Engines:** PostgreSQL 16, MySQL 8.0 (port 3307), SQLite, Local File System.
5. **Execution Abstraction:** Synchronous/thread-pooled DAG orchestration with checkpointing, dynamic expression evaluation, and failure recovery.

---

## 2. Repository Layout & Component Architecture

```
Dataforge/
├── backend/
│   ├── app/
│   │   ├── activities/           # Activity executors
│   │   │   ├── base.py           # BaseActivity, ExecutionContext, ExecutionResult
│   │   │   ├── factory.py        # Activity instantiation factory
│   │   │   ├── copy_data.py      # Chunked streaming, upsert, watermark
│   │   │   ├── sql_script.py     # Database query executor
│   │   │   ├── dq_check.py       # Data quality validation executor
│   │   │   ├── lookup.py         # Single-row / full dataset lookup
│   │   │   ├── set_variable.py   # Variable state assignment
│   │   │   ├── wait.py           # Delay / sleep executor
│   │   │   ├── if_condition.py   # Boolean branching evaluator
│   │   │   └── rest_api.py       # External HTTP/REST request executor
│   │   ├── api/                  # FastAPI REST API endpoints
│   │   │   ├── auth.py           # Token generation, user login
│   │   │   ├── workspaces.py     # Workspaces & Projects CRUD
│   │   │   ├── connections.py    # Connection test, discovery, CRUD
│   │   │   ├── pipelines.py      # Pipeline authoring, validation, run trigger
│   │   │   ├── runs.py           # PipelineRun & ActivityRun logs & metrics
│   │   │   ├── triggers.py       # Trigger schedule management
│   │   │   └── dashboard.py      # Aggregated metric summaries
│   │   ├── connectors/           # Pluggable data connector SDK
│   │   │   ├── base.py           # BaseConnector abstraction
│   │   │   ├── factory.py        # Connector factory
│   │   │   ├── postgres.py       # PostgreSQL connector (psycopg2/SQLAlchemy)
│   │   │   ├── mysql.py          # MySQL connector (pymysql)
│   │   │   ├── sqlite.py         # SQLite connector
│   │   │   └── local_file.py     # CSV and JSON stream connector
│   │   ├── core/                 # Platform configuration & database
│   │   │   ├── config.py         # Settings & environment variables
│   │   │   ├── database.py       # Engine & SessionLocal
│   │   │   └── security.py       # AES-256 Fernet secrets & bcrypt hashing
│   │   ├── execution/            # Core execution engine
│   │   │   ├── dag_engine.py     # PipelineDAG, topological sort, cycle detection
│   │   │   ├── expressions.py    # ExpressionEvaluator (@parameters, @variables)
│   │   │   ├── runner.py         # PipelineRunner, retry policy, checkpoints
│   │   │   └── event_bus.py      # In-memory execution event publisher
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── user.py           # User entity & roles
│   │   │   ├── workspace.py      # Workspace & Project entities
│   │   │   ├── connection.py     # Encrypted Connection entities
│   │   │   ├── pipeline.py       # Pipeline, PipelineVersion, Trigger entities
│   │   │   ├── execution.py      # PipelineRun, ActivityRun, ExecutionLog entities
│   │   │   └── data_quality.py   # DataQualityRule, Result, AuditLog entities
│   │   ├── orchestration/        # Scheduling daemon
│   │   │   └── scheduler.py      # Background cron scheduler
│   │   └── main.py               # FastAPI application entrypoint & static mount
│   ├── tests/                    # Pytest automated test suite (14 test cases)
│   ├── requirements.txt          # Python dependencies
│   └── Dockerfile                # Production container definition
├── frontend/
│   ├── src/
│   │   ├── api/client.ts         # Axios HTTP client with JWT interceptor
│   │   ├── components/layout/    # App shell, Navbar, Sidebar
│   │   ├── features/pipeline-designer/
│   │   │   ├── ActivityNode.tsx  # React Flow custom node with 4 outcome handles & delete buttons
│   │   │   ├── ActivityToolbox.tsx # Categorized draggable activity catalog
│   │   │   ├── ActivityConfigDrawer.tsx # Multi-tab ADF-style configuration inspector
│   │   │   └── PipelineDesignerPage.tsx # Drag-and-drop canvas, validation, publish
│   │   ├── pages/                # Top-level view controllers
│   │   │   ├── DashboardPage.tsx # Enterprise metrics & activity stream
│   │   │   ├── PipelinesListPage.tsx # Pipeline repository view
│   │   │   ├── ConnectionsPage.tsx # Connection manager & test ping
│   │   │   ├── TriggersPage.tsx  # Trigger scheduler management
│   │   │   ├── RunsMonitorPage.tsx # Real-time execution monitor & logs
│   │   │   └── DataQualityPage.tsx # Data quality rules & scorecard
│   │   ├── store/useAppStore.ts  # Zustand central state management
│   │   ├── types/index.ts        # TypeScript domain contracts
│   │   └── App.tsx               # Root view router
│   ├── package.json              # Frontend npm dependencies
│   └── vite.config.ts            # Vite bundler configuration
└── scripts/
    ├── start_platform.sh         # Unified daemon startup script
    ├── stop_platform.sh          # Daemon termination script
    ├── run_mvp_verification.py   # Milestone 1 verification script
    └── run_milestone2_verification.py # Milestone 2 verification script
```

---

## 3. Database Schema & Persistence Layer

The database schema is managed via PostgreSQL 16 on port 5433 with the following primary entities:

1. **`users`**: User identity, hashed passwords, roles (`Admin`, `DataEngineer`, `Viewer`), active flags.
2. **`workspaces`**: Logical tenancy boundary.
3. **`projects`**: Sub-boundary within workspaces for grouping pipelines.
4. **`connections`**: External system definitions with encrypted connection strings and secrets (`encrypted_secrets` using AES-256 Fernet).
5. **`pipelines`**: Pipeline definitions, metadata, parameters, variables, and full graph topology stored as structured JSON (`definition_json`).
6. **`pipeline_versions`**: Immutable version history snapshots created on every publish operation.
7. **`triggers`**: Automated schedule definitions supporting standard 5-part cron expressions, status, and target pipeline parameters.
8. **`pipeline_runs`**: Execution ledger tracking status (`Pending`, `Running`, `Succeeded`, `Failed`, `Cancelled`), start/end times, durations, rows read/written, and error summaries.
9. **`activity_runs`**: Granular node execution tracking with status, retry counts, execution duration, metrics, and output variables.
10. **`execution_logs`**: Streaming log storage linked to activity runs with log levels (`INFO`, `WARN`, `ERROR`).
11. **`data_quality_rules`** & **`data_quality_results`**: Declarative verification rules and rule execution audit results.

---

## 4. Execution Engine Architecture

### 4.1 DAG Engine (`backend/app/execution/dag_engine.py`)
- Directed Acyclic Graph validation with cycle detection via Tarjan's / Kahn's algorithms.
- Supports ADF-style 4-outcome dependency evaluation:
  - `Succeeded` (Green handle): Proceeds if parent activity completes with status `Succeeded`.
  - `Failed` (Red handle): Proceeds if parent activity fails (`Failed`), allowing error-handling branches.
  - `Completed` (Blue handle): Proceeds regardless of whether parent activity succeeded or failed.
  - `Skipped` (Gray handle): Proceeds if parent activity was skipped due to an upstream dead branch.
- Automatic dead branch detection (`is_activity_dead`): Cascade-marks unreachable downstream activities as `Skipped`.

### 4.2 Dynamic Expression Evaluator (`backend/app/execution/expressions.py`)
- Evaluates dynamic expressions inside activity configuration strings:
  - `@parameters('param_name')`
  - `@variables('var_name')`
  - `@activity('activity_name').output.field.nested`
  - Functions: `@equals()`, `@greater()`, `@less()`, `@not()`, `@concat()`, `@coalesce()`.

### 4.3 Pipeline Runner (`backend/app/execution/runner.py`)
- Thread-safe orchestrator managing topological execution.
- Handles configurable retry policies (`max_retries`, `retry_interval_seconds`).
- Checkpoints state into PostgreSQL at each activity transition.
- Catchment of handled errors: If an activity fails but its downstream `On Failure` branch completes successfully, the pipeline run is marked as `Succeeded` with error summary noting the handled failure.

---

## 5. Existing Connector Implementations

1. **`PostgresConnector`**: Direct SQLAlchemy/psycopg2 integration. Supports test connection, table discovery, column metadata discovery, data preview, chunked streaming ingestion, and upsert/merge logic.
2. **`MySQLConnector`**: Direct PyMySQL integration. Supports secure connection, schema discovery, table streaming, and watermark queries.
3. **`SQLiteConnector`**: Local SQLite connectivity for fast testing and lightweight environments.
4. **`LocalFileConnector`**: CSV and JSON line-by-line chunked streaming reader.

---

## 6. Existing Activity Implementations

| Activity Type | Description | Execution Status | Config UI |
|---|---|---|---|
| `CopyData` | Chunked extraction, column mapping, upsert, watermark | Functional & Verified | Full |
| `SqlScript` | Arbitrary SQL execution on relational connections | Functional & Verified | Full |
| `DataQualityCheck` | Enforces row counts, nulls, and SLA thresholds | Functional & Verified | Full |
| `Lookup` | Reads first row or full dataset into variable context | Functional & Verified | Full |
| `SetVariable` | Assigns scalar or object values to pipeline variables | Functional & Verified | Full |
| `Wait` | Delays execution for N seconds | Functional & Verified | Full |
| `IfCondition` | Evaluates boolean expression and branches | Functional & Verified | Full |
| `RestApi` | Issues HTTP GET/POST/PUT requests with payload & headers | Functional & Verified | Full |

---

## 7. Current Test Coverage & Verification Status

14 automated tests pass with 100% success rate:
- `backend/tests/test_auth.py` (3 tests)
- `backend/tests/test_dag_engine.py` (3 tests)
- `backend/tests/test_adf_dependency_conditions.py` (1 test)
- `backend/tests/test_copy_data.py` (1 test)
- `backend/tests/test_control_flow.py` (4 tests)
- `backend/tests/test_expressions.py` (1 test)
- `backend/tests/test_scheduler.py` (1 test)

E2E live verification scripts:
- `scripts/run_mvp_verification.py`: Verifies MySQL -> CopyData -> PostgreSQL full and incremental watermark loads.
- `scripts/run_milestone2_verification.py`: Verifies Lookup -> SetVariable -> IfCondition -> Wait pipeline flow and scheduled trigger dispatch.
