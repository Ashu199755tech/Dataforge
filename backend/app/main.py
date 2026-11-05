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
from backend.app.orchestration.scheduler import scheduler


def seed_initial_metadata():
    """Seeds default admin user, default workspace, and default project if not existing."""
    Base.metadata.create_all(bind=engine)
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
            print("[INFO] Default core project created.")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_initial_metadata()
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


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "1.0.0"}


# Mount static production frontend if built
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static-frontend")
