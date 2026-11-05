# DataForge Enterprise — Security & Credential Management Guide

## 1. Security Architecture Principles

DataForge Enterprise follows strict zero-trust security guidelines to prevent credential exfiltration, privilege escalation, and accidental leakage.

### Non-Negotiable Security Rules:
1. **Zero Credential Exposure:** Secrets never appear in logs, API responses, or pipeline definitions.
2. **At-Rest Envelope Encryption:** All sensitive connection configurations are encrypted before being written to PostgreSQL.
3. **Decryption at Execution Boundary:** Secrets are decrypted exclusively within worker memory during active transfer execution and immediately discarded upon connection teardown.
4. **Cooperative Cancellation:** Transfers aborted by users terminate network connections without leaking background worker threads.

---

## 2. Cryptographic Implementation

### AES-256 Fernet Envelope Encryption
Connection credentials (e.g. AWS secret keys, Azure account keys, GCS service account JSONs) are encrypted using Python's `cryptography.fernet.Fernet` with AES-128-CBC and SHA-256 HMAC authentication.

The encryption master key is supplied via environment variable:
```bash
export DATAFORGE_SECRET_KEY="<base64-encoded-32-byte-key>"
```

### Recursive Sanitization (`mask_secret_dict`)
Before any connection model or configuration dictionary is returned via the REST API or serialized into audit logs, it passes through `mask_secret_dict`:
- Evaluates keys case-insensitively against sensitive tokens: `password`, `secret`, `token`, `account_key`, `sas_token`, `access_key`, `private_key`, `service_account`, etc.
- Deeply recurses into nested dictionaries.
- Replaces secret values with `********`.

---

## 3. Least-Privilege IAM Policies

### A. AWS S3 Minimum IAM Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DataForgeS3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name"
    },
    {
      "Sid": "DataForgeS3ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

### B. Azure Storage Minimum RBAC Roles
Assign either of the following Azure built-in roles:
- **Storage Blob Data Contributor:** Allows read, write, and delete of blobs/containers.
- **Storage Blob Data Reader:** For read-only ingestion sources.

### C. GCP Storage Minimum IAM Roles
- **roles/storage.objectAdmin:** Full control over objects in the bucket.
- **roles/storage.objectViewer:** For read-only ingestion sources.
