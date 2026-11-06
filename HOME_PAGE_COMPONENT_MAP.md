# DataForge Studio — Component Architecture & Integration Map

**Document:** `HOME_PAGE_COMPONENT_MAP.md`  
**Phase:** Phase 0 — Existing UI Audit & Component Mapping  
**Author:** Antigravity Pairing Assistant  
**Date:** 2026-11-06  
**Status:** Component Map Complete — Awaiting User Approval  

---

## 1. Component Hierarchy & Architectural Map

The diagram below outlines the structural composition of the proposed **DataForge Studio** application:

```
App.tsx
│
├── StudioLayout.tsx (Root Workspace Container)
│   │
│   ├── StudioNavbar.tsx (Top Navigation Bar - 52px)
│   │   ├── Brand & Workspace Section (Logo, Name, Workspace Selector, Environment Switcher)
│   │   ├── GlobalSearchInput.tsx (Triggers GlobalSearchModal.tsx on Click / Ctrl+K)
│   │   ├── GitIntegrationWidget.tsx (Branch Switcher, Change Pill, Push/Pull Controls)
│   │   ├── NotificationCenter.tsx (Alert Events & Deployment Bells)
│   │   └── UserProfileDropdown.tsx (Role, Settings, Sign-out)
│   │
│   └── Body Area (Flex Row)
│       │
│       ├── StudioSidebar.tsx (ADF-Inspired Left Collapsible Navigation Rail)
│       │   ├── Rail Collapse / Expand Toggle
│       │   ├── Group: Author (Pipelines, Data Flows, Datasets, Connections, Triggers, Parameters)
│       │   ├── Group: Monitor (Pipeline Runs, Trigger Runs, Runtimes, Execution Logs, Alerts)
│       │   ├── Group: Manage (Runtime Manager, Connection Management, Datasets, Git, CI/CD)
│       │   ├── Group: Governance (Lineage & Impact, Data Quality, Catalog, Audit)
│       │   ├── Group: Administration (Users & Roles, Security, Workspace Settings)
│       │   └── Version & Health Footer
│       │
│       └── Main Content Area (Dynamic Tab Viewport)
│           ├── DataForgeHomePage.tsx (Redesigned Home / Landing Workspace)
│           │   ├── Section 1: WelcomeHeader.tsx
│           │   ├── Section 2: QuickActionGrid.tsx (6 Action Cards)
│           │   ├── Section 3: WorkspaceMetricsOverview.tsx (KPI Cards)
│           │   ├── Section 4: RecentPipelineRunsTable.tsx (Real Backend Runs)
│           │   ├── Section 5: RecentResourcesLedger.tsx (Multi-Entity Recent Assets)
│           │   ├── Section 6: PipelineActivityChart.tsx (Recharts 24h / 7d / 30d Trend)
│           │   ├── Section 7: RuntimeFleetHealthCard.tsx (Live Agent Telemetry)
│           │   └── Section 8: GettingStartedChecklist.tsx (Automated Metadata Checklist)
│           │
│           ├── [Existing] PipelinesListPage.tsx
│           ├── [Existing] PipelineDesignerPage.tsx
│           ├── [Existing] DataFlowsListPage.tsx
│           ├── [Existing] ConnectionsPage.tsx
│           ├── [Existing] DatasetsPage.tsx
│           ├── [Existing] RuntimesPage.tsx
│           ├── [Existing] TriggersPage.tsx
│           ├── [Existing] LineagePage.tsx
│           ├── [Existing] DeploymentsPage.tsx
│           ├── [Existing] RunsMonitorPage.tsx
│           ├── [Existing] ObservabilityPage.tsx
│           └── [Existing] DataQualityPage.tsx
```

---

## 2. Navigation Routing & Module Map

The following map defines the exact binding between the redesigned sidebar items and the existing application views:

| Category | Navigation Item | Tab ID in Store | Target Page Component | Existing Route / Action |
| :--- | :--- | :--- | :--- | :--- |
| **Workspace** | Home / Overview | `'dashboard'` | `DataForgeHomePage.tsx` | Redesigned Studio Landing Workspace |
| **Author** | Pipelines | `'pipelines'` | `PipelinesListPage.tsx` | Pipeline catalog, search, and creation |
| **Author** | Pipeline Designer | `'designer'` | `PipelineDesignerPage.tsx` | Visual React Flow canvas & activity drawer |
| **Author** | Data Flows | `'dataflows'` | `DataFlowsListPage.tsx` | Visual ETL transformation builder |
| **Author** | Datasets | `'datasets'` | `DatasetsPage.tsx` | Reusable dataset catalog & schema editor |
| **Author** | Connections | `'connections'` | `ConnectionsPage.tsx` | Multi-cloud connectors (Storage & DBs) |
| **Author** | Triggers | `'triggers'` | `TriggersPage.tsx` | Schedules, Storage Events, Windows |
| **Monitor** | Pipeline Runs | `'runs'` | `RunsMonitorPage.tsx` | Run history, Gantt timeline, logs |
| **Monitor** | Runtime Monitoring| `'observability'`| `ObservabilityPage.tsx` | Fleet utilization, telemetry charts |
| **Monitor** | Execution Alerts | `'observability'`| `ObservabilityPage.tsx` | Multi-channel alert rules & events |
| **Manage** | Runtime Manager | `'runtimes'` | `RuntimesPage.tsx` | Self-hosted agent setup & status |
| **Manage** | Deployments & CI/CD| `'deployments'` | `DeploymentsPage.tsx` | Promotion gates, approvals, rollbacks |
| **Governance** | Data Lineage | `'lineage'` | `LineagePage.tsx` | React Flow lineage & impact analysis |
| **Governance** | Data Quality | `'dq'` | `DataQualityPage.tsx` | Data quality rules & test reports |

---

## 3. Data Source & API Integration Map for Home Page

Every section of the redesigned Home Page connects directly to actual live backend endpoints:

| Home Page Section | Component | Backend REST Endpoint | Ingested Data Fields |
| :--- | :--- | :--- | :--- |
| **Workspace Overview** | `WorkspaceMetricsOverview` | `GET /api/v1/dashboard/metrics` | `pipelines.total`, `pipelines.active`, `runs.total`, `runs.successful`, `runs.failed`, `runs.success_rate_percent`, `volume.total_rows_read`, `volume.total_rows_written`, `connections.total`, `connections.active`. |
| **Workspace Overview** | `WorkspaceMetricsOverview` | `GET /api/v1/datasets` | Total reusable datasets count and drift counts. |
| **Workspace Overview** | `WorkspaceMetricsOverview` | `GET /api/v1/triggers` | Active schedules and event listeners count. |
| **Workspace Overview** | `WorkspaceMetricsOverview` | `GET /api/v1/observability/fleet-health` | Online runtimes count and active worker tasks. |
| **Recent Runs Table** | `RecentPipelineRunsTable` | `GET /api/v1/runs?limit=8` | `id`, `pipeline_id`, `run_type`, `status`, `started_at`, `duration_seconds`, `total_rows_written`, `worker_info.runtime_name`. |
| **Pipeline Activity Chart**| `PipelineActivityChart` | `GET /api/v1/runs?limit=100` | Historical runs aggregated by timestamp for 24h, 7d, and 30d timeframes. |
| **Runtime Health Card** | `RuntimeFleetHealthCard` | `GET /api/v1/observability/fleet-health` | `runtimes` array: `name`, `runtime_type`, `status`, `cpu_usage_pct`, `memory_used_bytes`, `active_tasks`, `last_heartbeat_at`. |
| **Recent Resources Ledger**| `RecentResourcesLedger` | Aggregated from `pipelines`, `dataflows`, `datasets`, `connections`, `triggers` | `name`, `type`, `updated_at`, `created_at`. |
| **Getting Started Checklist**| `GettingStartedChecklist` | Evaluates live metadata arrays in store | `connections.length > 0`, `datasets.length > 0`, `pipelines.length > 0`, `runs.total > 0`, `triggers.length > 0`. |

---

## 4. Reusable Component Map (Design System)

| New Reusable Component | File Location | Purpose & Props |
| :--- | :--- | :--- |
| `StudioNavbar` | `src/components/layout/StudioNavbar.tsx` | Top header with environment switcher, search, and user controls. |
| `StudioSidebar` | `src/components/layout/StudioSidebar.tsx` | Collapsible left rail with ADF grouping, tooltips, and badges. |
| `MetricCard` | `src/components/common/MetricCard.tsx` | Standardized KPI display card with trend indicator and icon. |
| `QuickActionCard` | `src/components/common/QuickActionCard.tsx` | Action card with icon, title, description, and click-through navigation. |
| `GlobalSearchModal` | `src/components/common/GlobalSearchModal.tsx` | Search modal searching all resources with keyboard navigation. |
| `StatusBadge` | `src/components/common/StatusBadge.tsx` | Unified status pill (Succeeded, Failed, Running, Queued, Online, Offline). |
| `ResourceTable` | `src/components/common/ResourceTable.tsx` | Styled enterprise data table with sorting, empty states, and action buttons. |

---

## 5. Non-Destructive Integration Strategy

- **Zero Breaking Changes:** Existing components in `src/pages/` and `src/features/` remain unchanged.
- **Component Swap in App.tsx:** `App.tsx` replaces `<Navbar />` and `<Sidebar />` with `<StudioNavbar />` and `<StudioSidebar />`, rendering `<DataForgeHomePage />` as the default view.
- **State Store Continuity:** `useAppStore.ts` remains the single source of truth for workspace metadata, active project, and navigation state.
