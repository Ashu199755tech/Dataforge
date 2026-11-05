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
- **Production Ready / Testing Complete:** 8
- **In Progress:** 2
- **Not Started / Planned:** 38
- **Current Parity Score:** **17.8%**

---

## 2. Activity Parity Catalog

### Category: Move & Transform (Data Movement)

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **Copy Data** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Lookup** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Get Metadata** | In Progress | In Progress | In Progress | In Progress | None | None | **In Progress** |
| **Delete Data** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **File Transfer / SFTP** | Not Started | Not Started | Not Started | Not Started | None | SFTP Server | **Not Started** |
| **Data Quality Check** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |

### Category: Control Flow (Orchestration & Branching)

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **If Condition** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Set Variable** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Wait** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Append Variable** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **ForEach** | In Progress | In Progress | In Progress | In Progress | None | None | **In Progress** |
| **Switch** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Until** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Filter** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Fail** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Validation** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Execute Pipeline** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |

### Category: Scripting, Compute & External Workloads

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **SQL Script** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Stored Procedure** | Not Started | Not Started | Not Started | Not Started | None | Relational DB | **Not Started** |
| **Python Script** | Not Started | Not Started | Not Started | Not Started | None | Python Runner | **Not Started** |
| **PySpark Job** | Not Started | Not Started | Not Started | Not Started | None | Apache Spark | **Provider Required** |
| **Spark Job** | Not Started | Not Started | Not Started | Not Started | None | Apache Spark | **Provider Required** |
| **Databricks Notebook** | Not Started | Not Started | Not Started | Not Started | None | Databricks REST | **Provider Required** |
| **Databricks Python** | Not Started | Not Started | Not Started | Not Started | None | Databricks REST | **Provider Required** |
| **Databricks JAR** | Not Started | Not Started | Not Started | Not Started | None | Databricks REST | **Provider Required** |
| **Synapse Notebook** | Not Started | Not Started | Not Started | Not Started | None | Azure Synapse | **Provider Required** |
| **Azure Function** | Not Started | Not Started | Not Started | Not Started | None | Azure Functions | **Provider Required** |
| **Custom Activity** | Not Started | Not Started | Not Started | Not Started | None | Docker Worker | **Not Started** |
| **Hive** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **Pig** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **MapReduce** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |
| **Hadoop Streaming** | Not Started | Not Started | Not Started | Not Started | None | Hadoop Cluster | **Provider Required** |

### Category: File & API Integration

| Activity Name | UI | Config | Backend | Executor | Tests | Provider Req | Status |
|---|---|---|---|---|---|---|---|
| **REST API Call** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Web Activity** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Webhook** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Read CSV** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Read JSON** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Read Parquet** | Not Started | Not Started | Not Started | Not Started | None | PyArrow | **Not Started** |
| **Read Excel** | Not Started | Not Started | Not Started | Not Started | None | OpenPyXL | **Not Started** |
| **Write CSV** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Write JSON** | Complete | Complete | Complete | Complete | Complete | None | **Production Ready** |
| **Write Parquet** | Not Started | Not Started | Not Started | Not Started | None | PyArrow | **Not Started** |
| **File Exists** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Archive / Zip** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Unzip / Extract** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Compress** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |
| **Move / Rename** | Not Started | Not Started | Not Started | Not Started | None | None | **Not Started** |

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
