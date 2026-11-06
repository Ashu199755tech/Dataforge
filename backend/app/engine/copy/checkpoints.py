import time
from typing import Dict, Any, List, Optional
from backend.app.engine.copy.models import PartitionSpec, CheckpointToken


class PartitionCheckpointLedger:
    """
    Manages partition-level checkpoint persistence for fault-tolerant resumable execution.
    Tracks state of each partition slice so failed runs resume only incomplete partitions.
    """

    def __init__(self, run_id: str, activity_id: str):
        self.run_id = run_id
        self.activity_id = activity_id
        self.partitions: Dict[str, PartitionSpec] = {}
        self.checkpoints: Dict[str, CheckpointToken] = {}

    def register_partitions(self, partition_specs: List[PartitionSpec]) -> None:
        """Initializes ledger with partition slice specifications."""
        for p in partition_specs:
            self.partitions[p.partition_id] = p

    def load_existing_checkpoints(self, checkpoint_data: Optional[Dict[str, Any]]) -> None:
        """Loads previously saved checkpoints to support partial resumption."""
        if not checkpoint_data or not isinstance(checkpoint_data, dict):
            return

        for p_id, p_info in checkpoint_data.items():
            if isinstance(p_info, dict):
                token = CheckpointToken(
                    partition_id=p_id,
                    completed_at=p_info.get("completed_at", time.time()),
                    rows_transferred=p_info.get("rows_transferred", 0),
                    bytes_transferred=p_info.get("bytes_transferred", 0),
                    checksum=p_info.get("checksum"),
                    metadata=p_info.get("metadata", {})
                )
                self.checkpoints[p_id] = token
                if p_id in self.partitions:
                    self.partitions[p_id].status = "Succeeded"
                    self.partitions[p_id].rows_transferred = token.rows_transferred
                    self.partitions[p_id].bytes_transferred = token.bytes_transferred

    def mark_in_progress(self, partition_id: str) -> None:
        if partition_id in self.partitions:
            self.partitions[partition_id].status = "InProgress"

    def mark_completed(
        self,
        partition_id: str,
        rows_transferred: int,
        bytes_transferred: int,
        checksum: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CheckpointToken:
        """Records successful partition completion and issues checkpoint token."""
        token = CheckpointToken(
            partition_id=partition_id,
            completed_at=time.time(),
            rows_transferred=rows_transferred,
            bytes_transferred=bytes_transferred,
            checksum=checksum,
            metadata=metadata or {}
        )
        self.checkpoints[partition_id] = token
        if partition_id in self.partitions:
            self.partitions[partition_id].status = "Succeeded"
            self.partitions[partition_id].rows_transferred = rows_transferred
            self.partitions[partition_id].bytes_transferred = bytes_transferred
        return token

    def mark_failed(self, partition_id: str, error_message: str) -> None:
        if partition_id in self.partitions:
            self.partitions[partition_id].status = "Failed"
            self.partitions[partition_id].error_message = error_message

    def get_pending_partitions(self) -> List[PartitionSpec]:
        """Returns partition slices that need execution (skipping already checkpointed ones)."""
        return [
            p for p in self.partitions.values() 
            if p.partition_id not in self.checkpoints and p.status != "Succeeded"
        ]

    def is_all_completed(self) -> bool:
        """Checks if all registered partitions have completed successfully."""
        if not self.partitions:
            return True
        return all(p.status == "Succeeded" for p in self.partitions.values())

    def get_total_stats(self) -> Dict[str, Any]:
        """Aggregates total rows, bytes, and partition counts."""
        total_rows = sum(p.rows_transferred for p in self.partitions.values())
        total_bytes = sum(p.bytes_transferred for p in self.partitions.values())
        succeeded = sum(1 for p in self.partitions.values() if p.status == "Succeeded")
        failed = sum(1 for p in self.partitions.values() if p.status == "Failed")
        return {
            "total_partitions": len(self.partitions),
            "succeeded_partitions": succeeded,
            "failed_partitions": failed,
            "total_rows": total_rows,
            "total_bytes": total_bytes
        }

    def serialize_checkpoints(self) -> Dict[str, Any]:
        """Serializes checkpoints for persistence in ActivityRun.metrics."""
        return {
            p_id: {
                "completed_at": token.completed_at,
                "rows_transferred": token.rows_transferred,
                "bytes_transferred": token.bytes_transferred,
                "checksum": token.checksum,
                "metadata": token.metadata
            }
            for p_id, token in self.checkpoints.items()
        }
