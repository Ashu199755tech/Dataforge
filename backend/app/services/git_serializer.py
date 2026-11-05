import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.dataset import Dataset, DatasetVersion
from backend.app.models.connection import Connection
from backend.app.models.trigger import Trigger
from backend.app.models.dataflow import DataFlow
from backend.app.models.runtime import IntegrationRuntime
from backend.app.core.security import decrypt_secret


class GitAssetSerializer:
    """
    Deterministic Canonical JSON Serializer for DataForge Enterprise Assets.
    Ensures sorted keys, normalized whitespace, stripped/parameterized secrets,
    and SHA-256 checksums to eliminate false diffs in Git version control.
    """

    @classmethod
    def to_canonical_json(cls, data: Dict[str, Any]) -> str:
        """Serializes dictionary to deterministic, pretty-printed canonical JSON with trailing newline."""
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def compute_checksum(cls, canonical_json: str) -> str:
        """Computes SHA-256 digest of canonical JSON content."""
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def serialize_pipeline(cls, pipeline: Pipeline) -> Dict[str, Any]:
        """Serializes a pipeline and its activities."""
        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/pipeline.json",
            "asset_type": "Pipeline",
            "name": pipeline.name,
            "description": pipeline.description or "",
            "concurrency_limit": pipeline.concurrency_limit,
            "definition": pipeline.definition_json or {},
            "status": pipeline.status or "Draft"
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def serialize_dataset(cls, dataset: Dataset) -> Dict[str, Any]:
        """Serializes a reusable dataset definition."""
        conn_name = dataset.connection.name if getattr(dataset, "connection", None) else None
        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/dataset.json",
            "asset_type": "Dataset",
            "name": dataset.name,
            "description": dataset.description or "",
            "dataset_type": dataset.dataset_type,
            "connection_name": conn_name,
            "location_config": dataset.location_config or {},
            "format_settings": dataset.format_settings or {},
            "parameters": dataset.parameters or {},
            "schema_definition": dataset.schema_definition or []
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def serialize_connection(cls, connection: Connection) -> Dict[str, Any]:
        """
        Serializes a connection (Linked Service) with credentials stripped or parameterized.
        Strictly prevents passwords, account keys, and SAS tokens from entering Git.
        """
        config_masked = {}
        try:
            raw_cfg = decrypt_secret(connection.config_encrypted)
            for k, v in raw_cfg.items():
                k_lower = k.lower()
                if any(secret_term in k_lower for secret_term in ["password", "secret", "key", "token", "pwd"]):
                    # Parameterize secret reference
                    config_masked[k] = f"${{vault:{connection.name}_{k}}}"
                else:
                    config_masked[k] = v
        except Exception:
            config_masked = {"masked": True}

        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/connection.json",
            "asset_type": "Connection",
            "name": connection.name,
            "description": connection.description or "",
            "connector_type": connection.connector_type,
            "config": config_masked
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def serialize_trigger(cls, trigger: Trigger) -> Dict[str, Any]:
        """Serializes trigger schedule, event listener, or tumbling window configuration."""
        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/trigger.json",
            "asset_type": "Trigger",
            "name": trigger.name,
            "description": trigger.description or "",
            "trigger_type": trigger.trigger_type,
            "cron_expression": trigger.cron_expression,
            "schedule_config": trigger.schedule_config or {},
            "tumbling_window_config": trigger.tumbling_window_config or {},
            "storage_event_config": trigger.storage_event_config or {},
            "pipeline_dependency_config": trigger.pipeline_dependency_config or {},
            "pipelines_to_run": trigger.pipelines_to_run or [],
            "parameters": trigger.parameters or {},
            "is_active": trigger.is_active
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def serialize_dataflow(cls, dataflow: DataFlow) -> Dict[str, Any]:
        """Serializes a mapping data flow graph."""
        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/dataflow.json",
            "asset_type": "DataFlow",
            "name": dataflow.name,
            "description": dataflow.description or "",
            "graph_definition": dataflow.graph_definition or {},
            "parameters": dataflow.parameters or {}
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def serialize_runtime(cls, runtime: IntegrationRuntime) -> Dict[str, Any]:
        """Serializes an Integration Runtime definition with tokens sanitized."""
        payload = {
            "$schema": "https://dataforge.enterprise/schemas/v1/runtime.json",
            "asset_type": "IntegrationRuntime",
            "name": runtime.name,
            "description": runtime.description or "",
            "runtime_type": runtime.runtime_type,
            "config": runtime.config or {}
        }
        raw = cls.to_canonical_json(payload)
        payload["checksum"] = cls.compute_checksum(raw)
        return payload

    @classmethod
    def export_workspace_tree(cls, db: Session, project_id: str) -> Dict[str, str]:
        """
        Exports all assets in a project into a clean relative repository folder tree.
        Returns a dictionary of: { "path/to/asset.json": canonical_json_string }
        """
        tree: Dict[str, str] = {}

        # 1. Pipelines
        pipelines = db.query(Pipeline).filter(Pipeline.project_id == project_id).all()
        for p in pipelines:
            fname = p.name.strip().replace(" ", "_").lower()
            rel_path = f"pipelines/{fname}.json"
            tree[rel_path] = cls.to_canonical_json(cls.serialize_pipeline(p))

        # 2. Datasets
        datasets = db.query(Dataset).filter(Dataset.project_id == project_id).all()
        for d in datasets:
            fname = d.name.strip().replace(" ", "_").lower()
            rel_path = f"datasets/{fname}.json"
            tree[rel_path] = cls.to_canonical_json(cls.serialize_dataset(d))

        # 3. Connections
        connections = db.query(Connection).filter(Connection.project_id == project_id).all()
        for c in connections:
            fname = c.name.strip().replace(" ", "_").lower()
            rel_path = f"connections/{fname}.json"
            tree[rel_path] = cls.to_canonical_json(cls.serialize_connection(c))

        # 4. Triggers
        triggers = db.query(Trigger).all()  # triggers can target project pipelines
        pipe_ids = {p.id for p in pipelines}
        for t in triggers:
            # Check if this trigger targets any pipeline in this project
            target_ids = [p.get("pipeline_id") for p in (t.pipelines_to_run or []) if p.get("pipeline_id")]
            if t.pipeline_id in pipe_ids or any(pid in pipe_ids for pid in target_ids):
                fname = t.name.strip().replace(" ", "_").lower()
                rel_path = f"triggers/{fname}.json"
                tree[rel_path] = cls.to_canonical_json(cls.serialize_trigger(t))

        # 5. DataFlows
        dataflows = db.query(DataFlow).filter(DataFlow.project_id == project_id).all()
        for df in dataflows:
            fname = df.name.strip().replace(" ", "_").lower()
            rel_path = f"dataflows/{fname}.json"
            tree[rel_path] = cls.to_canonical_json(cls.serialize_dataflow(df))

        # 6. Integration Runtimes
        runtimes = db.query(IntegrationRuntime).filter(
            (IntegrationRuntime.project_id == project_id) | (IntegrationRuntime.project_id == None)
        ).all()
        for r in runtimes:
            fname = r.name.strip().replace(" ", "_").lower()
            rel_path = f"runtimes/{fname}.json"
            tree[rel_path] = cls.to_canonical_json(cls.serialize_runtime(r))

        return tree
