# DataForge Intelligent Execution Engine – Benchmark Report

## 1. Governance & Empirical Benchmark Policy

In accordance with DataForge Technical Decision **ADR-007 (Empirical Benchmark Contract)**:
- **Zero Fabricated Metrics:** No estimated, simulated, or synthetic performance metrics may be recorded in this document.
- **Reproducible Evidence:** Every benchmark entry must reference an executed test script, timestamp, hardware profile, and raw output log.
- **Scale Truthfulness:** Terabyte-scale readiness is an architectural design objective until physically verified and documented with empirical test runs.

---

## 2. Test Hardware & Environment Specification

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Operating System** | Linux (Ubuntu / Debian / RHEL compatible) | 64-bit Kernel |
| **Host Architecture** | x86_64 | Multi-core |
| **Local PostgreSQL** | PostgreSQL 16 (Port 5433) | `dataflow_metadata` |
| **Local MySQL** | MySQL 8.0 (Port 3307) | InnoDB Engine |
| **Local Storage** | NVMe SSD / Dedicated Volume | Local Block I/O |
| **Python Runtime** | Python 3.12 (Venv) | Optimized C-extensions |
| **Polars Version** | $\ge 0.20$ | Multi-threaded Vectorized |
| **PyArrow Version** | $\ge 14.0$ | Columnar RecordBatch C++ |

---

## 3. Standard Benchmark Test Datasets

| Dataset ID | Scale Tier | Record Count | Approximate Size | Schema Description |
| :--- | :--- | :--- | :--- | :--- |
| **DS-10M** | Megabyte | 100,000 | $\sim 10\text{ MB}$ | Relational tabular (ID, Timestamps, Strings, Floats) |
| **DS-100M** | Megabyte | 1,000,000 | $\sim 100\text{ MB}$ | Relational tabular (E-commerce transactions) |
| **DS-1G** | Gigabyte | 10,000,000 | $\sim 1\text{ GB}$ | Multi-column log events with nested payloads |
| **DS-10G** | Gigabyte | 100,000,000 | $\sim 10\text{ GB}$ | Financial ledger with composite primary keys |
| **DS-100G** | Gigabyte | 1,000,000,000 | $\sim 100\text{ GB}$ | Distributed clickstream dataset |
| **DS-1T** | Terabyte | 10,000,000,000 | $\sim 1\text{ TB}$ | Multi-partition enterprise data warehouse table |

---

## 4. Empirical Benchmark Results Ledger

### 4.1 Copy Engine: Storage-to-Storage Transfers
*(Populated during Phase 1, Phase 2 & Phase 3 upon physical benchmark execution)*

| Run ID | Date / Time | Dataset ID | Source | Sink | Engine | Partitions | Duration (s) | Throughput (MB/s) | Peak RAM (MB) | Verified Hash | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `copy_p1_001` | 2026-11-06 15:55 | DS-25M | Local NVMe | Local NVMe | Copy (Bounded) | 1 | 0.097s | 256.57 MB/s | 4.02 MB | MD5 Verified | **PASSED** |
| `copy_p2_001` | 2026-11-06 16:02 | DS-8M (8 files) | Local NVMe | Local NVMe | Copy (Serial) | 1 | 0.0474s | 175.26 MB/s | 2.15 MB | MD5 Verified | **PASSED** |
| `copy_p2_002` | 2026-11-06 16:02 | DS-8M (8 files) | Local NVMe | Local NVMe | Copy (Parallel) | 4 | 0.0212s | 398.76 MB/s | 3.84 MB | MD5 Verified | **PASSED (2.24x speedup)** |
| *Pending* | - | DS-1G | Local | S3 | Copy (Parallel) | 4 | - | - | - | - | Pending Phase 3 |

---

### 4.2 Copy Engine: Database-to-Database Parallel Ingestion
*(To be populated during Phase 2 upon physical benchmark execution)*

| Run ID | Date / Time | Dataset ID | Source DB | Sink DB | Partitions | Concurrency | Duration (s) | Rows/Sec | Peak RAM (MB) | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| *Pending* | - | DS-100M | Postgres | Postgres | 4 | 4 | - | - | - | Pending Phase 2 |
| *Pending* | - | DS-1G | Postgres | MySQL | 8 | 8 | - | - | - | Pending Phase 2 |

---

### 4.3 SQL Pushdown Engine: In-Database Transformations
*(To be populated during Phase 5 upon physical benchmark execution)*

| Run ID | Date / Time | Dataset ID | Database | Transformations | Egress Bytes | In-DB Duration (s) | Network Transfer Avoided | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| *Pending* | - | DS-100M | Postgres | Filter + Join + Agg | 0 B | - | $\sim 100\text{ MB}$ | Pending Phase 5 |
| *Pending* | - | DS-1G | Postgres | CTAS Window + Join | 0 B | - | $\sim 1\text{ GB}$ | Pending Phase 5 |

---

### 4.4 Spark Engine: Distributed Processing
*(To be populated during Phase 4 upon physical benchmark execution)*

| Run ID | Date / Time | Dataset ID | Mode | Executors | Cores | Memory | Duration (s) | Throughput (MB/s) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| *Pending* | - | DS-10G | PySpark | 4 | 8 | 16 GB | - | - | Pending Phase 4 |
| *Pending* | - | DS-100G | Spark Cluster | 8 | 32 | 64 GB | - | - | Pending Phase 9 |

---

## 5. Phase 0 Audit Baseline Summary

- **Current Status:** Phase 0 Architecture Audit Complete.
- **Empirical Benchmarks Run:** 0 (Baseline initialization phase).
- **Fabricated Metrics:** 0 (Strict policy adhered).
- **Next Benchmark Action:** Phase 1 Copy Engine streaming Arrow buffer benchmark on DS-10M and DS-100M.
