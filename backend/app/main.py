import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.core.security import get_password_hash
from backend.app.api.auth import router as auth_router
from backend.app.api.workspaces import router as workspaces_router
from backend.app.api.connections import router as connections_router
from backend.app.api.pipelines import router as pipelines_router
from backend.app.api.runs import router as runs_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.triggers import router as triggers_router
from backend.app.api.activities import router as activities_router
from backend.app.api.callbacks import router as callbacks_router
from backend.app.api.dataflows import router as dataflows_router
from backend.app.api.expressions import router as expressions_router
from backend.app.api.data_quality import router as data_quality_router
from backend.app.api.alerts import router as alerts_router
from backend.app.api.environments import router as environments_router
from backend.app.api.secrets import router as secrets_router
from backend.app.api.audit import router as audit_router
from backend.app.api.scenarios import router as scenarios_router
from backend.app.api.runtimes import router as runtimes_router
from backend.app.api.datasets import router as datasets_router
from backend.app.api.git import router as git_router
from backend.app.api.deployments import router as deployments_router
from backend.app.api.lineage import router as lineage_router
from backend.app.models.runtime import IntegrationRuntime
from datetime import datetime, timezone
from backend.app.orchestration.scheduler import scheduler
from backend.app.core.migrations import run_migrations
from backend.app.orchestration.recovery import recover_orphaned_runs


def seed_initial_metadata():
    """Seeds default admin user, default workspace, and default project if not existing."""
    run_migrations()
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "admin@dataflow.enterprise").first()
        if not admin_user:
            admin_user = User(
                email="admin@dataflow.enterprise",
                full_name="Enterprise Administrator",
                hashed_password=get_password_hash("AdminPass123!"),
                role="Admin"
            )
            db.add(admin_user)
            db.commit()
            print("[INFO] Default admin user initialized (admin@dataflow.enterprise / AdminPass123!)")

        ws = db.query(Workspace).filter(Workspace.name == "Default Enterprise Workspace").first()
        if not ws:
            ws = Workspace(
                name="Default Enterprise Workspace",
                description="Primary workspace for enterprise ETL/ELT data integration workloads."
            )
            db.add(ws)
            db.commit()
            db.refresh(ws)
            print("[INFO] Default enterprise workspace created.")

        proj = db.query(Project).filter(Project.name == "Core Analytics & Ingestion").first()
        if not proj:
            proj = Project(
                workspace_id=ws.id,
                name="Core Analytics & Ingestion",
                description="Production data pipeline project."
            )
            db.add(proj)
            db.commit()
            db.refresh(proj)
            print("[INFO] Default core project created.")

        default_ir = db.query(IntegrationRuntime).filter(
            IntegrationRuntime.project_id == proj.id,
            IntegrationRuntime.name == "AutoResolveIntegrationRuntime"
        ).first()
        if not default_ir:
            default_ir = IntegrationRuntime(
                project_id=proj.id,
                name="AutoResolveIntegrationRuntime",
                description="Default managed multi-cloud serverless integration runtime.",
                runtime_type="Cloud",
                status="Online",
                concurrency_limit=10,
                last_heartbeat_at=datetime.now(timezone.utc)
            )
            db.add(default_ir)
            db.commit()
            print("[INFO] Default AutoResolveIntegrationRuntime created.")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_initial_metadata()
    db = SessionLocal()
    try:
        recover_orphaned_runs(db)
    except Exception as e:
        print(f"[WARN] Startup orphan recovery notice: {e}")
    finally:
        db.close()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Enterprise-grade independent Data Integration & Orchestration Platform",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(workspaces_router, prefix=settings.API_V1_STR)
app.include_router(connections_router, prefix=settings.API_V1_STR)
app.include_router(pipelines_router, prefix=settings.API_V1_STR)
app.include_router(runs_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(triggers_router, prefix=settings.API_V1_STR)
app.include_router(activities_router, prefix=settings.API_V1_STR)
app.include_router(callbacks_router, prefix=settings.API_V1_STR)
app.include_router(dataflows_router, prefix=settings.API_V1_STR)
app.include_router(expressions_router, prefix=settings.API_V1_STR)
app.include_router(data_quality_router, prefix=settings.API_V1_STR)
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(environments_router, prefix=settings.API_V1_STR)
app.include_router(secrets_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(scenarios_router, prefix=settings.API_V1_STR)
app.include_router(runtimes_router, prefix=settings.API_V1_STR)
app.include_router(datasets_router, prefix=settings.API_V1_STR)
app.include_router(git_router, prefix=settings.API_V1_STR)
app.include_router(deployments_router, prefix=settings.API_V1_STR)
app.include_router(lineage_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "1.0.0"}


# Mount static production frontend if built
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static-frontend")
