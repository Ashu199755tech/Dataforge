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
| **Source** | Input | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Sink** | Output | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Select** | Schema | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Filter** | Row | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Derived Column** | Column | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Sort** | Row | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Join** | Multiple Inputs | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Aggregate** | Grouping | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Union** | Multiple Inputs | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Conditional Split** | Branching | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Lookup** | Enrichment | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Surrogate Key** | Warehouse | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Window / Rank** | Analytics | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Exists** | Filtering | Complete | Polars Vectorized | Complete | **Production Ready** |
| **Pivot / Unpivot** | Reshaping | Planned | Polars Vectorized | None | **Phase 8 Extension** |
| **Alter Row** | Upsert/Delete | Planned | Polars Vectorized | None | **Phase 8 Extension** |
| **Assert** | Data Quality | Planned | Polars Vectorized | None | **Phase 8 Extension** |

---

## 4. Expression & Parameter Framework (Phase 7)

| Feature / Category | Syntax / Mechanism | Parser & Evaluator | UI Autocomplete | Automated Tests | Parity Status |
|---|---|---|---|---|---|
| **Pipeline Parameters** | `@parameters('name')`, `@pipeline().parameters` | Recursive Descent Parser | Interactive Selector | Verified (10/10) | **Production Ready** |
| **Global Parameters** | `@pipeline().globalParameters.name` | Recursive Descent Parser | Interactive Selector | Verified (10/10) | **Production Ready** |
| **Pipeline Variables** | `@variables('name')` | Recursive Descent Parser | Interactive Selector | Verified (10/10) | **Production Ready** |
| **Activity Output Navigation** | `@activity('name').output.path[0].key` | Recursive Descent Parser | Upstream Node Explorer | Verified (10/10) | **Production Ready** |
| **System Variables** | `@pipeline().RunId, Pipeline, TriggerType` | Recursive Descent Parser | Quick-Insert Palette | Verified (10/10) | **Production Ready** |
| **Loop Item Resolution** | `@item()`, `@item().property` | Recursive Descent Parser | Context Inspector | Verified (10/10) | **Production Ready** |
| **String Functions** | `concat, substring, toUpper, toLower, replace, split, join, guid` | Full Built-in Library | Searchable Catalog | Verified (10/10) | **Production Ready** |
| **Math Functions** | `add, sub, mul, div, mod, min, max, abs, round` | Full Built-in Library | Searchable Catalog | Verified (10/10) | **Production Ready** |
| **Logical & Comparison** | `equals, greater, less, and, or, not, if` | Full Built-in Library | Searchable Catalog | Verified (10/10) | **Production Ready** |
| **Date & Time Functions** | `utcNow, addDays, addHours, formatDateTime, dayOfMonth` | Full Built-in Library | Searchable Catalog | Verified (10/10) | **Production Ready** |
| **Collection & Conversion** | `createArray, first, last, take, skip, empty, coalesce, json` | Full Built-in Library | Searchable Catalog | Verified (10/10) | **Production Ready** |
| **String Interpolation** | `text_@{pipeline().RunId}.csv`, `@@` escaped | Full Regex & AST Sub-eval | Dynamic Content Modal | Verified (10/10) | **Production Ready** |
| **Expression Modal & Preview** | `/api/v1/expressions/validate`, `/evaluate` | REST API Endpoints | Monaco/Textarea Modal | Verified (10/10) | **Production Ready** |

---

## 5. Enterprise Data Quality & Profiling (Phase 8)

| Capability / Rule | Execution Engine | Pipeline Activity | Quarantine Support | Automated Tests | Parity Status |
|---|---|---|---|---|---|
| **Mandatory Field Check** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Non-Blank Check** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Null Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Duplicate Check** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Primary Key Uniqueness** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Referential Integrity** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Range Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Date Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Controlled List Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Schema Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Schema Drift Detection** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Row Count Validation** | Vectorized Polars | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **PII Detection** | Vectorized Polars & Regex | `DataQualityCheck` | Yes | Verified (11/11) | **Production Ready** |
| **Data Masking & Redaction** | Vectorized Polars | `DataMasking` | Destination Output | Verified (11/11) | **Production Ready** |
| **Statistical Data Profiling** | Vectorized Polars | `DataProfiling` | Stored in DB | Verified (11/11) | **Production Ready** |
| **Source-to-Target Reconciliation**| Vectorized Polars | `Reconciliation` | Parity Variance | Verified (11/11) | **Production Ready** |
| **Composite DQ Score Calculation** | Weighted Rule Engine | `DataQualityCheck` | Threshold Failure | Verified (11/11) | **Production Ready** |
