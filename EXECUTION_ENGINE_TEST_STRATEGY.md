# DataForge Intelligent Execution Engine – Test Strategy

## 1. Testing Philosophy & Verification Principles

The DataForge Intelligent Execution Engine governs mission-critical enterprise data movement and distributed computation. A bug in data movement can cause silent data corruption, duplicate records, or catastrophic data loss.

Our testing strategy enforces five non-negotiable principles:
1. **Automated Verification After Every Milestone:** Tests must be executed and passing before any milestone or phase can be considered complete.
2. **Zero Regression Guarantee:** The existing suite of 288 backend tests and frontend TypeScript builds must remain 100% green at all times.
3. **Data Integrity & Parity Verification:** When transferring or transforming data across engines (Polars vs PySpark vs SQL Pushdown), output datasets must be bit-level or record-level verified against reference results.
4. **Resilience & Chaos Testing:** Transient failures, worker crashes, and network interruptions must be systematically simulated to verify checkpoint resume and transaction rollback.
5. **No Synthetic Benchmarks:** Performance benchmarks must measure real physical wall-clock execution on verified hardware.

---

## 2. Test Pyramid Architecture

```
                       ┌─────────────────────────┐
                       │   Enterprise Benchmarks │
                       │    (MB to TB Scale)     │
                       └────────────┬────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │   Chaos & Resilience    │
                       │ (Worker Kill, Recovery) │
                       └────────────┬────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │   Cross-Engine Parity   │
                       │ (Polars vs Spark vs SQL)│
                       └────────────┬────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │    Integration Tests    │
                       │  (Postgres, S3, Azure)  │
                       └────────────┬────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │       Unit Tests        │
                       │ (AST, Buffer, Planner)  │
                       └─────────────────────────┘
```

---

## 3. Detailed Test Suites

### 3.1 Unit Testing Suite
- **Copy Engine Buffers (`test_copy_engine_buffer.py`):**
  - Verify `BoundedTransferBuffer` blocks on queue capacity (backpressure verification).
  - Verify cooperative `CancellationToken` immediately terminates reader and writer threads.
  - Verify streaming MD5 and SHA-256 calculators against Python `hashlib` reference.
- **Pushdown AST Compiler (`test_sql_pushdown_compiler.py`):**
  - Test translation of DataFlow nodes into ANSI SQL, PostgreSQL, MySQL 8.0, and SQLite.
  - Test complex expressions (Date truncations, string concatenations, surrogate keys, regex matching).
  - Test pushdown capability detection: correctly identifies unsupported operations and flags hybrid fallback.
- **Intelligent Planner (`test_execution_planner.py`):**
  - Test decision matrix: co-located databases $\to$ `SQL_PUSHDOWN`.
  - Test volume thresholds: $> 10\text{ GB}$ $\to$ `SPARK`.
  - Test manual overrides: user preference strictly respected regardless of heuristics.

### 3.2 Integration Testing Suite
- **Database Partition Movement (`test_partitioned_transfers.py`):**
  - Numeric range partitioning on PostgreSQL / MySQL: extracts parallel slices using `WHERE id >= ? AND id < ?`.
  - Date range partitioning: slicing by daily or hourly windows.
  - Record verification: total extracted row count equals exact table row count ($N = \sum \text{slice}_i$).
- **Cloud Storage Multi-Part Transfers (`test_cloud_transfers.py`):**
  - Multi-part chunked upload to AWS S3, Azure Blob, and GCP Storage.
  - Cross-cloud streaming: S3 $\to$ Azure Blob with direct byte-stream piping (zero local disk spillage).
  - End-to-end checksum verification: source hash matches destination hash.
- **SQL Pushdown Execution (`test_sql_pushdown_execution.py`):**
  - Executes real in-database CTAS and Merge operations inside PostgreSQL and MySQL.
  - Verifies zero rows egressed to Python runtime worker.

### 3.3 Cross-Engine Parity Testing (`test_cross_engine_parity.py`)
- Given identical source input data and identical transformation graph:
  1. Execute via Polars in-memory engine.
  2. Execute via DataForge PySpark engine.
  3. Execute via DataForge SQL Pushdown engine.
- Assert that all 3 output datasets contain identical rows, column types, and values.

### 3.4 Chaos & Fault Tolerance Testing (`test_chaos_recovery.py`)
- **Worker Crash Simulation:**
  - Launch 10-partition transfer.
  - Kill worker process after partition #5 completes.
  - Re-run activity: verify partitions 1–5 are skipped, and partitions 6–10 complete successfully.
- **Network Glitch Simulation:**
  - Inject HTTP 503 / socket reset during cloud storage upload.
  - Verify exponential backoff retries chunk and completes successfully.

---

## 4. Test Execution Commands & Automation

```bash
# 1. Run all core unit tests
PYTHONPATH=. venv/bin/pytest backend/tests/test_transfer_engine.py -q

# 2. Run new execution engine test suite
PYTHONPATH=. venv/bin/pytest backend/tests/test_execution_engine_*.py -v

# 3. Full regression test suite (must maintain 288+ passed)
PYTHONPATH=. venv/bin/pytest -q

# 4. Frontend TypeScript build check
cd frontend && npm run build
```
