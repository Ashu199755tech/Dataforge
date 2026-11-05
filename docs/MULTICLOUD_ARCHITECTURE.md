# DataForge Multi-Cloud Copy Data Engine — Architecture Specification

## 1. Architectural Overview

The DataForge Multi-Cloud Copy Data Engine provides high-throughput, memory-bounded, secure data movement across heterogeneous storage providers:
- **Cloud Object Storage:** Azure Blob, Azure Data Lake Storage Gen2 (ADLS Gen2), Amazon S3, Google Cloud Storage (GCS).
- **Relational Databases:** PostgreSQL, MySQL, SQLite, Snowflake/Redshift (via extension).
- **Local / Network File Systems:** POSIX compliant directories, NFS, SMB mounts.

```
                           +----------------------------------------+
                           |          DataForge Pipeline DAG        |
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           |           CopyDataActivity             |
                           +-------------------+--------------------+
                                               |
         +-------------------------------------+-------------------------------------+
         |                                                                           |
         v                                                                           v
+-------------------+                                                       +-------------------+
|  Source Connector |                                                       | Dest Connector    |
|  (BaseStorage /   |                                                       | (BaseStorage /    |
|   BaseConnector)  |                                                       |  BaseConnector)   |
+---------+---------+                                                       +---------+---------+
          |                                                                           ^
          | (Raw Bytes / PyArrow Batches)                           (Chunks / Batches)|
          v                                                                           |
+-------------------------------------------------------------------------------------+---------+
|                                    TRANSFER ENGINE                                            |
|                                                                                               |
|  +--------------------+       +--------------------+       +-------------------------------+  |
|  |   Source Reader    | ----> |   Memory Buffer    | ----> |      Destination Writer       |  |
|  | (Binary / Tabular) |       | (Backpressure Q)   |       | (Multipart / Resumable / DB)  |  |
|  +--------------------+       +--------------------+       +-------------------------------+  |
|                                         |                                                     |
|                                         v                                                     |
|                               +--------------------+                                          |
|                               |  Metrics / Progress|                                          |
|                               | (Bytes, Rows, ETA) |                                          |
|                               +--------------------+                                          |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Core Abstractions & Interfaces

### 2.1 The Storage Model: `StorageItem` & `StorageMetadata`

Unlike relational databases structured into catalogs, schemas, and tables, object storage is structured into buckets/containers, hierarchical prefixes, and objects/blobs.

```python
class StorageItem(BaseModel):
    name: str                           # Relative filename or folder name
    path: str                           # Full path within bucket/container (e.g., 'raw/2026/01/data.parquet')
    is_directory: bool                  # True if represents directory/prefix
    size_in_bytes: int = 0              # Size in bytes (0 for virtual folders)
    last_modified: Optional[datetime]   # Last modified timestamp
    content_type: Optional[str] = None  # MIME type (e.g., 'application/octet-stream')
    etag: Optional[str] = None          # Entity tag / MD5 hex
    metadata: Dict[str, str] = {}       # Custom key-value metadata tags
    storage_tier: Optional[str] = None  # Hot, Cool, Archive, Standard, Glacier, etc.
```

### 2.2 Capabilities Model

Different storage providers offer varying features (e.g., POSIX directory operations in ADLS Gen2 vs simulated virtual directories in S3). DataForge uses a capability-based interface pattern:

```python
class StorageCapability(str, Enum):
    BUCKET_DISCOVERY = "bucket_discovery"
    HIERARCHICAL_NAMESPACE = "hierarchical_namespace"  # Atomic directory operations (ADLS Gen2)
    MULTIPART_UPLOAD = "multipart_upload"              # AWS S3, Azure Block Blob
    RESUMABLE_UPLOAD = "resumable_upload"              # GCS Resumable Sessions
    SERVER_SIDE_ENCRYPTION = "server_side_encryption"  # KMS / Customer-provided keys
    STORAGE_TIERING = "storage_tiering"                # Hot / Cool / Cold / Archive
    PRESIGNED_URLS = "presigned_urls"                  # Ephemeral shared access
```

### 2.3 The Common Storage Connector Interface: `BaseStorageConnector`

`BaseStorageConnector` inherits from `BaseConnector` to preserve compatibility with existing activity runners, but introduces dedicated storage lifecycle methods:

```python
class BaseStorageConnector(BaseConnector):
    """Abstract base for all cloud and local object storage providers."""

    @abstractmethod
    def get_capabilities(self) -> Set[StorageCapability]:
        """Returns the set of capabilities supported by this provider."""
        pass

    @abstractmethod
    def list_containers(self) -> List[str]:
        """Lists containers (Azure) or buckets (AWS/GCP)."""
        pass

    @abstractmethod
    def list_objects(
        self,
        container: str,
        prefix: str = "",
        recursive: bool = False,
        limit: Optional[int] = None
    ) -> Iterator[StorageItem]:
        """Lists objects and virtual directories matching a prefix."""
        pass

    @abstractmethod
    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        """Retrieves metadata for a specific object."""
        pass

    @abstractmethod
    def read_stream(
        self,
        container: str,
        object_key: str,
        chunk_size: int = 4 * 1024 * 1024  # 4MB default chunk
    ) -> Iterator[bytes]:
        """Streams object content as raw binary byte chunks."""
        pass

    @abstractmethod
    def write_stream(
        self,
        container: str,
        object_key: str,
        stream: Iterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        """Uploads an object from a byte stream using provider multipart/resumable upload."""
        pass

    @abstractmethod
    def delete_object(self, container: str, object_key: str) -> bool:
        """Deletes a specific object."""
        pass

    @abstractmethod
    def copy_object(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        """Copies an object within the same provider."""
        pass
```

---

## 3. Provider SDK Isolation & Dynamic Loading

In compliance with **Rule 20 ("Do not make Azure, AWS or GCP mandatory for the core platform")**, no provider SDK (`boto3`, `azure-*`, `google-cloud-*`) may be an unconditional top-level import in `backend/app/main.py` or `BaseConnector`.

### Provider Registration Architecture:
1. Provider implementations reside in isolated modules:
   - `backend/app/connectors/storage/azure_blob.py`
   - `backend/app/connectors/storage/azure_adls.py`
   - `backend/app/connectors/storage/aws_s3.py`
   - `backend/app/connectors/storage/gcp_storage.py`
   - `backend/app/connectors/storage/local_storage.py`
2. Each provider module checks dependency availability gracefully:
   ```python
   try:
       import boto3
       from botocore.exceptions import ClientError
       HAS_BOTO3 = True
   except ImportError:
       HAS_BOTO3 = False
   ```
3. A centralized **Provider Registry** (`backend/app/connectors/storage/registry.py`) maintains registered providers, inspects SDK presence, and returns clear diagnostics:
   ```python
   class StorageProviderRegistry:
       @classmethod
       def is_provider_available(cls, provider_type: str) -> bool:
           ...
       @classmethod
       def get_missing_dependency_message(cls, provider_type: str) -> str:
           ...
   ```

---

## 4. Multi-Cloud Data Movement Pipelines

DataForge supports two primary data pipelines depending on the source and destination nature:

### Pipeline A: Binary Streaming Pipeline (Zero-Transform Direct Transfer)
*Used for: Cross-cloud file transfers (e.g., S3 `.parquet` to GCS `.parquet`) and unparsed file archival.*
- **Step 1:** Source Reader opens an HTTP range/chunk stream from cloud source via provider SDK (e.g., `s3_client.get_object()['Body'].read(chunk_size)`).
- **Step 2:** Byte chunks enter a memory-bounded producer-consumer queue (`queue.Queue(maxsize=4)`).
- **Step 3:** Destination Writer processes chunks via multipart upload (`UploadPart` in S3/ADLS or resumable session in GCS).
- **Step 4:** Checksums (CRC32C / MD5 / SHA-256) are calculated on the fly during transfer and validated before finalizing the upload.
- **Memory Footprint:** Fixed and bounded: $RAM = BufferSize \times ChunkSize \times Concurrency$ (e.g., $4 \times 8\text{MB} = 32\text{MB}$ per worker).

### Pipeline B: Tabular RecordBatch Pipeline (Format Transform & Database Hybrid)
*Used for: DB to Cloud (PostgreSQL -> Parquet), Cloud to DB (S3 CSV -> MySQL), or Format Transcoding (CSV -> Parquet).*
- **Step 1:** Source Reader yields chunks of PyArrow `RecordBatch` or relational cursor chunks.
- **Step 2:** Transformer applies column projections, data type conversions, schema validation, and row filtering.
- **Step 3:** Format Writer encodes batches into target format (PyArrow Parquet writer, CSV streaming writer) and streams directly to destination storage or database batch insert.
- **Memory Footprint:** PyArrow zero-copy record batches streamed in configurable chunk sizes (e.g., 5,000 to 50,000 records).

---

## 5. Security Architecture & Credential Protection

### 5.1 Credential Encapsulation
- All connection configurations (access keys, service account JSONs, client secrets, SAS tokens) are encrypted at rest using AES-256 Fernet via `encrypt_secret` in `backend/app/core/security.py`.
- Plaintext secrets are strictly decrypted in-memory inside worker execution threads and immediately discarded after connector initialization or session creation.

### 5.2 Zero-Credential Leakage Guarantee
1. **API Responses:** `ConnectionResponse` schema excludes sensitive fields, returning only masked metadata (e.g., `has_secret=True`, `auth_type="service_principal"`).
2. **Execution Logs:** The activity logger uses regex-based sanitizers to strip access keys, tokens, authorization headers, and SAS query strings before persisting logs to PostgreSQL.
3. **Pipeline JSON Export:** Pipeline definitions refer to connections by foreign key `connection_id`; no credentials reside in DAG JSON.

### 5.3 Authentication Modalities
- **Azure:**
  - Account Key (SharedKey).
  - Shared Access Signature (SAS Token).
  - Service Principal (Client ID, Client Secret, Tenant ID).
  - Managed Identity (System-assigned or User-assigned Client ID).
- **AWS:**
  - IAM Access Key & Secret Key (with optional Session Token).
  - STS AssumeRole (Role ARN, External ID, Session Name).
  - AWS IAM Instance Profile / ECS Task Role (Default Credentials Chain).
- **GCP:**
  - Service Account JSON Key (uploaded file or inline JSON).
  - Application Default Credentials (ADC) from environment.
  - Workload Identity Federation (WIF) & Impersonated Service Accounts.

---

## 6. Background Execution & Observability

1. **Decoupled Execution:** Transfers run exclusively in Celery / thread background workers, never inside FastAPI HTTP request-response cycles.
2. **Cancellation:** Workers periodically poll an atomic `cancellation_token` or Redis/database state between chunk transfers. Upon cancellation, open multipart uploads are aborted to prevent orphaned cloud storage charges.
3. **Metrics & Progress:** Real-time updates emitted to `activity_runs`:
   - `bytes_processed`, `rows_read`, `rows_written`.
   - `throughput_bytes_per_sec`, `estimated_time_remaining`.
   - `current_chunk_index`, `active_file_name`.
