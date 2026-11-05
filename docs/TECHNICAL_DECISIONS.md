# DataFlow Enterprise — Architectural Decision Records (ADR)

**Document Version:** 1.0.0  
**Last Updated:** 2026-11-05  

---

## ADR 001: Independent Clean-Room Implementation
- **Status:** Accepted & Enforced
- **Context:** The product must provide capabilities inspired by Azure Data Factory (ADF) without infringing upon Microsoft's proprietary intellectual property, trade dress, source code, logos, or cloud-specific assets.
- **Decision:** Build 100% vendor-agnostic architecture using standard open protocols (SQLAlchemy, REST, JDBC, PySpark, Polars) with independent UI design, original icons (Lucide), and proprietary metadata model.

---

## ADR 002: Metadata Model & JSON DAG Definition
- **Status:** Accepted
- **Context:** Visual pipeline authoring generates nodes, edges, conditions, parameters, and variable definitions that require persistence and execution.
- **Decision:** Persist pipeline topologies as structured JSON (`definition_json`) inside PostgreSQL. Pipeline state versions are created upon every `Save & Publish` action for immutable auditability and instant rollback.

---

## ADR 003: 4-Outcome Conditional Dependency Architecture
- **Status:** Accepted
- **Context:** Enterprise workflows require conditional branching based on activity outcomes (`On Success`, `On Failure`, `On Completion`, `On Skip`).
- **Decision:** Implement 4 distinct dependency outcome handles on each activity card in React Flow, supported by `PipelineDAG.is_activity_ready()` and `PipelineDAG.is_activity_dead()`. Unhandled failures trigger pipeline failure, while failures caught by downstream `On Failure` paths allow controlled recovery and successful pipeline conclusion.

---

## ADR 004: Decoupled Dynamic Activity Registry
- **Status:** Accepted (Phase 1 Target)
- **Context:** As the platform scales to 40+ activities, a hardcoded switch-statement factory creates high code churn and regression risk.
- **Decision:** Implement a centralized `ActivityRegistry` with dynamic discovery, declarative configuration schemas, metadata introspection, and a REST discovery endpoint (`GET /api/v1/activities`).
