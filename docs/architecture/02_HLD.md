# DataFlow Enterprise — High-Level Design (HLD)

## 1. System Architecture Overview

DataFlow Enterprise is designed with a strict separation between the **Control Plane** and the **Execution Plane**. This ensures that high-throughput data workloads, resource exhaustion, or failure in pipeline code cannot compromise platform availability, metadata integrity, or user interaction.

```
                           +----------------------------------------+
                           |         User Interface (SPA)           |
                           |  React 18 + Vite + Tailwind + Monaco   |
                           |       React Flow Visual Canvas         |
                           +-------------------+--------------------+
                                               |
                                     HTTPS REST / WSS Events
                                               |
                                               v
+-----------------------------------------------------------------------------------------+
|                                    CONTROL PLANE                                        |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                             FastAPI Gateway Layer                                 |  |
|  |   - Authentication & RBAC        - Connection Management & Schema Discovery      |  |
|  |   - Pipeline Graph CRUD & Valid. - Run Dispatcher & WebSocket Broadcaster         |  |
|  |   - Triggers & Scheduling        - Metrics & Audit Logging                        |  |
|  +---------------------------+-----------------------------------+-------------------+  |
|                              |                                   |                      |
|                              v                                   v                      |
|                +---------------------------+       +---------------------------+        |
|                |   Metadata Store (PG)     |       |   State Cache & Broker    |        |
|                |  - Users, Workspaces      |       |  - Redis Event Pub/Sub    |        |
|                |  - Pipeline Definitions   |       |  - Task Execution Queues  |        |
|                |  - Execution Runs & Logs  |       |  - Live Status Heartbeats |        |
|                +---------------------------+       +---------------------------+        |
+------------------------------------------------------------------+----------------------+
                                                                   |
                                                         Dispatched Tasks / IPC
                                                                   |
                                                                   v
+-----------------------------------------------------------------------------------------+
|                                    EXECUTION PLANE                                      |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                        DataFlow Engine Worker Nodes                               |  |
|  |                                                                                   |  |
|  |   +-----------------------+ +-----------------------+ +-----------------------+   |  |
|  |   |    DAG Orchestrator   | |   Connector Engine    | |  Transform & DQ Core  |   |  |
|  |   | - Topological Sort    | | - JDBC / SQLAlchemy   | | - Column Projection   |   |  |
|  |   | - Dependency Matrix   | | - Cloud Storage S3/GCS| | - Watermark Filtering |   |  |
|  |   | - State Checkpointing | | - REST API Connector  | | - Rule Validation     |   |  |
|  |   +-----------------------+ +-----------------------+ +-----------------------+   |  |
|  |                               |                                                   |  |
|  |                               v                                                   |  |
|  |                   Isolated Process / Sandbox                                      |  |
|  |                   (Python Script / PySpark / SQL)                                 |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
                               |                                   |
                               v                                   v
                   +-----------------------+           +-----------------------+
                   |  Source Data Systems  | --------> |  Target Data Systems  |
                   | (MySQL, PG, S3, APIs) |  Stream   | (PostgreSQL, DWH, Datalake)|
                   +-----------------------+           +-----------------------+
```

---

## 2. Component Descriptions

### 2.1 Web Application (Frontend)
- **Visual Pipeline Designer**: Built with React Flow. Node graph representations are strictly typed and serialized into standardized DataFlow JSON graphs.
- **Monaco Editor Integration**: Embedded code editor for SQL and Python scripts with syntax highlighting and parameter auto-complete.
- **Real-Time Run Monitor**: Subscribes to backend WebSocket channels to receive live activity transitions, log streams, and metrics (rows transferred, throughput MB/s).

### 2.2 API Server & Control Plane
- **RESTful Endpoints**: Versioned API (`/api/v1/...`) handling CRUD operations for pipelines, connections, schedules, secrets, and environments.
- **Schema Discovery Engine**: Queries source systems to extract table lists, column definitions, nullability, and primary key constraints without ingesting table data.
- **Security & Cryptography**: Credentials encrypted using AES-256-GCM. Secret keys never leave the backend environment.

### 2.3 Execution Plane & Workers
- **Topological DAG Runner**: Resolves activities into upstream/downstream dependency trees. Activities with met dependencies trigger concurrently up to configurable worker concurrency limits.
- **Streaming Transfer Pipeline**: Copies data in chunked batches (generator-based) from source to destination. Prevents Out-Of-Memory (OOM) errors even on multi-gigabyte datasets.
- **Incremental Engine**: Tracks high-watermark timestamps or sequential IDs per pipeline activity. Supports both Full Overwrite, Append, and Upsert/Merge patterns.

---

## 3. Communication Protocols
- **Client <-> API**: JSON over HTTPS / WSS (WebSockets).
- **Control Plane <-> Worker**: Direct in-process execution queue for local modular monolith; Redis/Celery queue for distributed cluster deployments.
- **Worker <-> Databases**: Native database drivers (psycopg2/3, pymysql/asyncmy, snowflake-connector) with connection pooling.
