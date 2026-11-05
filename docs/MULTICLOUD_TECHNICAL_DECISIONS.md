# DataForge Multi-Cloud Copy Data Engine — Architectural Decision Records (ADRs)

## ADR-MC001: Capability-Based Storage Connector Interface vs Monolithic Interface

### Status
Accepted

### Context
DataForge previously defined a single `BaseConnector` interface with methods like `discover_tables()`, `read_data_stream()`, and `execute_query()`. While appropriate for relational databases (PostgreSQL, MySQL, SQLite), object storage providers (Azure Blob, ADLS Gen2, AWS S3, Google Cloud Storage) have fundamentally different structural and operational paradigms:
- Flat or hierarchical namespaces rather than catalogs and schemas.
- Buckets, containers, and prefix-delimited keys rather than tables and views.
- Multipart and resumable upload streams rather than SQL `INSERT` batches.
- Asymmetric feature sets (e.g., ADLS Gen2 supports atomic directory renames and POSIX ACLs, whereas AWS S3 and Azure Blob treat directories as simulated prefixes).

### Decision
Introduce `BaseStorageConnector`, extending `BaseConnector` while introducing storage-native methods (`list_containers()`, `list_objects()`, `read_stream()`, `write_stream()`, `delete_object()`, `copy_object()`). Provide a formal `StorageCapability` enum so connectors declare exactly which operations they support (e.g., `HIERARCHICAL_NAMESPACE`, `MULTIPART_UPLOAD`, `RESUMABLE_UPLOAD`, `SERVER_SIDE_ENCRYPTION`).

### Consequences
- **Positive:** Connectors do not need to implement stubbed or unsupported methods.
- **Positive:** The transfer engine and UI can inspect capabilities before attempting operations (e.g. disabling directory rename on flat object stores).
- **Negative:** Dual inheritance and adaptation layer needed when relational activities interact with storage connectors.

---

## ADR-MC002: Dynamic Lazy-Loading of Cloud SDKs (Rule 20 Compliance)

### Status
Accepted

### Context
DataForge core platform runs on standard Linux/macOS environments and must remain lightweight. Non-Negotiable Rule 20 states: *"Do not make Azure, AWS or GCP mandatory for the core platform."* Bundling `boto3`, `azure-storage-blob`, `azure-identity`, and `google-cloud-storage` as hard dependencies could cause dependency conflicts, slow application startup, and bloat installations for users who only use local storage or relational databases.

### Decision
Implement provider SDKs with dynamic imports inside isolated connector modules. Provide a centralized `StorageProviderRegistry` that tracks available providers and emits diagnostic messages explaining how to install missing dependencies (e.g., `pip install boto3` or `pip install dataforge[aws]`).

### Consequences
- **Positive:** Core platform boots and runs tests cleanly with zero cloud SDKs installed.
- **Positive:** Strict modular isolation; bugs in one cloud SDK cannot impact others.
- **Negative:** Connector instantiation must check `is_available()` before attempting connections.

---

## ADR-MC003: Memory-Bounded Chunk Streaming Pipeline vs Disk Spooling

### Status
Accepted

### Context
When transferring multi-gigabyte or terabyte-scale files across clouds or from database to cloud, two traditional transfer patterns exist:
1. **Disk Spooling:** Download the complete source file to a temporary worker disk directory, then upload it to the destination.
2. **Chunked Memory Streaming:** Read byte chunks from the source, pass through a bounded in-memory buffer queue, and upload directly to the destination using multipart/resumable APIs.

### Decision
Adopt **Chunked Memory Streaming** with a bounded backpressure queue (`queue.Queue(maxsize=4)`) as the primary data transfer path. Only fall back to local disk staging when a destination provider requires a known fixed `Content-Length` before beginning upload and chunked multipart APIs are unavailable.

### Consequences
- **Positive:** Zero disk I/O bottlenecks and zero disk space exhaustion on worker hosts.
- **Positive:** Constant memory consumption ($< 256\text{MB}$) regardless of whether the file is 10MB or 100GB.
- **Positive:** Lower latency because upload starts immediately as the first chunk arrives from the source.
- **Negative:** Network drop mid-transfer requires chunk-level retry handling.

---

## ADR-MC004: PyArrow RecordBatch as Common Intermediate Tabular Representation

### Status
Accepted

### Context
When moving data between databases and cloud files (or transcoding between CSV, Parquet, JSON, Avro, ORC), DataForge previously represented records as lists of Python dicts (`List[Dict[str, Any]]`). For 100,000 records, Python dicts consume 5x to 10x the memory of raw data, introduce high garbage collection pauses, and lack strict columnar typing.

### Decision
Standardize on Apache Arrow (`pyarrow.RecordBatch`) as the common intermediate in-memory tabular data structure for all format conversions and database-to-cloud streams.

### Consequences
- **Positive:** High performance C++ streaming columnar engine with zero-copy conversions.
- **Positive:** Direct native support for reading and writing Parquet, CSV, Feather, and ORC.
- **Positive:** Preserves precise typing (timestamps, decimals, nested structs) without string serialization.
- **Negative:** Requires `pyarrow` dependency (already present in DataForge venv).

---

## ADR-MC005: Unified Credential Storage using Existing AES-256 Fernet Encryption

### Status
Accepted

### Context
Cloud connections require sensitive secrets: AWS secret access keys, Azure storage account keys, Azure client secrets, and GCP service account private keys. DataForge already has an established AES-256 Fernet encryption layer (`encrypt_secret` and `decrypt_secret` in `backend/app/core/security.py`).

### Decision
Reuse the existing AES-256 Fernet encryption system for all cloud storage credentials. Store credentials inside `connections.config_encrypted`. Decrypt strictly in-memory within worker execution contexts. Never expose decrypted configs in API responses, pipeline JSON, or audit logs.

### Consequences
- **Positive:** Reuses proven, tested cryptographic infrastructure.
- **Positive:** Fully preserves database schema compatibility with the existing `Connection` model.
- **Negative:** Fernet keys must be properly backed up in enterprise deployments (`SECRET_KEY`).

---

## ADR-MC006: Local Testing Strategy with Azurite, Moto, and GCS Mocks

### Status
Accepted

### Context
Testing cloud integrations during continuous integration and local development cannot depend on live cloud accounts, which incur billing costs, require network connectivity, and risk credential leakage.

### Decision
Implement a multi-tier testing architecture using industry-standard local emulators and mocks:
1. **Azure:** Azurite emulator (or local filesystem adapter conforming to Azure SDK).
2. **AWS:** Moto (`moto[s3]`) in-process server.
3. **GCP:** Google Cloud Storage Testbench / emulator.
4. **Live Clouds:** Optional, gated behind explicit environment variables.

### Consequences
- **Positive:** Unit and integration test suites run 100% offline with zero cloud bills.
- **Positive:** Fast test execution in automated CI environments.
- **Negative:** Emulators may lag behind the newest cloud provider edge features.
