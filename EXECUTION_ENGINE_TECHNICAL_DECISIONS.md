# DataForge Intelligent Execution Engine – Technical Decisions (ADRs)

## Record of Architecture Decisions (ADR)

| ADR # | Title | Status | Date |
| :---: | :--- | :---: | :---: |
| **ADR-001** | Three Independent Engines vs. Monolithic Executor | **ACCEPTED** | 2026-11-06 |
| **ADR-002** | Bounded-Memory Arrow RecordBatches vs. Full-File In-Memory Buffers | **ACCEPTED** | 2026-11-06 |
| **ADR-003** | AST-Based SQL Dialect Translation vs. String Concatenation | **ACCEPTED** | 2026-11-06 |
| **ADR-004** | Decoupled Integration Runtime Dispatch vs. FastAPI Thread Execution | **ACCEPTED** | 2026-11-06 |
| **ADR-005** | Resumable Partition Checkpoints vs. All-or-Nothing Activity Retry | **ACCEPTED** | 2026-11-06 |
| **ADR-006** | Heuristic & Cost-Based Execution Planning with Deterministic Fallback | **ACCEPTED** | 2026-11-06 |
| **ADR-007** | Empirical Benchmark Contract & Prohibition of Fabricated Metrics | **ACCEPTED** | 2026-11-06 |

---

### ADR-001: Three Independent Execution Engines vs. Monolithic Executor

#### Context
DataForge pipelines encounter diverse workloads ranging from a 5 MB CSV ingest between cloud buckets to a 500 GB join across multi-cloud databases to in-database warehouse transformations. Attempting to channel all workloads through a single framework (e.g. forcing everything into Apache Spark or forcing everything into single-threaded Python) introduces major trade-offs:
- Spark adds JVM startup latency, driver coordination overhead, and high cloud compute bills for simple transfers.
- Single-threaded Python lacks distributed clustering for terabyte-scale joins.
- Extracting database data to an external runtime when both source and target are in PostgreSQL wastes network bandwidth and CPU.

#### Decision
Implement three completely decoupled engines:
1. **DataForge Copy Engine:** Multi-threaded parallel streaming for point-to-point data movement without Spark.
2. **DataForge Spark Engine:** Distributed big data compute using PySpark for large-scale joins, aggregations, and windowing.
3. **DataForge SQL Pushdown Engine:** In-database ELT compiler that transforms visual DAGs into native SQL queries.

#### Consequences
- **Positive:** Each engine is optimal for its domain. Developers can choose the engine or let the planner select automatically.
- **Negative:** Requires maintaining three execution paths and ensuring strict output data parity.

---

### ADR-002: Bounded-Memory Arrow RecordBatches vs. Full-File In-Memory Buffers

#### Context
In the existing implementation, `TransferEngine._execute_transcoding_copy()` called `raw_source_stream = io.BytesIO(src_connector.read_file(src_container, src_path))`. For a 50 MB file, this works; for a 50 GB file, reading the entire binary payload into a Python `io.BytesIO` buffer causes an immediate process Out-Of-Memory (OOM) crash.

#### Decision
All data movement across the Copy Engine will use **Bounded-Memory Streaming** with Apache Arrow `RecordBatch` streams and `BoundedTransferBuffer`.
- Memory is capped at a fixed number of buffered chunks (default 4 chunks of 8 MB to 16 MB $\approx 32\text{ MB} - 64\text{ MB}$ total).
- The reader thread blocks if the buffer is full (backpressure).
- Zero-copy conversion is achieved through PyArrow/Polars C-level arrays rather than Python dictionary lists.

#### Consequences
- **Positive:** Memory footprint remains constant ($\le 64\text{ MB}$) regardless of whether the file being processed is 10 MB, 10 GB, or 1 TB.
- **Negative:** Requires strict generator pipelines and asynchronous/threaded buffer management.

---

### ADR-003: AST-Based SQL Dialect Translation vs. String Concatenation

#### Context
Translating visual DataFlow transformation graphs (Filter, Derived Column, Join, Aggregate) into SQL for pushdown execution could be done via raw string concatenation. However, string concatenation is brittle, vulnerable to SQL injection, and impossible to safely optimize or adapt across different database engines (e.g. PostgreSQL vs MySQL vs SQLite vs Snowflake).

#### Decision
Implement an Abstract Syntax Tree (AST) intermediate representation (`PushdownAST`).
- Visual DataFlow nodes compile into typed AST expression trees (`SelectNode`, `FilterNode`, `JoinNode`, `AggregateNode`, `WindowNode`).
- Dialect emitters (`PostgresEmitter`, `MySqlEmitter`, `SqliteEmitter`) traverse the AST and generate valid, sanitized, parameter-bound SQL statements with correct dialect-specific functions (e.g. `DATE_TRUNC` vs `DATE_FORMAT`, `ON CONFLICT` vs `ON DUPLICATE KEY`).

#### Consequences
- **Positive:** Type-safe, secure against injection, allows dialect-specific query optimization (CTE nesting, index hints), and cleanly detects unsupported operations for hybrid fallback.
- **Negative:** Higher initial engineering investment to build the AST compiler.

---

### ADR-004: Decoupled Integration Runtime Dispatch vs. FastAPI Thread Execution

#### Context
If heavy data movement runs inside the main FastAPI worker thread, the web server's event loop will block, leading to high API latency, dropped health checks, and unresponsiveness. Furthermore, enterprise databases often reside inside private corporate networks behind corporate firewalls without public ingress.

#### Decision
- The FastAPI application thread NEVER executes long-running data movement directly.
- Workloads are enqueued to `RuntimeManagerService` task queues.
- Execution occurs in isolated OS background worker threads (for Cloud AutoResolve) or on remote Self-Hosted Integration Runtime (SHIR) agent nodes that poll securely via outbound HTTPS.

#### Consequences
- **Positive:** Web API remains sub-millisecond responsive. On-premise databases are securely accessible through outbound-only polling agents.
- **Negative:** Requires task queue serialization and poll/callback status synchronization.

---

### ADR-005: Resumable Partition Checkpoints vs. All-or-Nothing Activity Retry

#### Context
When moving a 500 million row table partitioned into 20 slices, if partition #18 fails due to a transient network timeout after 45 minutes of processing, restarting the entire activity from scratch wastes 45 minutes of compute, network bandwidth, and cloud egress cost.

#### Decision
Implement fine-grained **Partition Checkpoints**:
- Each completed partition writes a persistent checkpoint record into the activity execution state ledger (`ActivityRun.metrics["partitions"]`).
- When a retry is initiated, the engine inspects the checkpoint ledger, skips partitions already marked `Succeeded`, and resumes only pending or failed slices.
- Final commit occurs only when all partitions succeed.

#### Consequences
- **Positive:** Dramatically reduces mean-time-to-recovery (MTTR) on large-scale datasets.
- **Negative:** Target sinks must support idempotent slice writes (e.g. staging prefixes or upsert keys).

---

### ADR-006: Heuristic & Cost-Based Execution Planning with Deterministic Fallback

#### Context
Automatically choosing between Copy Engine, Spark Engine, and SQL Pushdown requires balancing performance, resource cost, and operational constraints.

#### Decision
The Intelligent Execution Planner uses a 4-tier evaluation pipeline:
1. **User Override:** If user configured `execution_engine` on activity, immediately apply and bypass heuristics.
2. **Affinity & Pushdown Check:** If source and sink are co-located in the same database engine and transformations are 100% pushdown-compatible, choose `SQL_PUSHDOWN` (0 network transfer).
3. **Volume & Complexity Check:** If estimated data volume $> 10\text{ GB}$ or includes distributed joins, check Spark cluster availability:
   - If Spark cluster online $\to$ select `SPARK`.
   - If Spark cluster unavailable $\to$ fall back gracefully to `COPY` with multi-threaded range partitioning.
4. **Default Copy Engine:** For all cross-system transfers, multi-cloud storage movements, and datasets $< 10\text{ GB}$, select `COPY`.

#### Consequences
- **Positive:** Provides optimal engine selection out of the box with zero configuration, while preserving total developer control.
- **Negative:** Requires accurate volume estimation via database statistics or file headers.

---

### ADR-007: Empirical Benchmark Contract & Prohibition of Fabricated Metrics

#### Context
In enterprise data engineering, claiming TB-scale readiness or advertising multi-GB/s throughput without reproducible test evidence destroys credibility and creates production risks.

#### Decision
All performance claims, benchmark reports, and throughput figures in DataForge must adhere to the **Empirical Benchmark Contract**:
- Every number published in `EXECUTION_ENGINE_BENCHMARK_REPORT.md` must be generated by an automated, reproducible benchmark test run on specified hardware.
- Zero mock latency numbers, simulated throughput values, or synthetic benchmarks are allowed.
- Until a physical terabyte test is run and measured on verified hardware, the system is documented as "Architecturally designed for TB scale; empirically verified up to [Measured Scale]".

#### Consequences
- **Positive:** Uncompromising technical integrity and trusted production metrics.
- **Negative:** Requires rigorous test infrastructure and real hardware benchmark execution.
