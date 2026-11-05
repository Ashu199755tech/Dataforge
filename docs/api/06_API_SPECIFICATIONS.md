# DataFlow Enterprise — REST API Specifications

Base URL: `/api/v1`

## 1. Authentication & Security
- `POST /auth/login` -> `{ email, password }` => Returns JWT access token & refresh token.
- `GET /auth/me` -> Returns current user profile, workspace, and assigned permissions.
- `POST /auth/refresh` -> Refresh token rotation.

---

## 2. Workspaces & Projects
- `GET /workspaces` -> List workspaces accessible by current user.
- `POST /workspaces` -> Create workspace.
- `GET /workspaces/{id}/projects` -> List projects within workspace.
- `POST /projects` -> Create new project.

---

## 3. Connections & Schema Discovery
- `GET /projects/{project_id}/connections` -> List connections.
- `POST /connections` -> Create new connection (with encrypted credentials).
- `GET /connections/{id}` -> Get connection metadata (passwords masked).
- `PUT /connections/{id}` -> Update connection configuration.
- `DELETE /connections/{id}` -> Remove connection.
- `POST /connections/{id}/test` -> Perform live connectivity handshake.
- `GET /connections/{id}/schemas` -> Discover available database schemas.
- `GET /connections/{id}/tables?schema={schema}` -> Discover tables and views.
- `GET /connections/{id}/tables/{table_name}/columns?schema={schema}` -> Discover column types and nullability.
- `GET /connections/{id}/tables/{table_name}/preview?limit=50` -> Preview top sample rows safely.

---

## 4. Pipeline Authoring & Management
- `GET /projects/{project_id}/pipelines` -> List pipelines.
- `POST /pipelines` -> Create pipeline with visual graph definition.
- `GET /pipelines/{id}` -> Retrieve pipeline JSON graph, variables, and parameters.
- `PUT /pipelines/{id}` -> Update pipeline graph & auto-create version record.
- `DELETE /pipelines/{id}` -> Delete pipeline.
- `POST /pipelines/{id}/validate` -> Validate graph (detect cycles, disconnected nodes, unconfigured schemas).

---

## 5. Pipeline Execution & Monitoring
- `POST /pipelines/{id}/run` -> Trigger manual execution. Body can override parameters.
- `POST /runs/{run_id}/cancel` -> Request cancellation of running pipeline.
- `GET /projects/{project_id}/runs` -> Query execution runs with status, duration, and date filters.
- `GET /runs/{run_id}` -> Detailed status, summary metrics, and activity breakdown.
- `GET /runs/{run_id}/activities/{activity_id}/logs` -> Fetch streaming execution logs.
- `WS /ws/runs/{run_id}` -> WebSocket stream for live status transitions and row transfer counters.

---

## 6. Dashboard & Observability Metrics
- `GET /workspaces/{workspace_id}/dashboard/summary` ->
  Aggregated statistics:
  - Total pipelines, active pipelines
  - 24h / 7d success rate percentage
  - Total rows read and written
  - Active vs failed runs
  - Connection health statuses
  - Recent executions list

---

## 7. Data Quality & Governance
- `GET /projects/{project_id}/dq/rules` -> List configured DQ rules.
- `POST /projects/{project_id}/dq/rules` -> Create rule (Completeness, Uniqueness, Range, Regex).
- `GET /runs/{run_id}/dq/results` -> Get rule pass/fail breakdown and quarantined sample records.
- `GET /workspaces/{workspace_id}/audit-logs` -> Query immutable security audit log.
