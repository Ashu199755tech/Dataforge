# DataFlow Enterprise — Development Roadmap

## Phase 1: Foundation & MVP (Milestone 1 — Current Focus)
- [x] Complete Architectural Blueprint (PRD, HLD, LLD, ERD, Threat Model, Licensing).
- [ ] Initialize Repository Monorepo (Backend FastAPI + Frontend React/Vite/Tailwind).
- [ ] Database Schema Definition & Migrations (PostgreSQL metadata persistence).
- [ ] Pluggable Connector SDK (PostgreSQL, MySQL, SQLite with live testing & schema discovery).
- [ ] Pluggable Activity Framework (Copy Data with full & watermark incremental loading).
- [ ] Core DAG Execution Engine (Topological sort, activity runner, event bus).
- [ ] REST API Endpoints (Auth, Workspaces, Projects, Connections, Pipelines, Runs, Dashboard).
- [ ] Visual Pipeline Designer Frontend (React Flow, Activity Toolbox, Configuration Drawer).
- [ ] End-to-End Verification: MySQL Source -> Copy Data Activity -> PostgreSQL Destination.

---

## Phase 2: Advanced Orchestration & Control Flow
- Control Flow Activities: ForEach, If-Condition, Switch, Wait, Set Variable, Sub-Pipeline.
- Dynamic Expression Language (evaluation of pipeline parameters, system variables, runtime triggers).
- Scheduled Triggers (Cron scheduler engine, time-zone awareness, parameter binding).
- Webhook & Storage Event Triggers (S3 / Blob creation listener).

---

## Phase 3: Distributed Execution & Compute Scalability
- Decoupled Celery / Redis task queue for distributed worker scale-out.
- PySpark & Spark-Submit Connector for multi-terabyte distributed transformations.
- Stored Procedure & Notebook Execution Activities (Databricks, Jupyter).
- Distributed Tracing with OpenTelemetry and Prometheus metric exports.

---

## Phase 4: Enterprise Governance & Data Quality
- Advanced Data Quality Engine: Completeness, Uniqueness, Referential Integrity, Volume Anomaly.
- Quarantined record routing (failed rows diverted to dead-letter storage).
- Multi-tenancy with RBAC, Keycloak OIDC/SAML SSO, and HashiCorp Vault secrets integration.
- Git-based pipeline version control (Git commit, pull request, branch promotion).
