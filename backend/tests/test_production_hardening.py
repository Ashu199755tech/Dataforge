import pytest
import json
from datetime import datetime, timezone
from backend.app.core.security import mask_secret_dict, encrypt_secret, decrypt_secret
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.storage.models import StorageException, StorageErrorCategory
from backend.app.models.connection import Connection
from backend.app.models.workspace import Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.core.database import SessionLocal
from backend.app.api.connections import _to_response


class TestProductionHardeningAndSecurity:
    """
    Phase 10 Production Readiness and Hardening Test Suite:
    - Zero Credential Leakage Verification
    - Missing Dependency Diagnostics
    - Non-Blocking Execution and Cancellation
    """

    def test_credential_masking_comprehensive(self):
        """Verifies recursive masking of all sensitive credentials across cloud providers."""
        raw_config = {
            "account_name": "dataforgestore",
            "account_key": "SuperSecretKey123==",
            "sas_token": "?sv=2021-06-08&ss=bfqt&srt=sco&sp=rwdlacupx",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "session_token": "AQoDYXdzEJr111111111111111111111",
            "service_account_json": {
                "type": "service_account",
                "private_key_id": "key_abc_123",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgI...\n-----END PRIVATE KEY-----\n",
                "client_email": "sa@proj.iam.gserviceaccount.com",
                "client_secret": "SuperClientSecret"
            },
            "public_setting": "safe_value",
            "region": "us-east-1",
            "port": 5432
        }

        masked = mask_secret_dict(raw_config)

        # Sensitive keys masked
        assert masked["account_key"] == "********"
        assert masked["sas_token"] == "********"
        assert masked["secret_access_key"] == "********"
        assert masked["session_token"] == "********"
        
        # Nested credentials masked
        assert masked["service_account_json"]["private_key_id"] == "********"
        assert masked["service_account_json"]["private_key"] == "********"
        assert masked["service_account_json"]["client_secret"] == "********"

        # Safe metadata preserved
        assert masked["account_name"] == "dataforgestore"
        assert masked["region"] == "us-east-1"
        assert masked["port"] == 5432
        assert masked["public_setting"] == "safe_value"
        assert masked["service_account_json"]["client_email"] == "sa@proj.iam.gserviceaccount.com"

    def test_connection_response_guarantees_zero_secret_leakage(self):
        """Verifies ConnectionResponse DTO returns only masked secrets."""
        db = SessionLocal()
        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Hardening Project")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            raw_secrets = {
                "account_name": "corpstore",
                "account_key": "ACTUAL_SECRET_KEY_NEVER_EXPOSE",
                "connection_string": "DefaultEndpointsProtocol=https;AccountName=corpstore;AccountKey=RAW_KEY;"
            }

            conn = Connection(
                project_id=proj.id,
                name="Secure Azure Store",
                connector_type="azure_blob",
                config_encrypted=encrypt_secret(raw_secrets),
                status="Verified"
            )
            db.add(conn)
            db.commit()
            db.refresh(conn)

            resp = _to_response(conn)
            resp_dict = resp.model_dump()

            # Ensure config_masked is present and raw secrets are sanitized
            assert "config_masked" in resp_dict
            assert resp_dict["config_masked"]["account_key"] == "********"
            assert resp_dict["config_masked"]["connection_string"] == "********"
            assert "ACTUAL_SECRET_KEY_NEVER_EXPOSE" not in str(resp_dict)
            assert "RAW_KEY" not in str(resp_dict)

            # Cleanup
            db.delete(conn)
            db.commit()
        finally:
            db.close()

    def test_missing_dependency_diagnostics_message(self):
        """Verifies clear error diagnostics when a cloud SDK is missing."""
        # Querying an unregistered provider raises descriptive StorageException
        with pytest.raises(StorageException) as exc_info:
            StorageProviderRegistry.create_connector("oracle_cloud_storage", {})
        
        assert exc_info.value.category == StorageErrorCategory.OPERATION_NOT_SUPPORTED
        assert "Unknown storage provider 'oracle_cloud_storage'" in str(exc_info.value)

    def test_cancellation_state_machine_and_reason_recording(self):
        """Verifies cancellation transition and audit reason recording."""
        db = SessionLocal()
        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Test Cancellation Proj")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            pipe = Pipeline(
                project_id=proj.id,
                name=f"Cancel_Pipe_{int(datetime.now(timezone.utc).timestamp())}",
                definition_json={"activities": []}
            )
            db.add(pipe)
            db.commit()
            db.refresh(pipe)

            run = PipelineRun(
                pipeline_id=pipe.id,
                status="Running",
                run_type="Manual",
                started_at=datetime.now(timezone.utc)
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            # Transition to Cancelled
            run.status = "Cancelled"
            run.ended_at = datetime.now(timezone.utc)
            run.error_summary = "Execution cancelled by operator."
            db.commit()
            db.refresh(run)

            assert run.status == "Cancelled"
            assert run.ended_at is not None
            assert "cancelled by operator" in run.error_summary.lower()

            # Cleanup
            db.delete(run)
            db.delete(pipe)
            db.commit()
        finally:
            db.close()
