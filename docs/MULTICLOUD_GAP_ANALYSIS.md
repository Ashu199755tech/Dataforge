# DataForge Multi-Cloud Copy Data Engine — Gap Analysis

## 1. Executive Summary

DataForge Enterprise currently provides robust pipeline orchestration, DAG dependency resolution, parameter/expression evaluation, monitoring, and database-to-database data movement. However, its data movement engine (`CopyDataActivity`) and connector architecture were primarily engineered for relational tabular systems (PostgreSQL, MySQL, SQLite) and a basic local filesystem connector.

To evolve DataForge into an enterprise-grade multi-cloud data movement engine, the platform must support first-class object storage services across the three major hyperscalers:
1. **Microsoft Azure:** Azure Data Lake Storage Gen2 (ADLS Gen2) and Azure Blob Storage.
2. **Amazon Web Services (AWS):** Amazon S3.
3. **Google Cloud Platform (GCP):** Google Cloud Storage (GCS).

In addition, it must deliver robust **cross-cloud transfers** (e.g., S3 to ADLS, GCS to S3), **database-to-cloud ingestion** (e.g., PostgreSQL/MySQL to Parquet in S3), and **cloud-to-database reverse ETL** (e.g., CSV/JSON in ADLS to PostgreSQL).

This gap analysis document audits the existing codebase, details missing capabilities, and establishes the blueprint for the phased implementation.

---

## 2. Current Codebase Audit

### 2.1 Connector Framework (`backend/app/connectors/`)

| File / Component | Current Implementation | Multi-Cloud Gap / Limitation |
| :--- | :--- | :--- |
| `base.py` (`BaseConnector`) | Standard interface defining: `test_connection()`, `discover_schemas()`, `discover_tables()`, `discover_columns()`, `read_data_stream()`, `write_data_batch()`, `execute_query()`, `get_metadata()`, `delete_data()`. | Strictly relational/table-oriented. Assumes data resides in tabular tables with columns and SQL queries. Lacks hierarchical object storage primitives (buckets, containers, prefixes, directories, object keys, blob metadata, streaming byte chunks, upload/download parts). |
| `factory.py` (`get_connector`) | Factory routing `postgres`, `mysql`, `sqlite`, and `local_file`. | Does not support cloud storage providers (`azure_blob`, `azure_adls`, `aws_s3`, `gcp_storage`). Lacks capability-based discovery and dynamic lazy-loading of provider SDKs. |
| `local_file.py` (`LocalFileConnector`) | Operates on a local directory path (`base_path`). Discovers files matching `.csv`, `.json`, `.parquet`, `.xlsx`. Reads and writes whole records or chunks using PyArrow/csv/openpyxl. | Implements table paradigms over files. Does not model containers/buckets, prefix browsing, recursive folder traversal, multipart uploads, resumable uploads, or cloud metadata. |
| Cloud SDKs | Not installed in `venv` (`azure-storage-blob`, `azure-storage-file-datalake`, `azure-identity`, `boto3`, `google-cloud-storage`, `google-auth`). | Provider SDKs must be isolated and loaded dynamically so the core DataForge platform operates without mandatory cloud dependencies. |

### 2.2 Copy Data Activity (`backend/app/activities/copy_data.py`)

| Feature | Current Implementation | Multi-Cloud Gap / Limitation |
| :--- | :--- | :--- |
| Extraction Pipeline | Calls `src_connector.read_data_stream(table_name=...)` which yields Python dictionaries (`List[Dict[str, Any]]`). | High memory overhead for large file transfers. Cannot perform zero-overhead binary byte-streaming when file format conversion is not required. |
| Ingestion Pipeline | Calls `dst_connector.write_data_batch(table_name=...)`. | Does not support streaming direct to cloud object storage with multipart/resumable chunk writers, partitioning, or compression. |
| Watermark / Incremental | Supports single-column scalar watermark comparison (e.g., `updated_at > last_watermark`). | No file-based incremental ingestion (e.g., file modification timestamp, directory change tracking, partition scanning). |
| Pre/Post Scripts | Executes SQL queries via `execute_query()`. | Object storage cannot execute SQL directly; pre/post operations in cloud storage require blob existence checks, staging folder cleanup, or object renaming. |
| Column Mapping & Types | Dictionary-based column renaming in batch writes. | Lacks format-level projection, explicit data type coercion, nested JSON flattening, and PyArrow schema enforcement. |

### 2.3 Connection & Credential Management (`backend/app/models/connection.py`, `backend/app/core/security.py`)

| Feature | Current Implementation | Multi-Cloud Gap / Limitation |
| :--- | :--- | :--- |
| Encryption | AES-256 Fernet symmetric encryption of connection configs (`config_encrypted`). | Working effectively. However, cloud connections require structured validation for diverse authentication modes (Service Principals, SAS tokens, Account Keys, IAM Roles, STS AssumeRole, Service Account JSONs, ADC). |
| Secret Sanitization | Credentials decrypted only at execution time in memory. | Need strict auditing to ensure cloud secrets, temporary STS tokens, and private keys never leak into execution logs, activity run payloads, or frontend API responses. |
| Connection Test API | `POST /api/connections/test` and `POST /api/connections` tests connection. | Current tests assume relational ping or directory access. Cloud testing must verify bucket listing, read permissions, and write permissions using capability checks. |

### 2.4 Frontend Architecture (`frontend/src/`)

| UI Area | Current State | Multi-Cloud Gap / Limitation |
| :--- | :--- | :--- |
| Connections Page (`ConnectionsPage.tsx`) | Modal contains inputs for: Host, Port, Username, Password, Database Name. | No provider selection for Azure Blob, ADLS Gen2, AWS S3, or GCS. No forms for cloud-specific authentication (Account Key, SAS, IAM Role, STS AssumeRole, Service Account JSON). |
| Copy Data Drawer (`ActivityConfigDrawer.tsx`) | Single configuration section with source connection, destination connection, table names, and batch size. | Missing the 7 mandatory enterprise tabs: **General**, **Source**, **Source Settings**, **Destination**, **Mapping**, **Performance**, **Advanced**. Lacks interactive storage browser (bucket/container, directory, file picker). |

---

## 3. Detailed Feature-by-Feature Gap Matrix

| Domain | Feature Requirement | Current Status | Target Implementation Phase |
| :--- | :--- | :--- | :--- |
| **Framework** | Common Base Storage Connector (`BaseStorageConnector`) | Missing | Phase 1 |
| **Framework** | Capability Discovery (`SupportsMultipart`, `SupportsBrowsing`, etc.) | Missing | Phase 1 |
| **Framework** | Dynamic / Optional SDK Provider Registration | Missing | Phase 1 |
| **Framework** | Standardized Storage Metadata Model (`StorageItem`, `StorageMetadata`) | Missing | Phase 1 |
| **Azure** | ADLS Gen2: Filesystem & Directory Browsing, POSIX hierarchy | Missing | Phase 2 |
| **Azure** | Azure Blob: Container & Prefix-based blob browsing | Missing | Phase 2 |
| **Azure** | Azure Auth: Service Principal, Managed Identity, Account Key, SAS | Missing | Phase 2 |
| **Azure** | Azure Operations: Read, Write, Upload, Download, List, Delete, Rename | Missing | Phase 2 |
| **AWS** | AWS S3: Bucket Discovery, Prefix Browsing, Object Listing | Missing | Phase 3 |
| **AWS** | AWS S3 Auth: IAM Role, Access/Secret Key, STS AssumeRole, Session Token | Missing | Phase 3 |
| **AWS** | AWS S3 Operations: Read, Write, Multipart Upload, Download, Delete | Missing | Phase 3 |
| **AWS** | AWS S3 Security: Server-side encryption (SSE-S3, SSE-KMS, SSE-C) | Missing | Phase 3 |
| **GCP** | GCS: Project selection, Bucket Discovery, Object Browsing | Missing | Phase 4 |
| **GCP** | GCS Auth: Service Account JSON, ADC, Workload Identity Federation | Missing | Phase 4 |
| **GCP** | GCS Operations: Read, Write, Resumable Upload, Download, Delete | Missing | Phase 4 |
| **UI** | 7-Tab Enterprise Copy Data Configuration Drawer | Missing | Phase 5 |
| **UI** | Cloud Storage Hierarchy Browser (Bucket -> Prefix -> Object) | Missing | Phase 5 |
| **UI** | Dynamic Column Mapping & Type Conversion Designer | Missing | Phase 5 |
| **Formats** | PyArrow-backed CSV, JSON, JSONL, Parquet, Avro, ORC, Excel, Text | Partial (CSV/JSON/Parquet/Excel in local_file only) | Phase 6 |
| **Formats** | Schema Discovery, Inference, and Explicit Schema Definition | Missing | Phase 6 |
| **Formats** | Streamed Low-Memory File Preview (Head N rows) | Missing | Phase 6 |
| **Engine** | Provider-Independent Memory-Bounded Transfer Engine | Missing | Phase 7 |
| **Engine** | Zero-Disk Streaming & Chunk Staging Fallbacks | Missing | Phase 7 |
| **Engine** | Transfer Integrity Checksum Validation (MD5, SHA-256, CRC32C) | Missing | Phase 7 |
| **Hybrid** | Cross-Cloud Movement (S3 <-> GCS <-> ADLS / Blob) | Missing | Phase 8 |
| **Hybrid** | Database-to-Cloud Movement (Postgres/MySQL -> S3/GCS/ADLS) | Missing | Phase 8 |
| **Hybrid** | Cloud-to-Database Movement (S3/GCS/ADLS -> Postgres/MySQL) | Missing | Phase 8 |
| **Testing** | Emulators: Azurite (Azure), Moto/LocalStack (AWS), Fake GCS Server | Missing | Phase 9 |
| **Testing** | Live Credential Gated E2E Scenarios | Missing | Phase 9 |
| **Hardening**| Worker Execution, Cancellation Tokens, Heartbeats, Metrics | Partial (Basic Celery/Thread worker exists) | Phase 10 |

---

## 4. Root Causes & Architectural Deficits

1. **Schema Coupling:** The existing `BaseConnector` defines `discover_tables()` and `execute_query()`, coupling every connector to SQL-like systems.
2. **Memory Inefficiency:** Loading whole chunks into memory as lists of Python dicts incurs significant memory amplification (often 5x to 10x the raw data size).
3. **Missing Abstraction Layer for Object Stores:** Cloud storage concepts (buckets, containers, prefixes, keys, parts, resumable sessions) are distinct from database concepts (catalogs, schemas, tables, rows, columns). A parallel `BaseStorageConnector` hierarchy is required that seamlessly bridges into `CopyDataActivity`.
4. **Static UI Forms:** The frontend connection and activity drawers were built with static relational form fields rather than provider-aware dynamic schemas.

---

## 5. Implementation Roadmap Alignment

The identified gaps map directly to the 11-phase development strategy:
- **Phase 0:** Audit & Architecture Specifications (Current).
- **Phase 1:** Common Storage Connector Framework.
- **Phase 2:** Azure Storage Integration.
- **Phase 3:** Amazon S3 Integration.
- **Phase 4:** Google Cloud Storage Integration.
- **Phase 5:** Copy Data Frontend Enhancement.
- **Phase 6:** File Format and Schema Framework.
- **Phase 7:** Multi-Cloud Transfer Engine.
- **Phase 8:** Cross-Cloud & Hybrid Transfers.
- **Phase 9:** Verification, Emulators & Scenarios.
- **Phase 10:** Production Readiness & Security Hardening.
