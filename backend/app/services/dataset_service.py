import io
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.dataset import Dataset, DatasetVersion
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    SchemaDriftReport,
    DatasetPreviewResponse,
    DatasetUsageResponse
)
from backend.app.core.security import decrypt_secret
from backend.app.connectors.factory import get_connector
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.formats.registry import FormatRegistry


class DatasetService:
    """
    Central service for managing Reusable Datasets:
    - Relational tables/queries and multi-cloud file datasets (ADLS, S3, GCS, Local)
    - Automated schema discovery & inference from live connections
    - Schema drift detection & schema version snapshots
    - Bounded memory-safe data previewing
    - Pipeline dependency and usage analysis
    """

    @classmethod
    def create_dataset(cls, db: Session, dataset_in: DatasetCreate) -> Dataset:
        """Creates a dataset, auto-discovers schema if requested, and saves initial version snapshot."""
        conn = db.query(Connection).filter(Connection.id == dataset_in.connection_id).first()
        if not conn:
            raise ValueError(f"Referenced connection '{dataset_in.connection_id}' not found.")

        schema_def = list(dataset_in.schema_definition or [])

        # Create dataset instance
        dataset = Dataset(
            project_id=dataset_in.project_id or conn.project_id,
            connection_id=conn.id,
            name=dataset_in.name,
            description=dataset_in.description,
            dataset_type=dataset_in.dataset_type,
            location_config=dataset_in.location_config,
            format_settings=dataset_in.format_settings,
            parameters=dataset_in.parameters,
            schema_definition=schema_def,
            current_version=1,
            schema_status="Current"
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        # Auto-discover schema if requested and empty
        if dataset_in.auto_discover_schema and not schema_def:
            try:
                discovered = cls.infer_schema(db, dataset)
                if discovered:
                    dataset.schema_definition = discovered
                    db.commit()
                    db.refresh(dataset)
            except Exception as e:
                # Non-fatal: if target table or file doesn't exist yet, leave schema empty
                print(f"[WARN] Auto-discovery for dataset '{dataset.name}' encountered: {e}")

        # Save Version 1 snapshot
        initial_version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=1,
            schema_snapshot=dataset.schema_definition,
            location_snapshot=dataset.location_config,
            format_snapshot=dataset.format_settings,
            change_summary="Initial dataset creation"
        )
        db.add(initial_version)
        db.commit()

        return dataset

    @classmethod
    def get_dataset(cls, db: Session, dataset_id: str) -> Dataset:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' not found.")
        return dataset

    @classmethod
    def list_datasets(
        cls,
        db: Session,
        project_id: Optional[str] = None,
        connection_id: Optional[str] = None
    ) -> List[Dataset]:
        query = db.query(Dataset)
        if project_id:
            query = query.filter(Dataset.project_id == project_id)
        if connection_id:
            query = query.filter(Dataset.connection_id == connection_id)
        return query.order_by(Dataset.name.asc()).all()

    @classmethod
    def update_dataset(cls, db: Session, dataset_id: str, dataset_in: DatasetUpdate) -> Dataset:
        dataset = cls.get_dataset(db, dataset_id)

        schema_changed = False
        new_schema = None

        if dataset_in.name is not None:
            dataset.name = dataset_in.name
        if dataset_in.description is not None:
            dataset.description = dataset_in.description
        if dataset_in.location_config is not None:
            dataset.location_config = dataset_in.location_config
        if dataset_in.format_settings is not None:
            dataset.format_settings = dataset_in.format_settings
        if dataset_in.parameters is not None:
            dataset.parameters = dataset_in.parameters

        if dataset_in.schema_definition is not None:
            if dataset_in.schema_definition != dataset.schema_definition:
                schema_changed = True
                new_schema = dataset_in.schema_definition
                dataset.schema_definition = new_schema

        dataset.updated_at = datetime.now(timezone.utc)

        # If schema changed, create new version snapshot
        if schema_changed:
            dataset.current_version += 1
            dataset.schema_status = "Current"
            dataset.last_drift_summary = None

            version_record = DatasetVersion(
                dataset_id=dataset.id,
                version_number=dataset.current_version,
                schema_snapshot=dataset.schema_definition,
                location_snapshot=dataset.location_config,
                format_snapshot=dataset.format_settings,
                change_summary=f"Schema updated to version {dataset.current_version}"
            )
            db.add(version_record)

        db.commit()
        db.refresh(dataset)
        return dataset

    @classmethod
    def delete_dataset(cls, db: Session, dataset_id: str) -> bool:
        dataset = cls.get_dataset(db, dataset_id)
        db.delete(dataset)
        db.commit()
        return True

    @classmethod
    def infer_schema(
        cls,
        db: Session,
        dataset: Dataset,
        parameter_values: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Infers schema directly from physical data source (database table or storage file).
        Returns normalized list: [{"name": col, "type": dtype, "nullable": bool}]
        """
        conn = db.query(Connection).filter(Connection.id == dataset.connection_id).first()
        if not conn:
            raise ValueError(f"Connection '{dataset.connection_id}' not found.")

        decrypted_config = decrypt_secret(conn.config_encrypted)
        connector = get_connector(conn.connector_type, decrypted_config)
        loc = dataset.location_config or {}

        # 1. Relational Database Source
        if not isinstance(connector, BaseStorageConnector) and hasattr(connector, "discover_columns"):
            table_name = loc.get("table") or loc.get("table_name")
            schema_name = loc.get("schema") or loc.get("schema_name")
            if not table_name:
                raise ValueError("Location config must specify 'table' for relational dataset schema discovery.")
            cols = connector.discover_columns(table_name=table_name, schema_name=schema_name)
            return [
                {
                    "name": col.name,
                    "type": str(col.data_type).upper(),
                    "nullable": bool(getattr(col, "is_nullable", getattr(col, "nullable", True))),
                    "description": getattr(col, "comment", None)
                }
                for col in cols
            ]

        # 2. Object Storage / File Dataset (ADLS, S3, GCS, Local)
        if isinstance(connector, BaseStorageConnector):
            container = loc.get("container") or loc.get("bucket")
            file_path = loc.get("path") or loc.get("file_name") or loc.get("prefix") or ""
            if not container:
                raise ValueError("Location config must specify 'container' or 'bucket' for storage datasets.")

            # If path points to directory or empty, discover first file
            if not file_path or file_path.endswith("/"):
                files = list(connector.list_files(container=container, prefix=file_path, limit=5))
                if not files:
                    raise ValueError(f"No files found in '{container}/{file_path}' to infer schema from.")
                file_path = files[0].key

            fmt_name = loc.get("format") or dataset.format_settings.get("format") or FormatRegistry.detect_format_from_filename(file_path)
            reader = FormatRegistry.get_reader(fmt_name, dataset.format_settings)

            # Sample bounded chunk for schema inference
            chunks = []
            bytes_read = 0
            for chunk in connector.read_stream(container=container, object_key=file_path, chunk_size=64 * 1024):
                chunks.append(chunk)
                bytes_read += len(chunk)
                if bytes_read >= 2 * 1024 * 1024:  # 2MB sample ceiling
                    break

            buffered = io.BytesIO(b"".join(chunks))
            preview_res = reader.preview(buffered, limit=10)

            inferred_cols = []
            for col_name in preview_res.columns:
                # Detect column type from sample values
                sample_vals = [r.get(col_name) for r in preview_res.rows if r.get(col_name) is not None]
                inferred_type = "VARCHAR"
                if sample_vals:
                    first = sample_vals[0]
                    if isinstance(first, int):
                        inferred_type = "INTEGER"
                    elif isinstance(first, float):
                        inferred_type = "FLOAT"
                    elif isinstance(first, bool):
                        inferred_type = "BOOLEAN"
                    elif isinstance(first, dict) or isinstance(first, list):
                        inferred_type = "JSON"
                inferred_cols.append({
                    "name": col_name,
                    "type": inferred_type,
                    "nullable": True
                })
            return inferred_cols

        return []

    @classmethod
    def detect_schema_drift(cls, db: Session, dataset_id: str) -> SchemaDriftReport:
        """
        Compares stored dataset schema against live physical schema.
        Identifies added, removed, and altered columns.
        """
        dataset = cls.get_dataset(db, dataset_id)
        current_stored = dataset.schema_definition or []
        stored_map = {c["name"].lower(): c for c in current_stored}

        try:
            physical_schema = cls.infer_schema(db, dataset)
        except Exception as e:
            raise RuntimeError(f"Could not reach physical source to check schema drift: {str(e)}")

        physical_map = {c["name"].lower(): c for c in physical_schema}

        added = []
        removed = []
        altered = []

        # Find added columns
        for name_lower, col in physical_map.items():
            if name_lower not in stored_map:
                added.append(col)

        # Find removed columns
        for name_lower, col in stored_map.items():
            if name_lower not in physical_map:
                removed.append(col)

        # Find altered columns
        for name_lower, phys_col in physical_map.items():
            if name_lower in stored_map:
                stored_col = stored_map[name_lower]
                phys_type = phys_col.get("type", "").upper()
                stored_type = stored_col.get("type", "").upper()
                if phys_type != stored_type:
                    altered.append({
                        "name": stored_col["name"],
                        "stored_type": stored_type,
                        "physical_type": phys_type,
                        "change": f"Type altered from {stored_type} to {phys_type}"
                    })

        has_drift = bool(added or removed or altered)
        status = "DriftDetected" if has_drift else "Current"

        # Update dataset drift tracking columns
        dataset.schema_status = status
        dataset.last_drift_check_at = datetime.now(timezone.utc)
        dataset.last_drift_summary = {
            "has_drift": has_drift,
            "status": status,
            "added_count": len(added),
            "removed_count": len(removed),
            "altered_count": len(altered),
            "added_columns": added,
            "removed_columns": removed,
            "altered_columns": altered
        }
        db.commit()
        db.refresh(dataset)

        return SchemaDriftReport(
            has_drift=has_drift,
            status=status,
            added_columns=added,
            removed_columns=removed,
            altered_columns=altered,
            current_physical_schema=physical_schema,
            stored_schema=current_stored
        )

    @classmethod
    def sync_schema(
        cls,
        db: Session,
        dataset_id: str,
        change_summary: Optional[str] = None
    ) -> Tuple[Dataset, DatasetVersion]:
        """
        Pulls current physical schema and creates a new version snapshot,
        resetting schema status to Current.
        """
        dataset = cls.get_dataset(db, dataset_id)
        physical_schema = cls.infer_schema(db, dataset)

        dataset.current_version += 1
        dataset.schema_definition = physical_schema
        dataset.schema_status = "Current"
        dataset.last_drift_check_at = datetime.now(timezone.utc)
        dataset.last_drift_summary = {"has_drift": False, "status": "Current"}
        dataset.updated_at = datetime.now(timezone.utc)

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=dataset.current_version,
            schema_snapshot=physical_schema,
            location_snapshot=dataset.location_config,
            format_snapshot=dataset.format_settings,
            change_summary=change_summary or f"Synchronized schema with live source (Version {dataset.current_version})"
        )
        db.add(version)
        db.commit()
        db.refresh(dataset)
        db.refresh(version)

        return dataset, version

    @classmethod
    def preview_data(
        cls,
        db: Session,
        dataset_id: str,
        row_limit: int = 50,
        parameter_values: Optional[Dict[str, Any]] = None
    ) -> DatasetPreviewResponse:
        """
        Safely previews up to row_limit records with memory ceiling protection.
        """
        start_clock = time.time()
        row_limit = max(1, min(row_limit, 500))

        dataset = cls.get_dataset(db, dataset_id)
        conn = db.query(Connection).filter(Connection.id == dataset.connection_id).first()
        if not conn:
            raise ValueError(f"Connection '{dataset.connection_id}' not found.")

        decrypted_config = decrypt_secret(conn.config_encrypted)
        connector = get_connector(conn.connector_type, decrypted_config)
        loc = dataset.location_config or {}

        columns: List[str] = []
        rows: List[Dict[str, Any]] = []
        bytes_sampled = 0

        # Relational Preview
        if not isinstance(connector, BaseStorageConnector) and hasattr(connector, "read_data_stream"):
            table_name = loc.get("table") or loc.get("table_name")
            schema_name = loc.get("schema") or loc.get("schema_name")
            stream = connector.read_data_stream(table_name=table_name, batch_size=row_limit, schema_name=schema_name)
            for batch in stream:
                rows.extend(batch)
                if len(rows) >= row_limit:
                    break
            rows = rows[:row_limit]
            if rows:
                columns = list(rows[0].keys())
            bytes_sampled = len(json.dumps(rows).encode("utf-8"))

        # Storage Preview
        elif isinstance(connector, BaseStorageConnector):
            container = loc.get("container") or loc.get("bucket")
            file_path = loc.get("path") or loc.get("file_name") or loc.get("prefix") or ""
            if not container:
                raise ValueError("Location config must specify 'container' or 'bucket'.")

            if not file_path or file_path.endswith("/"):
                files = list(connector.list_files(container=container, prefix=file_path, limit=5))
                if not files:
                    raise ValueError(f"No files found in '{container}/{file_path}' to preview.")
                file_path = files[0].key

            fmt_name = loc.get("format") or dataset.format_settings.get("format") or FormatRegistry.detect_format_from_filename(file_path)
            reader = FormatRegistry.get_reader(fmt_name, dataset.format_settings)

            chunks = []
            for chunk in connector.read_stream(container=container, object_key=file_path, chunk_size=64 * 1024):
                chunks.append(chunk)
                bytes_sampled += len(chunk)
                if bytes_sampled >= 2 * 1024 * 1024:
                    break

            buffered = io.BytesIO(b"".join(chunks))
            preview_res = reader.preview(buffered, limit=row_limit)
            columns = preview_res.columns
            rows = preview_res.rows

        duration_ms = max(1, int((time.time() - start_clock) * 1000))

        return DatasetPreviewResponse(
            columns=columns,
            rows=rows,
            total_rows_previewed=len(rows),
            bytes_sampled=bytes_sampled,
            duration_ms=duration_ms
        )

    @classmethod
    def get_dataset_usages(cls, db: Session, dataset_id: str) -> DatasetUsageResponse:
        """
        Scans all pipelines to locate activities referencing this dataset as source or sink.
        """
        dataset = cls.get_dataset(db, dataset_id)
        pipelines = db.query(Pipeline).all()

        matching_pipelines: List[Dict[str, Any]] = []

        for p in pipelines:
            p_def = p.definition_json or {}
            activities = p_def.get("activities", [])
            referencing_activities = []

            for act in activities:
                cfg = act.get("config", {})
                source = cfg.get("source", {})
                sink = cfg.get("sink", {})

                is_source = (source.get("dataset_id") == dataset_id or act.get("source_dataset_id") == dataset_id)
                is_sink = (sink.get("dataset_id") == dataset_id or act.get("sink_dataset_id") == dataset_id)
                direct_match = (act.get("dataset_id") == dataset_id)

                if is_source or is_sink or direct_match:
                    referencing_activities.append({
                        "activity_id": act.get("id"),
                        "activity_name": act.get("name", act.get("id")),
                        "activity_type": act.get("type", "Unknown"),
                        "role": "Source" if is_source else ("Sink" if is_sink else "Reference")
                    })

            if referencing_activities:
                matching_pipelines.append({
                    "pipeline_id": p.id,
                    "pipeline_name": p.name,
                    "activities": referencing_activities
                })

        return DatasetUsageResponse(
            dataset_id=dataset.id,
            pipeline_count=len(matching_pipelines),
            pipelines=matching_pipelines
        )
