# DataForge Enterprise — Transfer Optimization & Tuning Guide

## 1. Overview

The DataForge Multi-Cloud Copy Data Engine is architected to stream gigabyte and terabyte datasets across cloud providers with a constant, bounded RAM footprint. This guide provides concrete tuning recommendations to maximize network throughput and minimize cloud egress costs.

---

## 2. Core Memory Architecture

### The Bounded Transfer Buffer (`BoundedTransferBuffer`)
- Transfers do not buffer entire files in memory or write unencrypted intermediate staging files to local disks.
- The `BoundedTransferBuffer` couples producer (source stream reader) and consumer (destination stream writer) using a thread-safe synchronized queue with backpressure.
- Maximum RAM usage during binary transfers is deterministically bounded by:
  $$\text{RAM}_{\text{max}} = (\text{max\_buffered\_chunks} + 1) \times \text{chunk\_size}$$
- For default settings ($4 \times 8\,\text{MB}$), the active streaming buffer never exceeds **$40\,\text{MB}$**, regardless of whether transferring 100MB, 1GB, or 100GB.

---

## 3. Performance Tuning Parameters

### A. Chunk Size (`chunk_size`)
- **Default:** `8,388,608` bytes (8 MB).
- **Small Files (< 50MB):** Set `chunk_size = 4,194,304` (4 MB) to reduce first-byte latency.
- **Large Files (> 1GB):** Increase `chunk_size = 16,777,216` (16 MB) or `33,554,432` (32 MB) to maximize WAN throughput and saturation of 10Gbps+ network links.

### B. S3 Multipart Upload Tuning
- `multipart_threshold`: Size at which S3 transfers switch from standard `PutObject` to multipart uploads. Default: `8 MB`.
- `multipart_part_size`: Part size for S3 multipart uploads. Must be $\ge 5\,\text{MB}$. Recommended: `8 MB` or `16 MB`.

### C. GCS Resumable Upload Alignment
- Google Cloud Storage resumable upload chunk sizes **must** be an exact multiple of $256\,\text{KB}$ ($262,144$ bytes).
- DataForge automatically enforces this alignment, defaulting to `8 MB` ($32 \times 256\,\text{KB}$).

### D. Relational Ingestion Batch Size (`batch_size`)
- Controls how many database rows are fetched and flushed per chunk.
- **Default:** `5,000` rows.
- **Wide Tables (> 50 columns):** Reduce to `1,000` - `2,500` rows to prevent memory pressure during record transformation.
- **Narrow Tables (< 10 columns):** Increase to `10,000` - `25,000` rows for maximum vectorized insertion speeds.

---

## 4. File Format Selection & Compression Matrix

| Format | Read Speed | Write Speed | Compression Ratio | Schema Evolution | Best Fit |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Parquet** | ★★★★★ | ★★★★☆ | ★★★★★ (Snappy/GZIP) | Excellent | Cloud Data Warehouses, Lakehouses, Columnar Analytics |
| **ORC** | ★★★★★ | ★★★★☆ | ★★★★★ (ZLIB/Snappy) | Good | Apache Hive, Presto/Trino, Databricks |
| **Avro** | ★★★★☆ | ★★★★★ | ★★★★☆ (Deflate/Snappy)| Superb | Event Streaming, Schema Registry, Row-based storage |
| **JSON Lines** | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ (GZIP) | Dynamic | Microservices, Log aggregation, Unstructured events |
| **CSV** | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ (GZIP) | Poor | Human review, Legacy ERP exchanges |
| **Excel** | ★★☆☆☆ | ★★☆☆☆ | ★★☆☆☆ (ZIP) | None | Business user reporting (< 100k rows) |

---

## 5. Checksum Verification Overhead

DataForge supports streaming MD5, SHA-256, and hardware-accelerated CRC32C:
- **CRC32C (Castagnoli):** Uses CPU SSE4.2 hardware instructions. Near-zero CPU overhead (~0.5%). Recommended for GCS and high-throughput pipelines.
- **MD5:** Standard for AWS S3 and Azure Blob. Moderate CPU overhead (~2-3%).
- **SHA-256:** Cryptographically secure. Recommended for financial audit compliance.
