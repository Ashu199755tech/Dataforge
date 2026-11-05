# DataFlow Enterprise — Repository Structure

```
dataflow-enterprise/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entrypoint & middleware
│   │   ├── core/                    # App configuration, security, database session
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── models/                  # SQLAlchemy ORM Models
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── connection.py
│   │   │   ├── pipeline.py
│   │   │   ├── execution.py
│   │   │   └── data_quality.py
│   │   ├── schemas/                 # Pydantic Request/Response models
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── connection.py
│   │   │   ├── pipeline.py
│   │   │   └── execution.py
│   │   ├── connectors/              # Pluggable Connector SDK
│   │   │   ├── base.py
│   │   │   ├── postgres.py
│   │   │   ├── mysql.py
│   │   │   ├── sqlite.py
│   │   │   └── factory.py
│   │   ├── activities/              # Pluggable Pipeline Activity Executors
│   │   │   ├── base.py
│   │   │   ├── copy_data.py
│   │   │   ├── sql_script.py
│   │   │   ├── dq_check.py
│   │   │   └── factory.py
│   │   ├── execution/               # Execution Engine & Worker
│   │   │   ├── dag_engine.py
│   │   │   ├── runner.py
│   │   │   └── event_bus.py
│   │   ├── api/                     # REST API Routes
│   │   │   ├── auth.py
│   │   │   ├── workspaces.py
│   │   │   ├── connections.py
│   │   │   ├── pipelines.py
│   │   │   ├── runs.py
│   │   │   ├── dashboard.py
│   │   │   └── websockets.py
│   │   └── services/                # Business Logic Services
│   ├── migrations/                  # Alembic DB Migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/                       # Automated Pytest Suite
│   │   ├── test_auth.py
│   │   ├── test_connectors.py
│   │   ├── test_dag_engine.py
│   │   ├── test_copy_data.py
│   │   └── test_end_to_end.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── public/                      # Static assets & brand icons
│   ├── src/
│   │   ├── api/                     # API client & endpoints (Axios / TanStack Query)
│   │   ├── components/              # Shared UI design system
│   │   │   ├── layout/
│   │   │   ├── common/
│   │   │   └── forms/
│   │   ├── pages/                   # Main application views
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── PipelinesListPage.tsx
│   │   │   ├── ConnectionsPage.tsx
│   │   │   ├── RunsMonitorPage.tsx
│   │   │   └── DataQualityPage.tsx
│   │   ├── features/
│   │   │   ├── pipeline-designer/   # React Flow visual canvas & activity nodes
│   │   │   │   ├── PipelineCanvas.tsx
│   │   │   │   ├── ActivityToolbox.tsx
│   │   │   │   ├── ActivityConfigDrawer.tsx
│   │   │   │   ├── custom-nodes/
│   │   │   │   └── hooks/
│   │   │   ├── connections/         # Connection modals & schema browser
│   │   │   └── monitoring/          # Live execution logs & Gantt timeline
│   │   ├── store/                   # Zustand state stores
│   │   ├── types/                   # TypeScript interfaces
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css                # Tailwind directives
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── infrastructure/
│   ├── docker/
│   │   ├── init-scripts/
│   │   └── supervisord.conf
│   └── docker-compose.yml
│
├── docs/
│   ├── architecture/
│   ├── database/
│   ├── api/
│   ├── security/
│   └── testing/
│
├── scripts/
│   ├── init_local_dbs.sh            # Initializes PostgreSQL & MySQL data dirs
│   ├── seed_demo_data.py            # Generates realistic demo source data
│   └── run_mvp_verification.py      # Automated end-to-end milestone tester
├── README.md
└── LICENSE
```
