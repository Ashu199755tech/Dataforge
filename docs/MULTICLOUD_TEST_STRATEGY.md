# DataForge Multi-Cloud Copy Data Engine — Test Strategy

## 1. Overview & Quality Objectives

The DataForge Multi-Cloud Copy Data Engine moves mission-critical enterprise data across heterogeneous cloud providers and internal databases. To guarantee strict data integrity, zero memory leaks, and seamless resilience, testing must be structured across multiple complementary tiers.

### Core Testing Objectives:
1. **Zero Credential Exposure:** Verify no tokens, secret keys, or headers leak into logs, exceptions, or payloads.
2. **Data Parity & Exact Row Counts:** Verify that destination data matches source data bit-for-bit or record-for-record.
3. **Bounded Memory Execution:** Verify transfers of arbitrary file sizes (including multi-gigabyte objects) run within a constant RAM footprint ($< 256\text{MB}$).
4. **Graceful Degradation:** Verify that when cloud SDKs are missing, the system emits clear diagnostic errors rather than unhandled crashes.
5. **No Fake Progress or Stubs:** Verify actual bytes are read and written across local emulators and live cloud services.

---

## 2. Test Architecture Tiers

```
+-------------------------------------------------------------------------+
| Tier 5: Live Cloud Verification (Credential-Gated, Opt-in)              |
| Live AWS S3, Azure ADLS/Blob, Google Cloud Storage                      |
+-------------------------------------------------------------------------+
                                   ^
+-------------------------------------------------------------------------+
| Tier 4: Cross-Cloud & Hybrid End-to-End Scenarios                       |
| DB -> S3 -> GCS -> ADLS -> DB roundtrip pipelines                      |
+-------------------------------------------------------------------------+
                                   ^
+-------------------------------------------------------------------------+
| Tier 3: Local Storage Emulators                                         |
| Azurite (Azure Blob/ADLS), Moto (AWS S3), GCS Testbench (GCP)           |
+-------------------------------------------------------------------------+
                                   ^
+-------------------------------------------------------------------------+
| Tier 2: Format & Transcoding Validation                                 |
| PyArrow RecordBatch conversions (CSV, Parquet, JSON, Avro, ORC, Excel)  |
+-------------------------------------------------------------------------+
                                   ^
+-------------------------------------------------------------------------+
| Tier 1: Unit & Protocol Tests (Fast, In-Memory, Mock-driven)            |
| Schema validation, Capability checking, Configuration parsing           |
+-------------------------------------------------------------------------+
```

---

## 3. Tier Details & Tooling

### Tier 1: Unit & Protocol Tests
- **Scope:** Storage configuration models, registry dynamic loader, URL parsing, credentials validation, and capability checks.
- **Dependencies:** Standard library, `pydantic`, `pytest`.
- **Execution:** Fast ($< 5\text{s}$), runs in every CI pipeline.

### Tier 2: Format & Transcoding Tests
- **Scope:** PyArrow reader/writer streaming, schema inference, type coercion (e.g. timestamp string to timestamp object), nested JSON flattening, and delimiter parsing.
- **Verification:** Row count assertions, column type equality, null handling, and low-memory head preview.

### Tier 3: Storage Emulator Tests
Storage emulators allow 100% realistic API interaction without incurred cloud bills or network dependencies.
- **Azure (Blob & ADLS Gen2):**
  - Tool: `Azurite` (npm package `azurite` or Docker container).
  - Protocol: Azure REST API on ports 10000 (Blob) and 10002 (ADLS).
  - Fallback: In-process fake storage client conforming to `azure-storage-blob` interface.
- **AWS (Amazon S3):**
  - Tool: `moto` (`moto[s3]`) or `localstack`.
  - Protocol: In-process mocked AWS endpoint intercepting `botocore` requests.
  - Features Tested: Multipart uploads, server-side encryption headers, prefix delimiter listings.
- **Google Cloud Platform (GCS):**
  - Tool: `google-cloud-storage` test bench or filesystem-backed mock client.
  - Features Tested: Resumable upload sessions, blob metadata, bucket creation.

### Tier 4: Cross-Cloud & Hybrid Transfers
- **Scope:** Orchestrated transfers across heterogeneous source and destination pairs:
  1. PostgreSQL table $\to$ Amazon S3 Parquet file.
  2. Amazon S3 Parquet file $\to$ Azure ADLS Gen2 CSV file.
  3. Azure ADLS Gen2 CSV file $\to$ Google Cloud Storage JSONL file.
  4. Google Cloud Storage JSONL file $\to$ MySQL table.
- **Verification:** Row count equality, SHA-256 hash comparison (for binary transfers), column value assertions.

### Tier 5: Live Cloud Verification (Credential-Gated)
- Live tests are conditionally executed when environment variables are detected:
  - `DATAFORGE_AZURE_STORAGE_CONNECTION_STRING`
  - `DATAFORGE_AWS_ACCESS_KEY_ID` & `DATAFORGE_AWS_SECRET_ACCESS_KEY`
  - `DATAFORGE_GCP_SERVICE_ACCOUNT_KEY`
- When variables are absent, `pytest.mark.skipif` cleanly skips live tests with informative explanations.

---

## 4. Test Matrix

| Provider / Feature | Unit Tests | Emulator Tests | Format Transcoding | Live Cloud Tests |
| :--- | :---: | :---: | :---: | :---: |
| Azure Blob Storage | Yes | Azurite | CSV, Parquet, JSON | Live (if configured) |
| Azure ADLS Gen2 | Yes | Azurite | CSV, Parquet, JSON | Live (if configured) |
| Amazon S3 | Yes | Moto | All 8 Formats | Live (if configured) |
| Google Cloud Storage | Yes | Fake GCS | All 8 Formats | Live (if configured) |
| Cross-Cloud S3 $\to$ GCS | Yes | Moto $\to$ Fake GCS | Binary & Parquet | Live (if configured) |
| Cross-Cloud GCS $\to$ ADLS | Yes | Fake GCS $\to$ Azurite | Binary & CSV | Live (if configured) |
| DB $\to$ S3 (PostgreSQL) | Yes | Real PG $\to$ Moto | Parquet, CSV | Live (if configured) |
| S3 $\to$ DB (PostgreSQL) | Yes | Moto $\to$ Real PG | Batch Insert / Copy | Live (if configured) |

---

## 5. Performance & Memory Profiling Strategy

To verify compliance with the bounded-memory architecture:
1. **Generator / Chunk Verification:** Automated tests assert that data readers yield `Iterator[bytes]` or `Iterator[pa.RecordBatch]` without loading the entire payload into a single list or bytearray.
2. **Memory Tracking Test:** Using Python's `tracemalloc` or `psutil`:
   - Generate a 500MB synthetic source stream.
   - Run transfer through `TransferEngine`.
   - Assert peak memory consumption during transfer stays below 128MB.
3. **Throughput Benchmark:** Measure transfer throughput (MB/s) and verify minimal overhead compared to raw network/disk speed.
