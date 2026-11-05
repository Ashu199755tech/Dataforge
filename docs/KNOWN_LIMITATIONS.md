# DataFlow Enterprise — Known Limitations & Technical Constraints

**Document Version:** 1.9.0  
**Last Updated:** 2026-11-05  

---

## 1. Resolved In Phases 1 Through 9

1. **In-Process Scripting & Process Isolation (Resolved in Phase 4):**
   - Python Script, Custom Activities, and Stored Procedures execute inside isolated sub-processes with real-time stdout streaming, timeout enforcement, and parameter injection.

2. **Distributed Compute Cluster Integration (Resolved in Phase 4):**
   - Clean-room Databricks Jobs REST API 2.1 integration and generic PySpark submission interfaces established.

3. **Hierarchical Control Flow & Sub-DAGs (Resolved in Phase 3):**
   - Hierarchical sub-DAGs, `ForEach` (sequential & parallel worker pools), `ExecutePipeline`, `Switch`, `Filter`, `Fail`, `AppendVariable`, and `Until` fully verified.

4. **Vectorized In-Memory Data Flows (Resolved in Phase 6):**
   - Dedicated visual Data Flow Designer with vectorized Polars multi-node execution graphs and intermediate node caching.

5. **Dynamic Expression Language (Resolved in Phase 7):**
   - Clean-room recursive descent tokenizer and parser supporting 35+ ADF-grade functions, system parameters, and string interpolation.

6. **Enterprise Data Quality & Governance (Resolved in Phase 8):**
   - Vectorized data quality validation (13 rules), PII detection, masking, statistical profiling, and source-to-target reconciliation.

7. **Real-time Observability & Telemetry (Resolved in Phase 9):**
   - Millisecond Gantt waterfall timeline, throughput telemetry (rows/s, MB/s), standard domain error classification, attempt retry histories, downloadable executive reports (JSON, CSV, TXT), and dynamic SLA alert rule evaluation.

---

## 2. Items Slated for Phase 10 (Enterprise Hardening)

1. **Role-Based Access Control (RBAC):**
   - Fine-grained workspace, project, and pipeline permissions (Viewer, Contributor, Operator, Administrator) enforced via declarative policies.

2. **Enterprise Secrets Management:**
   - Migration from local AES-256 Fernet `.env` secrets to pluggable HashiCorp Vault / KMS secret providers with rotation auditing.

3. **Git Integration & Version Control:**
   - Two-way synchronization with Git repositories (GitHub, GitLab, self-hosted Git) with commit-level pipeline definitions and branch switching.

4. **Environment Promotion & CI/CD:**
   - Automated Dev -> Test -> Prod promotion pipelines with parameter overriding and validation gates.

5. **Worker Resiliency & Cluster Auto-Recovery:**
   - Distributed worker heartbeat monitoring, automated dead-worker task recovery, and idempotent retry checkpoints.
