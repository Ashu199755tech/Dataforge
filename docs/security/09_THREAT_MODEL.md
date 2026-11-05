# DataFlow Enterprise — Security Threat Model (STRIDE)

## 1. Overview
As an enterprise data integration platform, DataFlow Enterprise processes sensitive connection credentials (database passwords, tokens, private keys) and orchestrates arbitrary data flows. A security-first architecture is mandatory from day one.

---

## 2. STRIDE Threat Analysis & Mitigations

### 2.1 Spoofing (Identity & Authentication)
- **Threat**: Unauthorized actors impersonating users or API clients to trigger pipelines or modify credentials.
- **Mitigation**:
  - JWT tokens with short lifespan (15 mins) and cryptographically secure HMAC-SHA256 signatures.
  - Refresh tokens stored in HTTP-only, Secure, SameSite cookies.
  - Standard OIDC / OAuth2 integration ready for enterprise IdPs (Keycloak, Okta, Azure AD).

### 2.2 Tampering (Data & Pipeline Modification)
- **Threat**: Malicious actor altering pipeline definitions or SQL scripts to exfiltrate or corrupt enterprise data.
- **Mitigation**:
  - Immutable version history for every pipeline modification (`pipeline_versions` table).
  - Parameterized queries across all connector drivers preventing SQL Injection.
  - Strict input schema validation on all incoming API payloads using Pydantic.

### 2.3 Repudiation (Auditability)
- **Threat**: An operator executes or deletes a sensitive pipeline and denies doing so.
- **Mitigation**:
  - Append-only `audit_logs` table capturing `user_id`, `action`, `resource_type`, `resource_id`, IP address, and payload difference.
  - Tamper-evident execution logs archived alongside pipeline run metadata.

### 2.4 Information Disclosure (Credential & Data Leakage)
- **Threat**: Plaintext database passwords or API keys leaking via REST APIs, logs, or error stack traces.
- **Mitigation**:
  - Symmetric AES-256-GCM / Fernet encryption of all connection secret fields before storage in PostgreSQL.
  - Explicit masking (`"***"`) of sensitive keys in all REST API response schemas.
  - Dedicated log sanitizer filtering passwords, authorization headers, and token strings.

### 2.5 Denial of Service (Worker Exhaustion & Resource Starvation)
- **Threat**: A massive dataset or infinite loop activity exhausts API server memory or worker thread pools.
- **Mitigation**:
  - Streamed/chunked generator reads from source connectors with strict batch caps (default 5,000 rows).
  - Worker timeout enforcement per activity (configurable `timeout_seconds`, default 3600s).
  - Process isolation between FastAPI API server and execution workers.

### 2.6 Elevation of Privilege (RBAC)
- **Threat**: A read-only user triggers a production pipeline or modifies production connection endpoints.
- **Mitigation**:
  - Granular RBAC permissions: `Admin`, `DataEngineer`, `Operator`, `Viewer`.
  - Endpoint-level FastAPI dependency injection verifying permissions per workspace and project.
