# DataFlow Enterprise — Technical Gap Analysis

**Document Version:** 1.0.0  
**Audit Target:** Current DataFlow Codebase vs. Enterprise ADF Feature Specification

---

## 1. Architectural & Functional Gap Breakdown

| Functional Area | Current Capability | Target ADF-Parity Capability | Gap Severity | Proposed Technical Solution |
|---|---|---|---|---|
| **Activity Registry** | Static `if/elif` in `factory.py` | Extensible plugin registry with metadata discovery & schema validation | **High** | Implement `ActivityRegistry` singleton with `@register_activity`, schema validation & API endpoint |
| **Activity Toolbox** | Hardcoded array in `ActivityToolbox.tsx` | Dynamically populated catalog driven by backend registry API | **Medium** | Load activity catalog from `GET /api/v1/activities` with dynamic fallback |
| **Data Movement** | Full load, chunked stream, upsert, watermark | Bulk load, Get Metadata, Delete Data, SFTP | **Medium** | Implement `GetMetadataActivity`, `DeleteDataActivity`, optimize chunk staging |
| **Control Flow** | IfCondition, SetVariable, Wait | ForEach (seq/par), ExecutePipeline, Switch, Filter, Fail, Until | **High** | Implement hierarchical sub-DAG runners, thread-pool parallelism for ForEach |
| **Scripting / Compute** | In-process SQL script executor | Isolated Python runner, Stored Procedures, PySpark provider | **High** | Subprocess worker with chroot/timeout isolation, PySpark connector |
| **File Formats** | CSV and JSON line streaming | Parquet, Excel, Gzip, Zip Archive, Unzip | **Medium** | Integrate `pyarrow`, `openpyxl`, `zipfile` with chunked buffer streams |
| **Visual Data Flows** | Single pipeline designer canvas | Dedicated Data Flow designer canvas with row/column transformations | **High** | Build dedicated DataFlow canvas using React Flow + Polars/DuckDB execution |
| **Expression Engine** | Basic regex-based token replacer | Complete AST-based expression parser with functions, typing, null-safety | **Medium** | Enhance `ExpressionEvaluator` with tokenized lexer and function registry |
| **Data Quality** | Table-level check activity | Field-level validations, profiling, dead-letter routing, DQ scorecards | **Medium** | Add profiling metrics, quarantined error table insertion |
| **Observability** | REST poll-based execution monitor | Real-time WebSocket streaming, Gantt chart, metrics time-series | **Low** | Mount WebSocket endpoint in `main.py` + Recharts timeline view |
| **Tenancy & Security** | Single workspace, static JWT, Fernet | Multi-tenant RBAC, OIDC/SAML integration, HashiCorp Vault | **Medium** | Keycloak OIDC client, pluggable secrets manager interface |

---

## 2. Identified Refactoring Priorities

1. **Activity Factory Decoupling (Phase 1):** Replace the static `factory.py` dispatch switch with a true pluggable registry pattern that supports versioning, configuration schema extraction, and auto-registration.
2. **Dynamic UI Synchronization (Phase 1):** Ensure the frontend designer (`ActivityToolbox.tsx` and `ActivityConfigDrawer.tsx`) can introspect backend activity metadata so new activities appear instantly without UI code churn.
3. **Control Flow Nested Execution (Phase 3):** Enable `ForEach` and `ExecutePipeline` to spawn nested DAG executions that feed child run metrics and logs into the parent pipeline run ledger.
4. **Data Flow Transformation Engine (Phase 6):** Establish a separate graph abstraction specifically for data transformation streams (sources, projections, joins, aggregations, sinks) independent of the control flow DAG.
