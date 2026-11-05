# DataFlow Enterprise — Azure Data Factory (ADF) Parity Matrix

**Document Version:** 1.0.0  
**Last Updated:** 2026-11-05  
**Calculation Methodology:**  
- **Parity Score Formula:**  
  $$\text{Parity \%} = \frac{\sum \text{Status Weight}}{\text{Total Activities} \times 100} \times 100$$
  - *Production Ready:* 100%
  - *Testing Complete:* 90%
  - *Execution Complete:* 75%
  - *Backend Complete:* 60%
  - *Configuration Complete:* 40%
  - *UI Complete:* 25%
  - *In Progress:* 10%
  - *Not Started:* 0%
  - *Provider Required:* Deferred until execution provider plugin is available.

---

## 1. Summary Statistics

- **Total Activities Catalogued:** 48
- **Production Ready / Testing Complete:** 32
- **In Progress:** 0
- **Not Started / Planned:** 16
- **Current Parity Score:** **72.8%**

---

## 2. Activity Parity Catalog

### Category: Move & Transform (Data Movement)

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **Copy Data** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Lookup** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Get Metadata** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Delete Data** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **File Transfer / SFTP** | Not Started | Not Started | Not Started | Not Started | None | SFTP Server | **Not Started** |
| **Data Quality Check** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |

### Category: Control Flow (Orchestration & Branching)

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **If Condition** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Set Variable** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Wait** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Append Variable** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **ForEach** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Switch** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Until** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Filter** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Fail** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Validation** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Execute Pipeline** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |

### Category: Scripting, Compute & External Workloads

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **SQL Script** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Stored Procedure** | Complete | Complete | Complete | Complete | Complete | Relational DB | **Production Ready** |
| **Python Script** | Complete | Complete | Complete | Complete | Complete | Python Worker | **Production Ready** |
| **PySpark Job** | Complete | Complete | Complete | Complete | Complete | Apache Spark | **Production Ready** |
| **Spark Job** | Complete | Complete | Complete | Complete | Complete | Apache Spark | **Production Ready** |
| **Databricks Notebook** | Complete | Complete | Complete | Complete | Complete | Databricks REST | **Production Ready** |
| **Databricks Python** | Not Started | Not Started | Not Started | Not Started | None | Databricks REST | **Provider Required** |
| **Databricks JAR** | Not Started | Not Started | Not Started | Not Started | None | Databricks REST | **Provider Required** |
| **Synapse Notebook** | Not Started | Not Started | Not Started | Not Started | None | Azure Synapse | **Provider Required** |
| **Azure Function** | Not Started | Not Started | Not Started | Not Started | None | Azure Functions | **Provider Required** |
| **Custom Activity** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Hive** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **Pig** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **MapReduce** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **Hadoop Streaming** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |

### Category: File & API Integration

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **REST API Call** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Web Activity** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Webhook** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Read CSV** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Read JSON** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Read Parquet** | Complete | Complete | Complete | Complete | Complete | PyArrow | **Production Ready** |
| **Read Excel** | Complete | Complete | Complete | Complete | Complete | OpenPyXL | **Production Ready** |
| **Write CSV** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Write JSON** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Write Parquet** | Complete | Complete | Complete | Complete | Complete | PyArrow | **Production Ready** |
| **File Exists** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Archive / Zip** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Unzip / Extract** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Compress** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Move / Rename** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |

---

## 3. Visual Data Flow Transformation Operators (Phase 6)

| Transformation | Category | Graph Compiler | Engine | Tests | Status |
|---|---|---|---|---|---|
| **Source** | Input | Planned | Polars/Spark | None | **Not Started** |
| **Sink** | Output | Planned | Polars/Spark | None | **Not Started** |
| **Select** | Schema | Planned | Polars/Spark | None | **Not Started** |
| **Filter** | Row | Planned | Polars/Spark | None | **Not Started** |
| **Derived Column** | Column | Planned | Polars/Spark | None | **Not Started** |
| **Sort** | Row | Planned | Polars/Spark | None | **Not Started** |
| **Join** | Multiple Inputs | Planned | Polars/Spark | None | **Not Started** |
| **Aggregate** | Grouping | Planned | Polars/Spark | None | **Not Started** |
| **Union** | Multiple Inputs | Planned | Polars/Spark | None | **Not Started** |
| **Conditional Split** | Branching | Planned | Polars/Spark | None | **Not Started** |
| **Lookup** | Enrichment | Planned | Polars/Spark | None | **Not Started** |
| **Exists** | Filtering | Planned | Polars/Spark | None | **Not Started** |
| **Pivot / Unpivot** | Reshaping | Planned | Polars/Spark | None | **Not Started** |
| **Window / Rank** | Analytics | Planned | Polars/Spark | None | **Not Started** |
| **Surrogate Key** | Warehouse | Planned | Polars/Spark | None | **Not Started** |
| **Alter Row** | Upsert/Delete | Planned | Polars/Spark | None | **Not Started** |
| **Assert** | Data Quality | Planned | Polars/Spark | None | **Not Started** |
