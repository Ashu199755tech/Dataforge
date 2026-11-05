# DataForge Multi-Cloud Copy Data Engine — Known Technical Limitations

## 1. Overview

While the DataForge Multi-Cloud Copy Data Engine provides enterprise-grade data movement across Azure, AWS, GCP, and relational databases, certain architectural and cloud-provider boundaries exist. This document details these limitations, their technical root causes, and recommended workarounds.

---

## 2. Cloud Provider Specific Limitations

### 2.1 Non-Direct Cross-Cloud Transfers
- **Limitation:** Cloud object storage providers (AWS S3, Azure Blob/ADLS, GCP GCS) do not possess native peering mechanisms to transfer data directly between each other's proprietary APIs without an intermediary host.
- **DataForge Mechanism:** DataForge acts as the streaming proxy. Data flows securely through DataForge worker memory buffers without touching local disk.
- **Bandwidth Implication:** Egress and ingress charges will apply from the source cloud provider, and DataForge worker host network bandwidth determines maximum cross-cloud throughput.

### 2.2 S3 vs ADLS Gen2 Hierarchical Directory Semantics
- **AWS S3 & Azure Blob Storage:** Are object stores with a flat namespace. Directories do not exist as real filesystem objects; they are simulated using forward slash delimiters (`/`). Deleting or renaming a "folder" requires listing and deleting or renaming every object under that prefix individually.
- **ADLS Gen2:** Possesses a true hierarchical namespace (POSIX filesystem). Renaming a directory is an atomic metadata operation ($O(1)$).
- **Engine Behavior:** Directory rename and delete operations are atomic on ADLS Gen2, but execute as iterative prefix walks on Amazon S3 and Azure Blob.

### 2.3 Cloud Storage Multipart & Chunk Size Constraints
- **AWS S3:**
  - Minimum multipart upload part size is **5 MB** (except for the last part).
  - Maximum parts per object: **10,000**.
  - Maximum single object size: **5 TB**.
- **Google Cloud Storage (GCS):**
  - Resumable upload chunk size must be a multiple of **256 KB** ($256 \times 1024$ bytes). Recommended chunk size is $\ge 8\text{MB}$.
- **Azure Blob Storage:**
  - Block blob maximum block size is **4,000 MB** (version 2019-12-12 and newer), with a maximum of **50,000 blocks**.
- **Engine Adaptation:** DataForge `TransferEngine` automatically normalizes streaming chunks to satisfy provider minimum part thresholds (e.g., standardizing on 8MB chunks for cross-cloud streaming).

### 2.4 Cloud Authentication Boundaries
- **AWS IAM Instance Profiles & STS AssumeRole:** Can only auto-negotiate credentials if DataForge runs within AWS (EC2/ECS/EKS) or if external access keys with `sts:AssumeRole` permissions are provided.
- **Azure Managed Identity:** Only accessible when DataForge runs on Azure VMs, AKS, or Azure App Services. For external deployments, Service Principal (Client ID + Client Secret + Tenant ID) or Account Key must be used.
- **GCP Workload Identity:** Only accessible natively within GKE/GCP Compute. External deployments require Service Account JSON keys.

---

## 3. File Format & Schema Limitations

### 3.1 Excel (.xlsx / .xls) File Constraints
- Maximum row limit: **1,048,576 rows** per worksheet (strict OpenXML specification).
- High memory footprint: OpenXML parsing requires significantly more memory than Parquet or CSV. For files exceeding 100,000 rows, Parquet or CSV should be used instead.
- Excel files cannot be streamed in chunks for writing without specialized zip stream handling; DataForge writes Excel files using buffered worksheet batches.

### 3.2 Avro & ORC Complex Types
- Avro and ORC formats require strict schemas prior to writing. Unlike CSV/JSON which can infer schemas dynamically during streaming, Avro/ORC writing requires either:
  1. An explicit schema provided in the activity configuration.
  2. A pre-pass schema inference over the initial record batch.

### 3.3 Parquet Schema Evolution
- When appending multiple batches to a single destination Parquet directory, schema evolution (e.g., new nullable columns) is supported by PyArrow/Hive partition conventions, but schema conflicts (e.g., column `id` changing from `int32` to `string`) will cause read failures unless explicitly mapped.

---

## 4. Execution Engine & Infrastructure Boundaries

### 4.1 Bounded Worker Concurrency
- The number of concurrent file transfers is constrained by the worker thread pool capacity and network interface bandwidth.
- Recommended worker sizing: 2 concurrent transfers per CPU core, with a baseline buffer pool of 64MB RAM per transfer.

### 4.2 Network Timeouts on Very Large Single Objects
- When transferring very large files ($> 100\text{GB}$) over unstable network links, individual chunk upload retries are supported. However, if a transfer is cancelled or the worker crashes, resumable sessions are preserved up to their provider timeout (typically 24 hours for GCS resumable sessions and 7 days for S3 multipart uploads).
