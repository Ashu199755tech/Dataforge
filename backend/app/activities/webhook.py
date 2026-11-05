import time
import uuid
import httpx
from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.callbacks import callback_store
from backend.app.execution.expressions import ExpressionEvaluator


class WebhookActivity(BaseActivity):
    """
    Webhook Activity:
    Invokes an external endpoint with an injected callback URL, pauses pipeline
    execution, and awaits an asynchronous callback response from the external system.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_url = config.get("url")
        method = config.get("method", "POST").upper()
        raw_headers = config.get("headers", {})
        raw_body = config.get("body", {})
        callback_param_name = config.get("callback_param_name", "callBackUri")
        callback_base_url = config.get("callback_base_url", "http://127.0.0.1:8000").rstrip("/")
        timeout_seconds = max(5, min(int(config.get("timeout_seconds", 300)), 86400))
        verify_ssl = not bool(config.get("disable_cert_validation", False))

        if not raw_url:
            raise ValueError("Target 'url' is required for WebhookActivity.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        url = evaluator.evaluate(raw_url)
        headers = evaluator.evaluate(raw_headers) if isinstance(raw_headers, dict) else {}
        body = evaluator.evaluate(raw_body) if isinstance(raw_body, dict) else {}

        # 1. Generate unique callback identifier & URL
        callback_id = str(uuid.uuid4())
        callback_url = f"{callback_base_url}/api/v1/callbacks/{callback_id}"

        # 2. Inject callback URL into request body
        if isinstance(body, dict):
            body[callback_param_name] = callback_url
        elif isinstance(body, str):
            body = f"{body}&{callback_param_name}={callback_url}"

        # 3. Register callback listener
        callback_store.register(callback_id)
        self.log("INFO", f"Registered Webhook callback ID: {callback_id}")

        # 4. Fire initial notification to external service
        start_time = time.time()
        try:
            with httpx.Client(timeout=30, verify=verify_ssl, follow_redirects=True) as client:
                resp = client.request(method, url, json=body if isinstance(body, dict) else None, data=body if isinstance(body, str) else None, headers=headers)
                if resp.is_error:
                    error_msg = f"Webhook trigger request failed with HTTP {resp.status_code}: {resp.text[:200]}"
                    self.log("ERROR", error_msg)
                    return ActivityExecutionResult(
                        status="Failed",
                        error_message=error_msg,
                        metrics={"trigger_status_code": resp.status_code}
                    )

            self.log("INFO", f"Webhook trigger dispatched to {url}. Waiting up to {timeout_seconds}s for external callback...")

            # 5. Await asynchronous callback
            callback_payload = callback_store.wait(callback_id, timeout_seconds=timeout_seconds)
            duration = round(time.time() - start_time, 2)

            if callback_payload is None:
                error_msg = f"Webhook activity timed out after {timeout_seconds}s awaiting external callback."
                self.log("ERROR", error_msg)
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=error_msg,
                    metrics={"duration_seconds": duration, "is_timeout": True}
                )

            self.log("INFO", f"Asynchronous webhook callback received successfully in {duration}s")
            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={
                    "callback_data": callback_payload,
                    "callback_id": callback_id,
                    "duration_seconds": duration
                },
                metrics={"duration_seconds": duration}
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            self.log("ERROR", f"Webhook activity failed: {str(e)}")
            return ActivityExecutionResult(
                status="Failed",
                error_message=str(e),
                metrics={"duration_seconds": duration}
            )
