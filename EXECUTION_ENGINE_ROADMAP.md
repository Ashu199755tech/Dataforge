# DataForge Intelligent Execution Engine – Master Roadmap

## 1. Roadmap Overview

This roadmap defines the engineering milestones for implementing the DataForge Intelligent Execution Engine.
Development follows a strict phased gate workflow:
- Each phase is divided into independently testable milestones.
- Only one phase is implemented at a time.
- Automated unit, integration, and regression tests run after every milestone.
- Every phase concludes with documentation updates and an explicit user approval gate.
- Zero mock execution metrics or fabricated benchmarks are permitted.

---

## 2. Phased Milestone Breakdown

```
Phase 0: Architecture Audit & Blueprints (Active)
   │
   ▼
Phase 1: Copy Engine Foundation (Streaming Core, Arrow Batches, Zero-Copy Transcoding)
   │
   ▼
Phase 2: Parallel & Partitioned Data Movement (Range & Hash Slicing, Concurrent Workers)
   │
   ▼
Phase 3: Cloud Transfer Optimization (Multi-Part Uploads, Bounded Buffers, S3/Azure/GCS)
   │
   ▼
Phase 4: Spark Engine (PySpark Code Generator, Local & Cluster Dispatch, Catalyst Plans)
   │
   ▼
Phase 5: SQL Pushdown Engine (AST Dialect Translation, In-DB ELT for Postgres/MySQL/SQLite)
   │
   ▼
Phase 6: Intelligent Execution Planner (Volume, Complexity, Affinity & Hardware Cost Model)
   │
   ▼
Phase 7: Pipeline Designer Integration (Engine Selector UI, Planner Overrides, Canvas Hints)
   │
   ▼
Phase 8: Monitoring & Performance Analytics (Live Partition Progress, Metrics, Gantt Timelines)
   │
   ▼
Phase 9: Performance, Reliability & Enterprise Testing (MB-to-TB Benchmarks, Chaos Testing)
```

---

## 3. Detailed Phase Specifications

### Phase 0: Architecture Audit & Blueprint
- **Objective:** Comprehensive audit of existing pipeline engine, connectors, transfer engine, and runtimes; formulate blueprints, gap analysis, and governance documentation.
- **Deliverables:**
  - `EXECUTION_ENGINE_ARCHITECTURE.md`
  - `EXECUTION_ENGINE_ROADMAP.md`
  - `EXECUTION_ENGINE_TRACKER.md`
  - `EXECUTION_ENGINE_TECHNICAL_DECISIONS.md`
  - `EXECUTION_ENGINE_TEST_STRATEGY.md`
  - `EXECUTION_ENGINE_KNOWN_LIMITATIONS.md`
  - `EXECUTION_ENGINE_BENCHMARK_REPORT.md`
- **Verification Criteria:**
  - 100% of existing regression tests pass (288/288).
  - Codebase audit complete with zero application code modifications.
  - User approval gate cleared.

---

### Phase 1: Copy Engine Foundation
- **Objective:** Establish the core streaming foundation of the standalone DataForge Copy Engine with memory bounds and streaming Arrow columnar conversion.
- **Key Deliverables:**
  - `backend/app/engine/copy/` core module.
  - Streaming RecordBatch pipeline using Apache Arrow / Polars memory buffers.
  - Fix streaming memory leaks: replace full-file in-memory buffering (`io.BytesIO(src.read_file())`) with true incremental chunked streaming.
  - Cancellation token integration and MD5/SHA256 streaming verification.
- **Verification Criteria:**
  - Streaming a 500 MB file consumes $< 64\text{ MB}$ of resident worker RAM.
  - Unit tests covering all format transcodings (CSV, Parquet, JSON, Avro, ORC).

---

### Phase 2: Parallel and Partitioned Data Movement
- **Objective:** Enable high-throughput parallel data extraction and ingestion via partitioned slices.
- **Key Deliverables:**
  - Dynamic partition planner for databases: numeric range slicing (`Min`/`Max` boundaries) and date/timestamp slicing.
  - File-set partitioner for multi-file datasets and storage buckets.
  - Worker thread pool coordinator with concurrency limits (`max_parallel_partitions`).
  - Partition checkpoint ledger for resumable transfers upon partial failure.
- **Verification Criteria:**
  - Parallel extraction achieves $> 3\times$ speedup over single-threaded baseline on multi-million row tables.
  - Simulated worker kill mid-transfer resumes only unfinished partitions.

---

### Phase 3: Cloud Transfer Optimization
- **Objective:** Maximize multi-cloud storage transfer speeds with parallel chunk streaming.
- **Key Deliverables:**
  - High-performance multi-part upload coordinators for AWS S3, Azure Blob/ADLS, and Google Cloud Storage.
  - Bounded pre-fetch and write buffers with dynamic chunk sizing (8 MB – 64 MB).
  - Direct cloud-to-cloud cross-provider streaming without intermediate disk writes.
  - Network error backoff and transient failure retry policies.
- **Verification Criteria:**
  - Cross-cloud transfer verified with automated multi-cloud test harness.
  - Checksum validation matches between source and destination.

---

### Phase 4: Spark Engine
- **Objective:** Native distributed Apache Spark and PySpark processing engine for heavy computations and big data.
- **Key Deliverables:**
  - `backend/app/engine/spark/` distributed runner.
  - Automatic compiler translating DataForge DataFlow DAGs into standalone PySpark scripts.
  - Spark cluster dispatch: local mode, remote Standalone, YARN, and Databricks REST API.
  - Distributed partition configuration and Catalyst optimizer hints.
- **Verification Criteria:**
  - Visual DataFlow with 5+ transformation nodes compiles and executes in PySpark.
  - Output dataset matches Polars engine reference output with 100% data parity.

---

### Phase 5: SQL Pushdown Engine
- **Objective:** Zero-network-egress in-database ELT transformation engine.
- **Key Deliverables:**
  - `backend/app/engine/sql_pushdown/` compiler.
  - Abstract Syntax Tree (AST) translator for PostgreSQL, MySQL, and SQLite/DuckDB dialects.
  - Pushdown capability evaluator detecting pushdown-compatible subgraphs.
  - Atomic CTAS (`CREATE TABLE AS SELECT`) and Merge/Upsert statements.
- **Verification Criteria:**
  - Multi-node join and aggregate DataFlow executes in PostgreSQL with 0 bytes network egress.
  - Fallback mechanism correctly handles unsupported operators.

---

### Phase 6: Intelligent Execution Planner
- **Objective:** Cost-based and heuristic engine selector evaluating volume, complexity, connector affinity, and hardware resources.
- **Key Deliverables:**
  - `backend/app/engine/planner/` decision engine.
  - Volume estimator analyzing table metadata, row counts, and file sizes.
  - Complexity analyzer scoring transformation graphs.
  - Affinity matcher checking co-location of source and sink.
  - Policy resolver: `Auto`, `Force Copy`, `Force Spark`, `Force SqlPushdown`.
- **Verification Criteria:**
  - In-DB transformations automatically route to `SQL_PUSHDOWN`.
  - Massive datasets automatically route to `SPARK`.
  - Simple cross-system transfers automatically route to `COPY`.
  - Manual overrides strictly honored.

---

### Phase 7: Pipeline Designer Integration (Completed)
- **Objective:** Expose execution engine controls and hints in the visual frontend canvas.
- **Key Deliverables:**
  - Canvas property drawer: Execution Engine selector dropdown (`Auto (Recommended)`, `Copy Engine`, `Spark Engine`, `SQL Pushdown`).
  - Interactive design-time execution plan evaluator modal and preview card (`/api/v1/pipelines/plan-activity`, `/api/v1/dataflows/{id}/plan`).
  - Visual engine badges on pipeline and dataflow activity nodes.
  - Pushdown capability badge indicating whether DAG qualifies for in-DB execution.
  - Partition configuration UI (partition column, concurrency limit, slicing strategy).
- **Verification Criteria:**
  - Users can configure engine overrides and partition parameters on canvas.
  - Production build clean (`tsc && vite build` 0 errors).
  - Automated integration suite passed (6 new tests, 349 total passed).

---

### Phase 8: Monitoring & Performance Analytics
- **Objective:** Deep operational visibility into engine performance and partition progress.
- **Key Deliverables:**
  - Real-time partition progress tracker (e.g. 8/10 partitions completed, active throughput).
  - SQL pushdown query plan viewer in run diagnostics.
  - Spark application ID and stage progress links in execution logs.
  - Throughput and latency metrics emitted to OpenTelemetry spans.
- **Verification Criteria:**
  - Operators can inspect live partition speeds and generated pushdown SQL in Studio UI.

---

### Phase 9: Performance, Reliability & Enterprise Testing
- **Objective:** Stress testing, failure injection, scale benchmarks, and final documentation.
- **Key Deliverables:**
  - Empirical benchmark suite measuring MB-to-TB data transfers under controlled conditions.
  - Chaos test suite: worker kill, network disconnection, database connection drops.
  - Memory leak verification: continuous 24-hour run with zero RSS memory creep.
  - Final publication of `EXECUTION_ENGINE_BENCHMARK_REPORT.md`.
- **Verification Criteria:**
  - Zero memory leaks over multi-hour runs.
  - All automated benchmarks reproducible and documented with real empirical metrics.
