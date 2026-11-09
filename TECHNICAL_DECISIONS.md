# DataForge – Master Architectural Decision Records (ADR)

**Document Version:** 2.0.0  
**Last Updated:** 2026-11-06  
**Governing Charter:** [GEMINI.md](file:///home/fifity-five/projects/Dataforge/GEMINI.md)

---

## Index of Architectural Decisions

### Section I: Core Platform Architecture (ADR 001 – ADR 014)
*Original platform records maintained in detail in [docs/TECHNICAL_DECISIONS.md](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md)*

1. **[ADR 001: Independent Clean-Room Implementation](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L8)**: 100% vendor-agnostic architecture avoiding proprietary trademarks, trade dress, or proprietary SDKs.
2. **[ADR 002: Metadata Model & JSON DAG Definition](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L15)**: Persist visual pipeline topologies as structured JSON (`definition_json`) with version snapshots.
3. **[ADR 003: 4-Outcome Conditional Dependency Architecture](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L22)**: Granular edge branching (`On Success`, `On Failure`, `On Completion`, `On Skip`).
4. **[ADR 004: Decoupled Dynamic Activity Registry](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L29)**: Declarative activity registration replacing hardcoded factory switch statements.
5. **[ADR 005: Hierarchical Scope & Variable Accumulation Engine](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L36)**: Thread-safe nested control loops (`ForEach`, `Until`, `Switch`, `ExecutePipeline`).
6. **[ADR 006: Sandboxed Subprocess Worker & Compute Abstraction](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L43)**: Isolated script child processes (`IsolatedSubprocessWorker`) with hard timeout guards.
7. **[ADR 007: Asynchronous Webhook & Callback Event Store](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L50)**: Thread-safe asynchronous callback resumption for long-running external tasks.
8. **[ADR 008: Multi-Format Vectorized File Connectors](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L57)**: Vectorized Parquet (`pyarrow`) and Excel (`openpyxl`) ingestion conforming to `BaseConnector`.
9. **[ADR 009: Vectorized In-Memory Transformation Engine](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L64)**: Dual-engine architecture with Polars and Apache Arrow for sub-20ms transformation previews.
10. **[ADR 010: Recursive Descent Expression Engine](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L75)**: Clean-room tokenizer/parser in `expressions.py` supporting 35+ ADF-compatible dynamic functions without `eval()`.
11. **[ADR 011: Vectorized Data Quality, Profiling & Reconciliation](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L86)**: SIMD-vectorized DQ engine with quarantine routing and source-to-target reconciliation.
12. **[ADR 012: Real-time Telemetry, Diagnostics & Alert Engine](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L97)**: Relational run metrics, 5-domain error classifier, Gantt waterfall, and automated alerts.
13. **[ADR 013: Enterprise Hardening, Secrets Vault & RBAC](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L109)**: AES-256 Fernet secret encryption, role hierarchies, environment promotion (Dev $\to$ Test $\to$ Prod), and orphan recovery.
14. **[ADR 014: End-to-End Multi-Engine Validation](file:///home/fifity-five/projects/Dataforge/docs/TECHNICAL_DECISIONS.md#L124)**: Verified 10 live acceptance scenarios across PostgreSQL, MySQL, REST APIs, and filesystem.

---

### Section II: Intelligent Execution Engine (ADR 015 – ADR 023)
*Engine records maintained in detail in [EXECUTION_ENGINE_TECHNICAL_DECISIONS.md](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md)*

15. **[ADR 015: Engine Triad Architecture](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L7)**: Strict decoupling of DataForge Copy Engine, Spark Engine, and SQL Pushdown Engine.
16. **[ADR 016: Bounded-Memory Producer-Consumer Streaming](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L21)**: Thread-safe bounded buffer (`BoundedTransferBuffer`) with hard 64 MB ceiling and backpressure.
17. **[ADR 017: Multi-Strategy Partition Slicing](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L36)**: Dynamic range, datetime, and file partition slicing with concurrent worker thread pools.
18. **[ADR 018: Zero-Copy Cloud-to-Cloud Pipes](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L50)**: Streaming cloud storage transfers with multipart part sizing and in-flight checksum validation.
19. **[ADR 019: Graph-to-PySpark AST Compilation](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L64)**: Automated visual DataFlow translation into distributed PySpark scripts without runtime JVM coupling.
20. **[ADR 020: Multi-CTE Database-Native SQL Pushdown](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L78)**: Dialect-specific CTE compilation for PostgreSQL, MySQL, SQLite, DuckDB, Snowflake with zero network egress.
21. **[ADR 021: Multi-Factor Intelligent Execution Planner](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L92)**: Cost-model optimizer evaluating volume, complexity, affinity, and resources with manual override support.
22. **[ADR 022: Partition-Level Checkpoint Resumption](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L106)**: Resumable execution skipping completed partition slices upon failure recovery.
23. **[ADR 023: OpenTelemetry & Prometheus Semantic Conventions](file:///home/fifity-five/projects/Dataforge/EXECUTION_ENGINE_TECHNICAL_DECISIONS.md#L120)**: Unified observability integrating engine badges, pushdown query viewers, and stage telemetry into UI.

---

### Section III: Modern Data Stack & Ecosystem Expansion (ADR 024 – ADR 025)

24. **ADR 024: SQL-Context Vectorized Data Quality & Declarative Rulebook Evaluation**:
    - **Context:** Enterprise users required evaluating custom multi-column SQL predicates and running declarative YAML/JSON data quality rulebooks against any dataset.
    - **Decision:** Integrated Polars in-memory `SQLContext` with AST mutation sanitization (`DISALLOWED_SQL_REGEX` blocking `DROP`, `DELETE`, `ALTER`, etc.). Added `CustomSqlCheck` supporting both column expressions (`sql_condition`) and full `SELECT` statements (`sql_query`), along with automated YAML/JSON rulebook loading (`evaluate_rulebook`).
25. **ADR 025: Snowflake SQL REST v2 Connector & Enterprise dbt Orchestration**:
    - **Context:** Modern data stack integration necessitated direct Snowflake virtual warehouse connectivity without fragile binary driver compilation, and dual-mode dbt transformation support (dbt Core CLI + dbt Cloud API).
    - **Decision:** Created dedicated `SnowflakeConnector` supporting streaming chunked reads, append/overwrite/merge writes, metadata auto-discovery, and mock verification via official Snowflake SQL REST API v2. Created dedicated `DbtActivity` supporting sandboxed local CLI subprocess execution with regex log telemetry extraction and dbt Cloud REST API v2 triggering and polling.
