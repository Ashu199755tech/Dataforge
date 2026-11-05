# DataFlow Enterprise — Known Limitations & Technical Constraints

**Document Version:** 1.0.0  
**Last Updated:** 2026-11-05  

---

## 1. Current Architectural Limitations

1. **In-Process Python Scripting (Targeted for Phase 4):**
   - Current Python execution occurs in the application runtime. Phase 4 will transition to isolated worker subprocesses with strict cgroups/memory limits, timeouts, and sandboxing.

2. **Distributed Compute Cluster Integration (Targeted for Phase 4):**
   - Workloads currently run on local threads. Distributed Spark cluster submission (`spark-submit` / Databricks REST API) is deferred to Phase 4 provider plugins.

3. **In-Memory Transformation Limits (Targeted for Phase 6):**
   - High-throughput transformations must currently use SQL pushdown or chunked generator streaming. Phase 6 will introduce vectorized Polars and PySpark engines for out-of-core streaming data flows.

4. **Hierarchical Sub-DAG Execution (Targeted for Phase 3):**
   - Nested `ForEach` iteration loops and `ExecutePipeline` activities are in progress and scheduled for complete verification in Phase 3.

5. **Secrets Storage:**
   - Secrets are currently encrypted at rest using AES-256 Fernet symmetric keys stored in `.env`. Enterprise HashiCorp Vault integration is scheduled for Phase 10.
