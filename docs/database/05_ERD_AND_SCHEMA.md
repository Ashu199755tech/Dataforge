# DataFlow Enterprise — Database Schema & ER Diagram

## 1. Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ WORKSPACE_MEMBERS : has
    WORKSPACES ||--o{ WORKSPACE_MEMBERS : contains
    WORKSPACES ||--o{ PROJECTS : contains
    PROJECTS ||--o{ ENVIRONMENTS : configures
    PROJECTS ||--o{ CONNECTIONS : registers
    PROJECTS ||--o{ PIPELINES : owns
    PIPELINES ||--o{ PIPELINE_VERSIONS : tracks
    PIPELINES ||--o{ TRIGGERS : activates
    PIPELINES ||--o{ PIPELINE_RUNS : executes
    PIPELINE_RUNS ||--o{ ACTIVITY_RUNS : details
    ACTIVITY_RUNS ||--o{ EXECUTION_LOGS : records
    PROJECTS ||--o{ DATA_QUALITY_RULES : defines
    PIPELINE_RUNS ||--o{ DATA_QUALITY_RESULTS : assesses
    WORKSPACES ||--o{ AUDIT_LOGS : tracks

    USERS {
        uuid id PK
        string email UK
        string full_name
        string hashed_password
        string role
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    WORKSPACES {
        uuid id PK
        string name UK
        string description
        timestamp created_at
    }

    PROJECTS {
        uuid id PK
        uuid workspace_id FK
        string name
        string description
        timestamp created_at
    }

    CONNECTIONS {
        uuid id PK
        uuid project_id FK
        string name
        string connector_type
        jsonb config_encrypted
        jsonb schema_cache
        string status
        timestamp last_tested_at
    }

    PIPELINES {
        uuid id PK
        uuid project_id FK
        string name
        string description
        string status
        jsonb definition_json
        int current_version
        timestamp created_at
        timestamp updated_at
    }

    PIPELINE_VERSIONS {
        uuid id PK
        uuid pipeline_id FK
        int version_number
        jsonb definition_json
        string changelog
        uuid created_by FK
        timestamp created_at
    }

    TRIGGERS {
        uuid id PK
        uuid pipeline_id FK
        string name
        string trigger_type
        string cron_expression
        boolean is_active
        jsonb parameters
        timestamp next_fire_time
    }

    PIPELINE_RUNS {
        uuid id PK
        uuid pipeline_id FK
        string run_type
        string status
        jsonb parameters
        timestamp started_at
        timestamp ended_at
        int duration_seconds
        int total_activities
        int succeeded_activities
        int failed_activities
        jsonb error_summary
    }

    ACTIVITY_RUNS {
        uuid id PK
        uuid pipeline_run_id FK
        string activity_id
        string activity_name
        string activity_type
        string status
        int retry_attempt
        bigint rows_read
        bigint rows_written
        bigint bytes_processed
        timestamp started_at
        timestamp ended_at
        jsonb metrics
        text error_message
    }

    EXECUTION_LOGS {
        bigserial id PK
        uuid activity_run_id FK
        string log_level
        text message
        timestamp timestamp
    }

    DATA_QUALITY_RULES {
        uuid id PK
        uuid project_id FK
        string rule_name
        string rule_type
        string target_table
        string target_column
        jsonb parameters
        float threshold_percent
    }

    DATA_QUALITY_RESULTS {
        uuid id PK
        uuid pipeline_run_id FK
        uuid rule_id FK
        string status
        bigint total_records_evaluated
        bigint failed_records_count
        float pass_percentage
        jsonb sample_failed_records
    }

    AUDIT_LOGS {
        bigserial id PK
        uuid workspace_id FK
        uuid user_id FK
        string action
        string entity_type
        string entity_id
        jsonb payload_diff
        timestamp created_at
    }
```

---

## 2. Table Specifications & Indexes

1. **`users`**:
   - `id`: UUID (Primary Key, default uuid_generate_v4())
   - `email`: VARCHAR(255) UNIQUE NOT NULL
   - `hashed_password`: VARCHAR(255) NOT NULL
   - `role`: VARCHAR(50) NOT NULL (Admin, Engineer, Operator, Viewer)
   - Index on `email`.

2. **`connections`**:
   - Stores connection configurations. Sensitive attributes (passwords, tokens) stored encrypted in `config_encrypted` column using Fernet / AES-GCM.
   - Index on `(project_id, name)` unique per project.

3. **`pipelines`**:
   - `definition_json`: JSONB column containing nodes, edges, activity configs, and parameter schemas.
   - GIN index on `definition_json` for JSON querying.

4. **`pipeline_runs` & `activity_runs`**:
   - High write throughput. Indexes on `(pipeline_id, started_at DESC)`, `status`, and `pipeline_run_id`.
   - `rows_read`, `rows_written`, `bytes_processed` for operational reporting.
