import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.execution import PipelineRun
from backend.app.models.security import Environment, SecretVaultEntry
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.security.vault import secret_vault
from backend.app.orchestration.recovery import enforce_concurrency_and_idempotency, recover_orphaned_runs


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def security_setup():
    db: Session = SessionLocal()
    # Users with different RBAC roles
    users = {
        "Admin": "admin_harden@enterprise.io",
        "Contributor": "contributor_harden@enterprise.io",
        "Operator": "operator_harden@enterprise.io",
        "Viewer": "viewer_harden@enterprise.io"
    }
    tokens = {}

    for role, email in users.items():
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                full_name=f"{role} User",
                hashed_password=get_password_hash("SecurePass123!"),
                role=role
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        tokens[role] = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})

    # Workspace & Project
    ws = db.query(Workspace).filter(Workspace.name == "Hardened Workspace").first()
    if not ws:
        ws = Workspace(name="Hardened Workspace", description="Workspace for hardening verification")
        db.add(ws)
        db.commit()
        db.refresh(ws)

    project = db.query(Project).filter(Project.name == "Hardened Project").first()
    if not project:
        project = Project(name="Hardened Project", workspace_id=ws.id)
        db.add(project)
        db.commit()
        db.refresh(project)

    project_id = project.id
    workspace_id = ws.id
    db.close()

    headers = {role: {"Authorization": f"Bearer {token}"} for role, token in tokens.items()}
    return {
        "headers": headers,
        "project_id": project_id,
        "workspace_id": workspace_id
    }


def test_rbac_access_control_rules(client, security_setup):
    """Verifies RBAC enforcement: Viewers cannot mutate, Admins have full access."""
    headers = security_setup["headers"]
    project_id = security_setup["project_id"]

    # 1. Viewer attempts to create pipeline -> 403 Forbidden
    viewer_res = client.post(
        "/api/v1/pipelines",
        headers=headers["Viewer"],
        json={
            "name": "Viewer Unauthorized Pipeline",
            "project_id": project_id,
            "definition_json": {"activities": []}
        }
    )
    assert viewer_res.status_code == 403

    # 2. Contributor creates pipeline -> 201 Created
    contrib_res = client.post(
        "/api/v1/pipelines",
        headers=headers["Contributor"],
        json={
            "name": "Contributor Authorized Pipeline",
            "project_id": project_id,
            "concurrency_limit": 3,
            "definition_json": {
                "activities": [
                    {
                        "id": "act_test",
                        "name": "Test Activity",
                        "type": "SetVariable",
                        "config": {"variable_name": "x", "value": 10}
                    }
                ]
            }
        }
    )
    assert contrib_res.status_code == 201
    pipe_data = contrib_res.json()
    pipe_id = pipe_data["id"]

    # 3. Viewer attempts to delete pipeline -> 403 Forbidden
    del_viewer = client.delete(f"/api/v1/pipelines/{pipe_id}", headers=headers["Viewer"])
    assert del_viewer.status_code == 403

    # 4. Admin deletes pipeline -> 200 OK
    del_admin = client.delete(f"/api/v1/pipelines/{pipe_id}", headers=headers["Admin"])
    assert del_admin.status_code == 200


def test_secrets_vault_encryption_and_rotation(client, security_setup):
    """Verifies AES-256 encryption at rest, masked listings, and non-disruptive key rotation."""
    headers = security_setup["headers"]

    # 1. Store secret via API
    secret_name = "DW_WAREHOUSE_PROD_KEY"
    raw_secret_value = "SuperSecretDbPassword#2026!"

    store_res = client.post(
        "/api/v1/secrets",
        headers=headers["Contributor"],
        json={
            "name": secret_name,
            "value": raw_secret_value,
            "description": "Production data warehouse connection password"
        }
    )
    assert store_res.status_code == 201
    sec_data = store_res.json()
    assert sec_data["is_masked"] is True
    assert "value" not in sec_data

    # 2. List secrets: value is NEVER exposed
    list_res = client.get("/api/v1/secrets", headers=headers["Contributor"])
    assert list_res.status_code == 200
    secrets_list = list_res.json()
    target = next((s for s in secrets_list if s["name"] == secret_name), None)
    assert target is not None
    assert target["vault_provider"] == "AES-256-Fernet"
    assert "value" not in target

    # 3. Internal backend decryption matches original raw value
    db: Session = SessionLocal()
    decrypted_val = secret_vault.get_secret(secret_name, db)
    assert decrypted_val == raw_secret_value
    db.close()

    # 4. Rotate encryption key
    new_key = "EnterpriseRotationKeySecure2026!"
    rot_res = client.post(
        "/api/v1/secrets/rotate",
        headers=headers["Admin"],
        json={"new_encryption_key": new_key}
    )
    assert rot_res.status_code == 200
    assert rot_res.json()["rotated_entries"] >= 1

    # 5. Verify secret is still decrypted correctly under new key
    db = SessionLocal()
    decrypted_after_rot = secret_vault.get_secret(secret_name, db)
    assert decrypted_after_rot == raw_secret_value

    # 6. Delete secret
    del_res = client.delete(f"/api/v1/secrets/{secret_name}", headers=headers["Admin"])
    assert del_res.status_code == 200
    db.close()


def test_environment_management_and_promotion(client, security_setup):
    """Verifies Dev -> Test -> Prod pipeline promotion with parameter overrides and version snapshots."""
    headers = security_setup["headers"]
    project_id = security_setup["project_id"]

    # 1. List default environments
    envs_res = client.get("/api/v1/environments", headers=headers["Viewer"])
    assert envs_res.status_code == 200
    env_names = [e["name"] for e in envs_res.json()]
    assert "Dev" in env_names
    assert "Prod" in env_names

    # 2. Create Dev Pipeline
    create_res = client.post(
        "/api/v1/pipelines",
        headers=headers["Contributor"],
        json={
            "name": "Sales Ingestion Pipeline",
            "project_id": project_id,
            "definition_json": {
                "parameters": {"batch_size": 100, "target_env": "dev"},
                "activities": [
                    {
                        "id": "act_wait",
                        "name": "Wait Step",
                        "type": "Wait",
                        "config": {"wait_time_in_seconds": 1}
                    }
                ]
            }
        }
    )
    assert create_res.status_code == 201
    pipe_id = create_res.json()["id"]

    # 3. Promote pipeline to Prod with parameter overrides
    promote_res = client.post(
        f"/api/v1/pipelines/{pipe_id}/promote",
        headers=headers["Contributor"],
        json={
            "target_environment": "Prod",
            "parameter_overrides": {"batch_size": 10000, "target_env": "prod"}
        }
    )
    assert promote_res.status_code == 200
    promoted = promote_res.json()
    assert promoted["status"] == "Published"
    assert promoted["current_version"] == 2
    assert promoted["definition_json"]["parameters"]["batch_size"] == 10000
    assert promoted["definition_json"]["parameters"]["target_env"] == "prod"


def test_pipeline_versioning_and_rollback(client, security_setup):
    """Verifies immutable version history and atomic rollback to historical snapshots."""
    headers = security_setup["headers"]
    project_id = security_setup["project_id"]

    # 1. Create pipeline at Version 1
    create_res = client.post(
        "/api/v1/pipelines",
        headers=headers["Contributor"],
        json={
            "name": "Rollback Test Pipeline",
            "project_id": project_id,
            "definition_json": {
                "activities": [
                    {
                        "id": "act_v1",
                        "name": "Version 1 Step",
                        "type": "SetVariable",
                        "config": {"variable_name": "v", "value": "1.0"}
                    }
                ]
            }
        }
    )
    assert create_res.status_code == 201
    pipe_id = create_res.json()["id"]

    # 2. Update to Version 2
    update_res = client.put(
        f"/api/v1/pipelines/{pipe_id}",
        headers=headers["Contributor"],
        json={
            "definition_json": {
                "activities": [
                    {
                        "id": "act_v2",
                        "name": "Version 2 Step",
                        "type": "SetVariable",
                        "config": {"variable_name": "v", "value": "2.0"}
                    }
                ]
            }
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["current_version"] == 2

    # 3. Check version ledger
    vers_res = client.get(f"/api/v1/pipelines/{pipe_id}/versions", headers=headers["Viewer"])
    assert vers_res.status_code == 200
    versions = vers_res.json()
    assert len(versions) >= 2
    assert versions[0]["version_number"] == 2

    # 4. Rollback to Version 1
    rollback_res = client.post(
        f"/api/v1/pipelines/{pipe_id}/rollback",
        headers=headers["Contributor"],
        json={"version_number": 1}
    )
    assert rollback_res.status_code == 200
    rolled_back = rollback_res.json()
    assert rolled_back["current_version"] == 3
    # Definition restored to act_v1
    assert rolled_back["definition_json"]["activities"][0]["id"] == "act_v1"


def test_git_declarative_export_and_import(client, security_setup):
    """Verifies vendor-agnostic Git export with checksums and import into new pipelines."""
    headers = security_setup["headers"]
    project_id = security_setup["project_id"]

    # 1. Create source pipeline
    create_res = client.post(
        "/api/v1/pipelines",
        headers=headers["Contributor"],
        json={
            "name": "Git Export Pipeline",
            "project_id": project_id,
            "concurrency_limit": 2,
            "definition_json": {
                "activities": [
                    {
                        "id": "step_one",
                        "name": "Step One",
                        "type": "SetVariable",
                        "config": {"variable_name": "git_tag", "value": "v1.0.0"}
                    }
                ]
            }
        }
    )
    pipe_id = create_res.json()["id"]

    # 2. Export declarative Git spec
    export_res = client.get(f"/api/v1/pipelines/{pipe_id}/export-git", headers=headers["Viewer"])
    assert export_res.status_code == 200
    git_spec = export_res.json()
    assert "$schema" in git_spec
    assert git_spec["name"] == "Git Export Pipeline"
    assert "checksum" in git_spec

    # 3. Import as a newly named pipeline from Git payload
    git_spec["name"] = "Imported From Git Pipeline"
    import_res = client.post(
        "/api/v1/pipelines/import-git",
        headers=headers["Contributor"],
        json={"project_id": project_id, "spec": git_spec}
    )
    assert import_res.status_code == 201
    imported_pipe = import_res.json()
    assert imported_pipe["name"] == "Imported From Git Pipeline"
    assert imported_pipe["concurrency_limit"] == 2
    assert imported_pipe["definition_json"]["activities"][0]["id"] == "step_one"


def test_concurrency_control_and_idempotency(client, security_setup):
    """Verifies concurrency saturation guards (HTTP 429) and deduplication of idempotent triggers."""
    headers = security_setup["headers"]
    project_id = security_setup["project_id"]
    db: Session = SessionLocal()

    # 1. Create pipeline with concurrency_limit = 1
    pipe = Pipeline(
        project_id=project_id,
        name="Singleton Concurrent Pipeline",
        concurrency_limit=1,
        definition_json={"activities": []}
    )
    db.add(pipe)
    db.commit()
    db.refresh(pipe)

    # 2. Simulate an active run in 'Running' status
    active_run = PipelineRun(
        pipeline_id=pipe.id,
        run_type="Manual",
        status="Running",
        idempotency_key="idemp_key_1001",
        started_at=datetime.now(timezone.utc)
    )
    db.add(active_run)
    db.commit()
    db.refresh(active_run)

    # 3. Trigger run with duplicate idempotency key -> returns existing run (Idempotency)
    idemp_res = client.post(
        f"/api/v1/pipelines/{pipe.id}/run",
        headers=headers["Operator"],
        json={"idempotency_key": "idemp_key_1001"}
    )
    assert idemp_res.status_code == 200
    assert idemp_res.json()["id"] == active_run.id

    # 4. Trigger run with different idempotency key -> saturated concurrency limit (HTTP 429)
    blocked_res = client.post(
        f"/api/v1/pipelines/{pipe.id}/run",
        headers=headers["Operator"],
        json={"idempotency_key": "idemp_key_1002"}
    )
    assert blocked_res.status_code == 429
    assert "concurrency limit reached" in blocked_res.json()["detail"].lower()

    # Cleanup active run
    active_run.status = "Succeeded"
    db.commit()
    db.close()


def test_worker_recovery_of_orphaned_runs(client, security_setup):
    """Verifies that running tasks with terminated workers are automatically transitioned to Failed."""
    db: Session = SessionLocal()
    project_id = security_setup["project_id"]

    pipe = Pipeline(
        project_id=project_id,
        name="Recovery Test Pipeline",
        definition_json={"activities": []}
    )
    db.add(pipe)
    db.commit()
    db.refresh(pipe)

    # Simulate an orphaned run with an invalid/dead worker PID (e.g. PID 99999999)
    orphaned_run = PipelineRun(
        pipeline_id=pipe.id,
        run_type="Manual",
        status="Running",
        worker_info={"pid": 99999999, "hostname": "local"},
        started_at=datetime.now(timezone.utc)
    )
    db.add(orphaned_run)
    db.commit()
    db.refresh(orphaned_run)

    # Trigger recovery routine
    recovered = recover_orphaned_runs(db)
    assert recovered >= 1

    db.refresh(orphaned_run)
    assert orphaned_run.status == "Failed"
    assert "[ORPHAN_RECOVERY]" in orphaned_run.error_summary
    db.close()


def test_audit_logs_query(client, security_setup):
    """Verifies that administrative, promotion, and secret actions are recorded in audit trail."""
    headers = security_setup["headers"]

    audit_res = client.get("/api/v1/audit/logs", headers=headers["Admin"])
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 3
    actions = [l["action"] for l in logs]
    assert any("PIPELINE" in a for a in actions)
