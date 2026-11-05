# DataForge Enterprise — Multi-Cloud Connector Configuration Guide

## 1. Overview

DataForge Enterprise provides native, high-performance connectors for enterprise object stores and relational data engines. Connectors are dynamically discovered and lazy-loaded via the `StorageProviderRegistry`.

All connection configurations are encrypted in the metadata database using AES-256 Fernet encryption and are never exposed in plaintext in logs, API responses, or pipeline definitions.

---

## 2. Microsoft Azure Storage

DataForge supports two dedicated connectors for Azure Storage:
- **Azure Blob Storage (`azure_blob`)**
- **Azure Data Lake Storage Gen2 (`azure_adls`)**

### Supported Authentication Modes

#### Mode 1: Account Key
```json
{
  "account_name": "dataforgelakehouse",
  "account_key": "YOUR_STORAGE_ACCOUNT_KEY==",
  "auth_mode": "account_key"
}
```

#### Mode 2: Shared Access Signature (SAS) Token
```json
{
  "account_name": "dataforgelakehouse",
  "sas_token": "?sv=2021-06-08&ss=bfqt&srt=sco&sp=rwdlacupx&se=2027-01-01T00:00:00Z&st=2026-01-01T00:00:00Z&spr=https&sig=...",
  "auth_mode": "sas_token"
}
```

#### Mode 3: Azure Entra ID / Service Principal
```json
{
  "account_name": "dataforgelakehouse",
  "auth_mode": "service_principal",
  "client_id": "00000000-0000-0000-0000-000000000000",
  "client_secret": "YOUR_AZURE_CLIENT_SECRET",
  "tenant_id": "11111111-1111-1111-1111-111111111111"
}
```

#### Mode 4: Managed Identity (Azure VM / AKS / Container App)
```json
{
  "account_name": "dataforgelakehouse",
  "auth_mode": "managed_identity",
  "client_id": "OPTIONAL_USER_ASSIGNED_MANAGED_IDENTITY_CLIENT_ID"
}
```

#### Mode 5: Connection String (Legacy / Azurite Emulator)
```json
{
  "connection_string": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10150/devstoreaccount1;",
  "account_name": "devstoreaccount1"
}
```

---

## 3. Amazon Web Services (AWS) S3

DataForge provides direct streaming integration with Amazon S3 (`aws_s3`).

### Supported Authentication Modes

#### Mode 1: IAM Access Key & Secret Key
```json
{
  "bucket": "dataforge-corp-lake",
  "region_name": "us-east-1",
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

#### Mode 2: Temporary Session Credentials
```json
{
  "bucket": "dataforge-corp-lake",
  "region_name": "us-east-1",
  "access_key_id": "ASIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "session_token": "AQoDYXdzEJr111111111111111111111..."
}
```

#### Mode 3: IAM Role / STS AssumeRole
```json
{
  "bucket": "dataforge-corp-lake",
  "region_name": "us-east-1",
  "role_arn": "arn:aws:iam::123456789012:role/DataForgeIngestionRole",
  "role_session_name": "DataForgeSession",
  "external_id": "CorpSecurityToken123"
}
```

#### Advanced S3 Settings
- `multipart_threshold`: Size in bytes before triggering multipart upload (default: `8,388,608` / 8MB).
- `multipart_part_size`: Chunk size for each multipart part (default: `8,388,608` / 8MB).
- `server_side_encryption`: `AES256` or `aws:kms`.
- `kms_key_id`: AWS KMS Key ARN or Alias when KMS encryption is selected.

---

## 4. Google Cloud Platform (GCP) Cloud Storage

DataForge provides direct integration with Google Cloud Storage (`gcp_storage`).

### Supported Authentication Modes

#### Mode 1: Service Account Key JSON
```json
{
  "bucket": "dataforge-gcs-lake",
  "project_id": "corporate-analytics-prod",
  "service_account_json": {
    "type": "service_account",
    "project_id": "corporate-analytics-prod",
    "private_key_id": "a1b2c3d4...",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
    "client_email": "dataforge-sa@corporate-analytics-prod.iam.gserviceaccount.com",
    "client_id": "123456789012345678901",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

#### Mode 2: Application Default Credentials (ADC) / GKE Workload Identity
```json
{
  "bucket": "dataforge-gcs-lake",
  "project_id": "corporate-analytics-prod",
  "auth_mode": "adc"
}
```

#### Mode 3: Service Account Impersonation
```json
{
  "bucket": "dataforge-gcs-lake",
  "project_id": "corporate-analytics-prod",
  "auth_mode": "adc",
  "impersonate_service_account": "dataforge-writer@corporate-analytics-prod.iam.gserviceaccount.com"
}
```

---

## 5. Local POSIX Storage

For on-premises edge nodes and local testing:
```json
{
  "base_path": "/var/dataforge/storage"
}
```

---

## 6. Relational Database Connectors

DataForge supports hybrid ingestion and reverse ETL for:
- **PostgreSQL 14+ / 16** (`postgresql`)
- **MySQL 8.0+** (`mysql`)
- **SQLite 3** (`sqlite`)

Connection settings include `host`, `port`, `user`, `password`, `database`, and optional connection pool settings.
