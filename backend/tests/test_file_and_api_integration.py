import os
import time
import json
import tempfile
import threading
import httpx
import pytest
from unittest.mock import patch, MagicMock

# Import factory to ensure dynamic activity registration occurs
import backend.app.activities.factory
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.web import WebActivity
from backend.app.activities.webhook import WebhookActivity
from backend.app.activities.validation import ValidationActivity
from backend.app.activities.file_operation import FileOperationActivity
from backend.app.activities.archive import ArchiveActivity
from backend.app.connectors.local_file import LocalFileConnector
from backend.app.execution.callbacks import callback_store


def test_registry_contains_phase5_activities():
    """Verify that all Phase 5 activities are registered in ActivityRegistry."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}

    assert "WebActivity" in types
    assert "Webhook" in types
    assert "Validation" in types
    assert "FileOperation" in types
    assert "Archive" in types

    meta_val = activity_registry.get_metadata("Validation")
    assert meta_val.category == "Control Flow"

    meta_archive = activity_registry.get_metadata("Archive")
    assert meta_archive.category == "File & Storage"


def test_web_activity_get_request():
    """Test WebActivity executing a GET request against live health endpoint."""
    context = ActivityExecutionContext(
        activity_id="act-web-1",
        activity_name="CheckHealthEndpoint",
        activity_type="WebActivity",
        pipeline_run_id="run-web-1",
        config={
            "url": "http://127.0.0.1:8000/health",
            "method": "GET",
            "timeout_seconds": 10
        }
    )

    activity = WebActivity(context=context)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.output_variables["status_code"] == 200
    assert result.output_variables["response"]["status"] == "healthy"
    assert result.output_variables["duration_seconds"] >= 0


def test_webhook_activity_callback_success():
    """Test WebhookActivity asynchronously waiting for an external callback."""
    # Mock httpx.Client so external dispatch succeeds
    with patch("httpx.Client.request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.is_error = False
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp

        context = ActivityExecutionContext(
            activity_id="act-webhook-1",
            activity_name="LongRunningExternalJob",
            activity_type="Webhook",
            pipeline_run_id="run-wh-1",
            config={
                "url": "https://external-service.com/start",
                "timeout_seconds": 5,
                "callback_base_url": "http://127.0.0.1:8000"
            }
        )

        activity = WebhookActivity(context=context)

        # Simulate background external service calling back after 0.5s
        def delayed_callback():
            time.sleep(0.5)
            # Find the active callback token from the callback store
            with callback_store._lock:
                keys = list(callback_store._events.keys())
            if keys:
                token = keys[0]
                callback_store.receive(token, {"status": "SUCCESS", "records_processed": 5000})

        thread = threading.Thread(target=delayed_callback)
        thread.start()

        result = activity.execute()
        thread.join()

        assert result.status == "Succeeded"
        assert result.output_variables["callback_data"]["status"] == "SUCCESS"
        assert result.output_variables["callback_data"]["records_processed"] == 5000


def test_webhook_activity_timeout():
    """Test WebhookActivity cleanly times out if no callback is received."""
    with patch("httpx.Client.request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.is_error = False
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp

        context = ActivityExecutionContext(
            activity_id="act-webhook-timeout",
            activity_name="TimeoutExternalJob",
            activity_type="Webhook",
            pipeline_run_id="run-wh-2",
            config={
                "url": "https://external-service.com/start",
                "timeout_seconds": 1
            }
        )

        activity = WebhookActivity(context=context)
        result = activity.execute()

        assert result.status == "Failed"
        assert "timed out" in result.error_message.lower()


def test_validation_activity_local_file():
    """Test ValidationActivity verifying a file exists with minimum size."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".flag") as tmp:
        tmp.write(b"READY_PAYLOAD_DATA")
        tmp_path = tmp.name

    try:
        context = ActivityExecutionContext(
            activity_id="act-val-1",
            activity_name="CheckFileReady",
            activity_type="Validation",
            pipeline_run_id="run-val-1",
            config={
                "file_path": tmp_path,
                "minimum_size_bytes": 5,
                "timeout_seconds": 5,
                "sleep_interval_seconds": 1
            }
        )

        activity = ValidationActivity(context=context)
        result = activity.execute()

        assert result.status == "Succeeded"
        assert result.output_variables["exists"] is True
        assert result.output_variables["size_bytes"] >= 5

        # Now test failure on missing file
        context_fail = ActivityExecutionContext(
            activity_id="act-val-2",
            activity_name="CheckMissingFile",
            activity_type="Validation",
            pipeline_run_id="run-val-2",
            config={
                "file_path": "/tmp/non_existent_dataflow_file.flag",
                "timeout_seconds": 1,
                "sleep_interval_seconds": 1
            }
        )
        act_fail = ValidationActivity(context=context_fail)
        res_fail = act_fail.execute()
        assert res_fail.status == "Failed"
        assert "timed out" in res_fail.error_message.lower()

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_file_operations_lifecycle():
    """Test FileOperationActivity for copy, move, rename, exists, and delete."""
    with tempfile.TemporaryDirectory() as temp_dir:
        src_file = os.path.join(temp_dir, "order_feed_2026.csv")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("id,amount\n1,100\n2,200\n")

        # 1. File Exists
        ctx_exists = ActivityExecutionContext(
            activity_id="act-fo-exists",
            activity_name="CheckExists",
            activity_type="FileOperation",
            pipeline_run_id="run-fo-1",
            config={"operation": "file_exists", "source_path": os.path.join(temp_dir, "*.csv")}
        )
        res_exists = FileOperationActivity(context=ctx_exists).execute()
        assert res_exists.status == "Succeeded"
        assert res_exists.output_variables["exists"] is True
        assert res_exists.output_variables["matched_count"] == 1

        # 2. Copy
        copy_dest = os.path.join(temp_dir, "backup", "order_feed_backup.csv")
        ctx_copy = ActivityExecutionContext(
            activity_id="act-fo-copy",
            activity_name="CopyBackup",
            activity_type="FileOperation",
            pipeline_run_id="run-fo-1",
            config={"operation": "copy", "source_path": src_file, "destination_path": copy_dest}
        )
        res_copy = FileOperationActivity(context=ctx_copy).execute()
        assert res_copy.status == "Succeeded"
        assert os.path.exists(copy_dest)

        # 3. Rename
        renamed_dest = os.path.join(temp_dir, "backup", "order_feed_v2.csv")
        ctx_rename = ActivityExecutionContext(
            activity_id="act-fo-rename",
            activity_name="RenameFile",
            activity_type="FileOperation",
            pipeline_run_id="run-fo-1",
            config={"operation": "rename", "source_path": copy_dest, "destination_path": renamed_dest}
        )
        res_rename = FileOperationActivity(context=ctx_rename).execute()
        assert res_rename.status == "Succeeded"
        assert not os.path.exists(copy_dest)
        assert os.path.exists(renamed_dest)

        # 4. Move
        moved_dest = os.path.join(temp_dir, "archive", "order_feed_v2.csv")
        ctx_move = ActivityExecutionContext(
            activity_id="act-fo-move",
            activity_name="MoveFile",
            activity_type="FileOperation",
            pipeline_run_id="run-fo-1",
            config={"operation": "move", "source_path": renamed_dest, "destination_path": moved_dest}
        )
        res_move = FileOperationActivity(context=ctx_move).execute()
        assert res_move.status == "Succeeded"
        assert not os.path.exists(renamed_dest)
        assert os.path.exists(moved_dest)

        # 5. Delete
        ctx_del = ActivityExecutionContext(
            activity_id="act-fo-delete",
            activity_name="DeleteFile",
            activity_type="FileOperation",
            pipeline_run_id="run-fo-1",
            config={"operation": "delete", "source_path": os.path.join(temp_dir, "*.csv")}
        )
        res_del = FileOperationActivity(context=ctx_del).execute()
        assert res_del.status == "Succeeded"
        assert not os.path.exists(src_file)


def test_archive_compress_and_extract():
    """Test ArchiveActivity compressing to .zip and extracting to target directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = os.path.join(temp_dir, "input_files")
        os.makedirs(input_dir)
        with open(os.path.join(input_dir, "f1.txt"), "w") as f:
            f.write("Alpha data")
        with open(os.path.join(input_dir, "f2.txt"), "w") as f:
            f.write("Beta data")

        zip_target = os.path.join(temp_dir, "output", "package.zip")
        ctx_zip = ActivityExecutionContext(
            activity_id="act-arch-1",
            activity_name="ZipFolder",
            activity_type="Archive",
            pipeline_run_id="run-arch-1",
            config={
                "action": "compress",
                "format": "zip",
                "source_path": input_dir,
                "destination_path": zip_target
            }
        )
        res_zip = ArchiveActivity(context=ctx_zip).execute()
        assert res_zip.status == "Succeeded"
        assert os.path.exists(zip_target)
        assert res_zip.output_variables["archive_size_bytes"] > 0

        # Extract
        extract_dir = os.path.join(temp_dir, "extracted")
        ctx_unzip = ActivityExecutionContext(
            activity_id="act-arch-2",
            activity_name="UnzipFolder",
            activity_type="Archive",
            pipeline_run_id="run-arch-1",
            config={
                "action": "extract",
                "source_path": zip_target,
                "destination_path": extract_dir
            }
        )
        res_unzip = ArchiveActivity(context=ctx_unzip).execute()
        assert res_unzip.status == "Succeeded"
        assert os.path.exists(os.path.join(extract_dir, "f1.txt"))
        assert os.path.exists(os.path.join(extract_dir, "f2.txt"))
        with open(os.path.join(extract_dir, "f1.txt"), "r") as f:
            assert f.read() == "Alpha data"


def test_local_file_connector_parquet_and_excel():
    """Test LocalFileConnector reading/writing Parquet and Excel formats."""
    with tempfile.TemporaryDirectory() as temp_dir:
        connector = LocalFileConnector({"base_path": temp_dir})

        # 1. Parquet write & read
        sample_records = [
            {"product_id": 1, "sku": "SKU-A", "price": 19.99},
            {"product_id": 2, "sku": "SKU-B", "price": 49.50},
            {"product_id": 3, "sku": "SKU-C", "price": 99.00}
        ]
        written_pq = connector.write_data_batch("products.parquet", sample_records, write_mode="overwrite")
        assert written_pq == 3

        meta_pq = connector.get_metadata("products.parquet")
        assert meta_pq["exists"] is True
        assert meta_pq["rowCount"] == 3
        assert meta_pq["columnCount"] == 3

        read_pq = list(connector.read_data_stream("products.parquet"))
        assert len(read_pq) == 1
        assert len(read_pq[0]) == 3
        assert read_pq[0][0]["sku"] == "SKU-A"

        # 2. Excel write & read
        sample_excel = [
            {"department": "Engineering", "headcount": 45},
            {"department": "Sales", "headcount": 30}
        ]
        written_xl = connector.write_data_batch("departments.xlsx", sample_excel, write_mode="overwrite")
        assert written_xl == 2

        meta_xl = connector.get_metadata("departments.xlsx")
        assert meta_xl["exists"] is True
        assert meta_xl["rowCount"] == 2

        read_xl = list(connector.read_data_stream("departments.xlsx"))
        assert len(read_xl) == 1
        assert len(read_xl[0]) == 2
        assert read_xl[0][0]["department"] == "Engineering"
