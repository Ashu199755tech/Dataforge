import time
import httpx
from typing import Dict, Any
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class RestApiActivity(BaseActivity):
    """
    REST API Activity: Makes outbound HTTP requests to external web services,
    microservices, webhooks, or alerting endpoints.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )

        url = evaluator.evaluate(config.get("url"))
        method = config.get("method", "GET").upper()
        headers = evaluator.evaluate(config.get("headers", {}))
        body = evaluator.evaluate(config.get("body", None))
        timeout = float(config.get("timeout_seconds", 30))

        if not url:
            raise ValueError("REST API activity requires a 'url'.")

        self.log("INFO", f"Sending {method} request to {url}")
        start = time.time()

        try:
            with httpx.Client(timeout=timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=body if isinstance(body, dict) else None, data=body if isinstance(body, str) else None)
                elif method == "PUT":
                    response = client.put(url, headers=headers, json=body if isinstance(body, dict) else None)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

            latency = round((time.time() - start) * 1000, 2)
            self.log("INFO", f"Response: HTTP {response.status_code} in {latency}ms")

            is_success = 200 <= response.status_code < 300

            try:
                response_json = response.json()
            except Exception:
                response_json = {"text": response.text[:2000]}

            return ActivityExecutionResult(
                status="Succeeded" if is_success else "Failed",
                output_variables={
                    "status_code": response.status_code,
                    "response": response_json
                },
                metrics={
                    "status_code": response.status_code,
                    "latency_ms": latency
                },
                error_message=None if is_success else f"HTTP error {response.status_code}: {response.text[:200]}"
            )
        except Exception as e:
            self.log("ERROR", f"HTTP Request failed: {str(e)}")
            raise
