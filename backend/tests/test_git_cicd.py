import pytest
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.dataset import Dataset
from backend.app.models.trigger import Trigger
from backend.app.models.git import GitRepository
from backend.app.models.deployment import Deployment
from backend.app.models.security import Environment
from backend.app.schemas.git import (
    GitRepositoryConfig,
    GitBranchSwitchRequest,
    GitCommitRequest
)
from backend.app.schemas.deployment import (
    DeploymentCreateRequest,
    DeploymentDryRunRequest,
    DeploymentApprovalRequest
)
from backend.app.services.git_serializer import GitAssetSerializer
from backend.app.services.git_service import GitService
from backend.app.services.cicd_service import CiCdService
from backend.app.main import app
from backend.app.core.security import encrypt_secret


@pytest.fixture(scope="module")
def db_session():
    """Provides test database session with clean metadata."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_setup(db_session: Session):
    """Initializes workspace, project, user, environment, and sample assets."""
    user = db_session.query(User).filter(User.email == "git_admin@dataforge.test").first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email="git_admin@dataforge.test",
            hashed_password="testpassword",
            full_name="Git CI/CD Admin",
            is_active=True
        )
        db_session.add(user)

    ws = db_session.query(Workspace).first()
    if not ws:
        ws = Workspace(id=str(uuid.uuid4()), name="Git Workspace", owner_id=user.id)
        db_session.add(ws)

    proj = db_session.query(Project).filter(Project.name == "Git CI/CD Project").first()
    if not proj:
        proj = Project(id=str(uuid.uuid4()), name="Git CI/CD Project", workspace_id=ws.id)
        db_session.add(proj)

    # Environments
    env_dev = db_session.query(Environment).filter(Environment.name == "Dev").first()
    if not env_dev:
        env_dev = Environment(id=str(uuid.uuid4()), name="Dev", variables={"storage_tier": "hot"})
        db_session.add(env_dev)

    env_prod = db_session.query(Environment).filter(Environment.name == "Prod").first()
    if not env_prod:
        env_prod = Environment(id=str(uuid.uuid4()), name="Prod", variables={"storage_tier": "archive"})
        db_session.add(env_prod)

    # Connection with sensitive credentials to test masking
    conn = Connection(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Production_DB_Conn",
        connector_type="postgres",
        config_encrypted=encrypt_secret({
            "host": "db.corp.internal",
            "port": 5432,
            "database": "enterprise_dw",
            "username": "dw_admin",
            "password": "SuperSecretPassword123!"  # MUST be masked in Git export
        })
    )
    db_session.add(conn)

    # Sample Pipeline
    pipe = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Sales_ETL_Pipeline",
        definition_json={
            "activities": [
                {
                    "id": "act_1",
                    "name": "CopySalesData",
                    "type": "CopyData",
                    "depends_on": []
                }
            ],
            "parameters": {"batch_id": "DEFAULT_100"}
        }
    )
    db_session.add(pipe)

    # Sample Dataset
    dataset = Dataset(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        connection_id=conn.id,
        name="Sales_Transactions_DS",
        dataset_type="RelationalTable",
        location_config={"table": "sales_transactions"},
        schema_definition=[
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "amount", "type": "FLOAT", "nullable": False}
        ]
    )
    db_session.add(dataset)

    # Sample Trigger
    trigger = Trigger(
        id=str(uuid.uuid4()),
        name="Daily_Midnight_Trigger",
        trigger_type="schedule",
        pipeline_id=pipe.id,
        cron_expression="0 0 * * *",
        is_active=True
    )
    db_session.add(trigger)
    db_session.commit()

    return {
        "user": user,
        "project": proj,
        "conn": conn,
        "pipe": pipe,
        "dataset": dataset,
        "trigger": trigger,
        "env_dev": env_dev,
        "env_prod": env_prod
    }


def test_canonical_json_serializer_determinism_and_secret_masking(db_session: Session, test_setup):
    """Verifies deterministic sorted JSON output, SHA-256 checksums, and credential stripping."""
    conn = test_setup["conn"]
    pipe = test_setup["pipe"]
    dataset = test_setup["dataset"]
    trigger = test_setup["trigger"]

    # 1. Connection Serialization - verify password is NOT leaked in Git output
    conn_dict = GitAssetSerializer.serialize_connection(conn)
    assert conn_dict["asset_type"] == "Connection"
    assert "password" in conn_dict["config"]
    # Password must be replaced with vault reference, not plain text!
    assert conn_dict["config"]["password"] != "SuperSecretPassword123!"
    assert "${vault:" in conn_dict["config"]["password"]

    # 2. Pipeline Serialization & Checksum determinism
    pipe_dict = GitAssetSerializer.serialize_pipeline(pipe)
    assert pipe_dict["asset_type"] == "Pipeline"
    assert "checksum" in pipe_dict

    # Serializing twice must produce byte-identical canonical JSON and identical SHA-256
    json1 = GitAssetSerializer.to_canonical_json(pipe_dict)
    json2 = GitAssetSerializer.to_canonical_json(pipe_dict)
    assert json1 == json2
    assert GitAssetSerializer.compute_checksum(json1) == GitAssetSerializer.compute_checksum(json2)

    # 3. Workspace Tree Export
    tree = GitAssetSerializer.export_workspace_tree(db_session, test_setup["project"].id)
    assert len(tree) >= 4
    assert any("pipelines/sales_etl_pipeline.json" in k for k in tree.keys())
    assert any("datasets/sales_transactions_ds.json" in k for k in tree.keys())
    assert any("connections/production_db_conn.json" in k for k in tree.keys())


def test_git_repository_connection_and_branch_operations(db_session: Session, test_setup):
    """Verifies connecting a project to GitHub/GitLab, token encryption, and branch management."""
    project = test_setup["project"]
    user = test_setup["user"]

    cfg = GitRepositoryConfig(
        repo_url="https://github.com/enterprise-org/dataforge-pipelines.git",
        provider="github",
        default_branch="main",
        current_branch="main",
        root_folder="/dataforge",
        auth_type="pat",
        token="ghp_SecretGitHubPersonalAccessToken999"
    )

    repo = GitService.connect_repository(db_session, project.id, cfg, user)
    assert repo.id is not None
    assert repo.is_connected is True
    assert repo.sync_status == "synced"
    # Token must be Fernet-encrypted
    assert repo.token_encrypted != "ghp_SecretGitHubPersonalAccessToken999"

    # Branch list
    branches = GitService.get_branches(db_session, project.id)
    assert len(branches) >= 1
    assert any(b.name == "main" and b.is_current for b in branches)

    # Create new feature branch
    switch_req = GitBranchSwitchRequest(
        branch_name="feature/cloud-ingestion",
        create_new=True,
        source_branch="main"
    )
    repo = GitService.switch_branch(db_session, project.id, switch_req, user)
    assert repo.current_branch == "feature/cloud-ingestion"

    updated_branches = GitService.get_branches(db_session, project.id)
    assert any(b.name == "feature/cloud-ingestion" and b.is_current for b in updated_branches)


def test_git_diff_calculation_and_commit_push(db_session: Session, test_setup):
    """Verifies working diff calculation, commit & push, and post-commit zero diff."""
    project = test_setup["project"]
    user = test_setup["user"]

    # 1. Before initial commit on this branch, all workspace files show as "added"
    diff_res = GitService.compute_diff(db_session, project.id)
    assert diff_res.total_changes > 0
    assert any(f.status == "added" for f in diff_res.files)

    # 2. Commit and push changes
    commit_res = GitService.commit_and_push(
        db_session,
        project.id,
        GitCommitRequest(message="Initial commit of enterprise data assets", branch="feature/cloud-ingestion"),
        user
    )
    assert "commit_hash" in commit_res
    assert commit_res["files_committed"] > 0

    # 3. After commit, diff should be 0 changes (clean working tree)
    clean_diff = GitService.compute_diff(db_session, project.id)
    assert clean_diff.total_changes == 0

    # 4. Pull & sync verification
    pull_res = GitService.pull_and_sync(db_session, project.id, "feature/cloud-ingestion", user)
    assert pull_res["status"] == "synced"


def test_cicd_dry_run_prevalidation(db_session: Session, test_setup):
    """Verifies pre-validation comparison report, DAG validation, and environment warnings."""
    project = test_setup["project"]
    pipe = test_setup["pipe"]
    dataset = test_setup["dataset"]
    trigger = test_setup["trigger"]

    dry_req = DeploymentDryRunRequest(
        source_environment="Dev",
        target_environment="Prod",
        pipeline_ids=[pipe.id],
        dataset_ids=[dataset.id],
        trigger_ids=[trigger.id],
        parameter_substitutions={"batch_id": "PROD_BATCH_2026"}
    )

    report = CiCdService.create_dry_run(db_session, project.id, dry_req)
    assert report.can_deploy is True
    assert any("approval gate" in w.lower() for w in report.warnings)
    assert len(report.asset_diffs) == 3
    assert report.diff_summary["added"] + report.diff_summary["modified"] >= 1


def test_cicd_deployment_approval_and_execution_lifecycle(db_session: Session, test_setup):
    """Verifies release creation, approval gate (reject & approve), promotion, and version snapshotting."""
    project = test_setup["project"]
    user = test_setup["user"]
    pipe = test_setup["pipe"]

    initial_pipe_ver = pipe.current_version

    # 1. Create Deployment release targeting Prod -> Requires approval
    dep_req = DeploymentCreateRequest(
        source_environment="Dev",
        target_environment="Prod",
        bundle_version="v1.0.0",
        pipeline_ids=[pipe.id],
        parameter_substitutions={"batch_id": "RELEASE_PROD_100"},
        notes="Q4 Production Pipeline Promotion"
    )
    dep = CiCdService.create_deployment(db_session, project.id, dep_req, user)
    assert dep.id is not None
    assert dep.status == "PendingApproval"

    # 2. Test Rejection
    dep = CiCdService.reject_deployment(db_session, dep.id, user, comment="Changes need additional test runs")
    assert dep.status == "Rejected"

    # 3. Create second deployment and approve
    dep2 = CiCdService.create_deployment(db_session, project.id, dep_req, user)
    dep2 = CiCdService.approve_deployment(db_session, dep2.id, user, comment="Approved after QA verification")
    assert dep2.status == "Approved"
    assert dep2.approved_by_id == user.id

    # 4. Execute deployment
    dep2 = CiCdService.execute_deployment(db_session, dep2.id, user)
    assert dep2.status == "Deployed"
    assert dep2.deployed_at is not None

    # Pipeline version must be incremented and parameter substituted
    db_session.refresh(pipe)
    assert pipe.current_version == initial_pipe_ver + 1
    assert pipe.definition_json["parameters"]["batch_id"] == "RELEASE_PROD_100"

    # 5. Rollback deployment
    dep2 = CiCdService.rollback_deployment(db_session, dep2.id, user)
    assert dep2.status == "RolledBack"


def test_git_and_deployment_rest_api_endpoints(test_setup):
    """Verifies FastAPI REST API endpoints for Git management and CI/CD releases."""
    client = TestClient(app)
    project = test_setup["project"]
    pipe = test_setup["pipe"]

    # 1. Connect Git repository endpoint
    res = client.post(f"/api/v1/git/connect?project_id={project.id}", json={
        "repo_url": "https://github.com/enterprise/pipelines-repo.git",
        "provider": "github",
        "default_branch": "main",
        "current_branch": "main"
    })
    assert res.status_code == 200, res.text
    assert res.json()["provider"] == "github"

    # 2. Get Git config endpoint
    res = client.get(f"/api/v1/git/config?project_id={project.id}")
    assert res.status_code == 200
    assert res.json()["repo_url"] == "https://github.com/enterprise/pipelines-repo.git"

    # 3. Get branches endpoint
    res = client.get(f"/api/v1/git/branches?project_id={project.id}")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 4. Get diff endpoint
    res = client.get(f"/api/v1/git/diff?project_id={project.id}")
    assert res.status_code == 200
    assert "total_changes" in res.json()

    # 5. Commit endpoint
    res = client.post(f"/api/v1/git/commit?project_id={project.id}", json={
        "message": "REST API Automated Asset Sync",
        "author_name": "QA Agent"
    })
    assert res.status_code == 200
    assert "commit_hash" in res.json()

    # 6. CI/CD Dry-Run Endpoint
    res = client.post(f"/api/v1/deployments/dry-run?project_id={project.id}", json={
        "source_environment": "Dev",
        "target_environment": "Test",
        "pipeline_ids": [pipe.id],
        "parameter_substitutions": {"env": "test"}
    })
    assert res.status_code == 200
    assert "diff_summary" in res.json()

    # 7. Create Deployment Endpoint
    res = client.post(f"/api/v1/deployments?project_id={project.id}", json={
        "source_environment": "Dev",
        "target_environment": "Test",
        "bundle_version": "v1.1.0",
        "pipeline_ids": [pipe.id]
    })
    assert res.status_code == 200
    dep_id = res.json()["id"]

    # 8. Execute Deployment Endpoint
    res = client.post(f"/api/v1/deployments/{dep_id}/execute")
    assert res.status_code == 200
    assert res.json()["status"] == "Deployed"

    # 9. GitHub Actions Workflow Template Endpoint
    res = client.get("/api/v1/deployments/template/github-actions?project_name=DataForge-Core")
    assert res.status_code == 200
    assert "name: DataForge CI/CD Release" in res.text
