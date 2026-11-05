# DataFlow Enterprise — Low-Level Design (LLD)

## 1. Pipeline Definition Model (JSON Specification)

A pipeline in DataFlow Enterprise is modeled as an executable declarative graph. The JSON format is strictly validated via Pydantic on the backend and TypeScript interfaces on the frontend.

```json
{
  "id": "pipe_01j7q9k2x",
  "name": "mysql_to_postgres_orders_etl",
  "description": "Daily incremental ingestion of orders with validation",
  "parameters": {
    "batch_size": { "type": "int", "default": 5000 },
    "env": { "type": "string", "default": "dev" }
  },
  "variables": {
    "last_watermark": { "type": "string", "default": "1970-01-01 00:00:00" }
  },
  "activities": [
    {
      "id": "act_extract_copy",
      "name": "Copy Orders Data",
      "type": "CopyData",
      "depends_on": [],
      "retry_policy": {
        "max_retries": 3,
        "retry_interval_seconds": 10
      },
      "timeout_seconds": 3600,
      "config": {
        "source": {
          "connection_id": "conn_mysql_prod",
          "query_mode": "table",
          "table_name": "source_orders",
          "incremental": {
            "mode": "watermark",
            "column": "updated_at",
            "watermark_value": "@variables('last_watermark')"
          }
        },
        "destination": {
          "connection_id": "conn_pg_warehouse",
          "table_name": "target_orders",
          "write_mode": "upsert",
          "key_columns": ["order_id"],
          "auto_create_table": true
        },
        "column_mappings": [
          { "source_column": "order_id", "target_column": "order_id", "target_type": "BIGINT" },
          { "source_column": "customer_id", "target_column": "customer_id", "target_type": "INTEGER" },
          { "source_column": "total_amount", "target_column": "total_amount", "target_type": "NUMERIC(12,2)" },
          { "source_column": "status", "target_column": "status", "target_type": "VARCHAR(50)" },
          { "source_column": "updated_at", "target_column": "updated_at", "target_type": "TIMESTAMP" }
        ]
      }
    },
    {
      "id": "act_dq_check",
      "name": "Validate Orders Data",
      "type": "DataQualityCheck",
      "depends_on": [
        { "activity_id": "act_extract_copy", "condition": "Succeeded" }
      ],
      "config": {
        "connection_id": "conn_pg_warehouse",
        "table_name": "target_orders",
        "rules": [
          { "rule_type": "NotNull", "column": "order_id", "threshold_percent": 100 },
          { "rule_type": "PositiveNumeric", "column": "total_amount", "threshold_percent": 99.9 },
          { "rule_type": "ControlledList", "column": "status", "allowed_values": ["PENDING", "COMPLETED", "CANCELLED"] }
        ],
        "fail_pipeline_on_error": true
      }
    }
  ]
}
```

---

## 2. Execution State Machine & DAG Engine

### 2.1 State Life-Cycle
```
[PENDING] ---> [QUEUED] ---> [RUNNING] ---> [SUCCEEDED]
                                |
                                +---> [FAILED] ---> [RETRYING] (if retries left)
                                |
                                +---> [CANCELLED]
```

### 2.2 DAG Resolution Algorithm
1. Construct in-degree adjacency list from `pipeline.activities[].depends_on`.
2. Check for cycles using Kahn's algorithm or Tarjan's strongly connected components. If cycles exist, reject validation.
3. Identify all root activities (in-degree == 0).
4. Dispatch runnable activities to execution thread/task pool.
5. On completion of an activity:
   - Record run status, start/end timestamps, metrics (rows read, rows written, bytes, error trace).
   - Evaluate conditions for downstream nodes (`Succeeded`, `Failed`, `Completed`).
   - Decrement in-degree for downstream nodes whose conditions are satisfied.
   - If downstream in-degree reaches 0, schedule downstream activity.
6. The pipeline completes when all reachable nodes are terminated. If any mandatory path fails and is unhandled, mark pipeline run as `FAILED`.

---

## 3. Connector Abstraction Interface

Every data connector implements the base class:

```python
class BaseConnector(ABC):
    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Verifies network reachability and authentication."""
        pass

    @abstractmethod
    def discover_schemas(self) -> List[str]:
        """Lists available databases/schemas."""
        pass

    @abstractmethod
    def discover_tables(self, schema: str | None = None) -> List[TableMetadata]:
        """Lists tables, views, and row count estimates."""
        pass

    @abstractmethod
    def discover_columns(self, table_name: str, schema: str | None = None) -> List[ColumnMetadata]:
        """Lists column names, physical types, logical types, nullability, primary keys."""
        pass

    @abstractmethod
    def read_data_stream(
        self,
        table_name: str,
        columns: List[str] | None = None,
        filter_expr: str | None = None,
        watermark_col: str | None = None,
        watermark_val: Any | None = None,
        batch_size: int = 5000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Yields chunks of records as dictionaries."""
        pass

    @abstractmethod
    def write_data_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        write_mode: str = "append", # append, overwrite, upsert
        key_columns: List[str] | None = None,
        column_mappings: List[Dict[str, str]] | None = None
    ) -> int:
        """Writes a batch of records, returning the number of rows written."""
        pass
```

---

## 4. Copy Data Streaming Pipeline
To prevent memory exhaustion when transferring millions of rows:
1. Source connector yields generator batches (`yield list[dict]`, chunk size 5,000–10,000).
2. DataFlow Transformer applies column mappings, type casts, and default values per row without storing the full dataset in memory.
3. Destination connector executes bulk multi-row insert or staging upsert within a transaction:
   - For PostgreSQL: `execute_batch` or `copy_expert` with temporary staging table for upsert.
   - For MySQL: `INSERT INTO ... ON DUPLICATE KEY UPDATE` or batch parameter sets.
4. Watermark updates are written to the pipeline state checkpoint upon transaction commit.
