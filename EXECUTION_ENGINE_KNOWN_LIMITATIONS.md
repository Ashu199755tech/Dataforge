# DataForge Intelligent Execution Engine – Known Limitations

## 1. Scope & Purpose

This document provides transparent, production-grade documentation of current technical boundaries, physical limits, unsupported operations, and operational prerequisites across the DataForge Intelligent Execution Engine.

---

## 2. Engine-Specific Limitations

### 2.1 DataForge Copy Engine
1. **Unindexed Database Tables:**
   - Slicing by numeric or date range requires an indexed column (Primary Key or B-tree index).
   - If a table lacks an index on the partition column, parallel range queries will trigger full table scans per worker thread, which can degrade database I/O performance rather than accelerating it.
   - *Mitigation:* The partition planner verifies column index existence before selecting range partitioning. If unindexed, it defaults to single-stream cursor ingestion.
2. **Unstructured File Slicing:**
   - Multi-part byte-range splitting is supported for binary and Parquet files (via row-group boundaries).
   - For unstructured or variable-length text/CSV files, byte-range splitting can divide records across chunk boundaries unless chunk-boundary scanning is active.
   - *Mitigation:* Non-splittable CSV/JSON files are transferred via streaming line readers or multi-file set partitioning.
3. **Database Concurrency Limits:**
   - Spawning 32 parallel partition workers against a small database instance can exhaust database connection pools (`max_connections`).
   - *Mitigation:* The Copy Engine strictly respects `max_parallel_partitions` (default $\le 4$ for cloud DBs, $\le 8$ for on-premise warehouses).

---

### 2.2 DataForge Spark Engine
1. **Cluster Dependency & Environment Prerequisites:**
   - Distributed Spark execution requires an accessible Apache Spark cluster (Standalone, YARN, Kubernetes) or Databricks workspace.
   - In environments where Spark binaries or PySpark are not installed locally, local Spark jobs cannot execute.
   - *Mitigation:* The Intelligent Execution Planner verifies Spark cluster heartbeat and environment availability before scheduling. If unreachable, it automatically falls back to the Copy Engine.
2. **Cold Start Latency:**
   - Initializing a new Spark session or spinning up an ephemeral cluster adds 15 to 90 seconds of startup latency.
   - *Mitigation:* Spark is never selected for workloads $< 10\text{ GB}$ unless explicitly forced by user override.

---

### 2.3 DataForge SQL Pushdown Engine
1. **Dialect Heterogeneity:**
   - Source and target must be within the same database engine (or supported federated foreign data wrapper / linked server) to execute 100% in-database ELT.
   - Cross-database pushdown (e.g. from PostgreSQL to Snowflake) requires a staging transfer step.
2. **Unsupported In-DB Pushdown Operators:**
   - Custom Python UDFs cannot be pushed into standard PostgreSQL/MySQL engines without dedicated language extensions (`plpython3u`).
   - Complex nested JSON schema reshaping where target databases lack native JSONPath functions.
   - *Mitigation:* The pushdown compiler inspects every node in the transformation DAG. If any node is unsupported, it flags the graph as non-pushdown and routes execution to the Copy or Spark Engine.
3. **SQLite Specific Limitations:**
   - SQLite does not support `FULL OUTER JOIN`, `RIGHT JOIN`, or native regular expressions without C extensions.

---

## 3. Cloud Provider Throughput & Rate Limits

When executing multi-cloud high-throughput transfers, cloud provider APIs impose strict rate limits that cannot be bypassed:

| Cloud Provider | Storage Service | Documented Rate Limits | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Amazon Web Services** | AWS S3 | 3,500 PUT/POST/DELETE per sec per prefix<br>5,500 GET/HEAD per sec per prefix | Prefix partitioning (hash prefixes) for massive parallel writes |
| **Microsoft Azure** | Azure Blob / ADLS Gen2 | 20,000 requests per second per storage account<br>Max 60 MB/s per single blob block | Multi-part block upload with concurrent worker threads |
| **Google Cloud** | Cloud Storage (GCS) | 1,000 write requests per second per bucket | Exponential backoff retry on HTTP 429 / 503 |

---

## 4. Hardware & Memory Ceilings

1. **Local Worker Memory Ceiling:**
   - Default memory ceiling for single Integration Runtime workers is 4 GB RSS RAM.
   - The Copy Engine streaming buffer is capped at 64 MB per partition. Concurrency is bounded to $\text{Workers} \times 64\text{ MB} \ll 4\text{ GB}$.
2. **Terabyte-Scale Operational Requirements:**
   - Processing $> 1\text{ TB}$ of data through the Copy Engine requires sufficient target disk IOPS ($> 500\text{ MB/s}$ NVMe or 10 Gbps network interface).
   - High-throughput parallel transfers are network-bound. A 1 Gbps NIC provides a theoretical maximum of $\sim 125\text{ MB/s}$ throughput regardless of engine optimization.
