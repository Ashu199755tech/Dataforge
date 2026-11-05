import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from backend.app.execution.providers.base import BaseComputeProvider, ComputeJobHandle


class DatabricksExecutionProvider(BaseComputeProvider):
    """
    Vendor-independent Databricks REST API 2.1 Provider.
    Enables remote execution of Databricks notebooks, python files, and JAR workloads.
    """

    def __init__(self, host: str, token: str):
        self.host = host.rstrip("/")
        if not self.host.startswith("http"):
            self.host = f"https://{self.host}"
        self.token = token

    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.host}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "DataFlowEnterprise/1.0"
        }
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Databricks API Error ({e.code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Databricks cluster at {self.host}: {str(e)}")

    def submit_job(self, job_spec: Dict[str, Any]) -> ComputeJobHandle:
        """
        Calls /api/2.1/jobs/runs/submit
        """
        resp = self._make_request("POST", "/api/2.1/jobs/runs/submit", job_spec)
        run_id = str(resp.get("run_id"))
        return ComputeJobHandle(
            job_id=str(job_spec.get("existing_cluster_id", "one_time_cluster")),
            run_id=run_id,
            status="PENDING"
        )

    def get_job_status(self, job_id: str, run_id: str) -> ComputeJobHandle:
        """
        Calls /api/2.1/jobs/runs/get
        """
        resp = self._make_request("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        state = resp.get("state", {})
        life_cycle = state.get("life_cycle_state", "PENDING")
        result_state = state.get("result_state")
        error_msg = state.get("state_message")

        return ComputeJobHandle(
            job_id=job_id,
            run_id=run_id,
            status=life_cycle,
            result_state=result_state,
            error_message=error_msg,
            start_time_epoch_ms=resp.get("start_time"),
            end_time_epoch_ms=resp.get("end_time")
        )

    def cancel_job(self, job_id: str, run_id: str) -> bool:
        """
        Calls /api/2.1/jobs/runs/cancel
        """
        try:
            self._make_request("POST", "/api/2.1/jobs/runs/cancel", {"run_id": int(run_id)})
            return True
        except Exception:
            return False
