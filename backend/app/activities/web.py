import json
import time
import httpx
from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class WebActivity(BaseActivity):
    """
    Web Activity:
    Sends HTTP/HTTPS requests to external endpoints and captures response
    status, JSON/text payloads, and headers for downstream consumption.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_url = config.get("url")
        method = config.get("method", "GET").upper()
        raw_headers = config.get("headers", {})
        raw_body = config.get("body")
        auth_config = config.get("authentication") or {}
        timeout_seconds = max(1, min(int(config.get("timeout_seconds", 30)), 600))
        verify_ssl = not bool(config.get("disable_cert_validation", False))

        if not raw_url:
            raise ValueError("URL is required for WebActivity.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        url = evaluator.evaluate(raw_url)
        headers = evaluator.evaluate(raw_headers) if isinstance(raw_headers, dict) else {}
        body = evaluator.evaluate(raw_body) if raw_body is not None else None

        # Process Authentication
        auth_type = auth_config.get("type", "None").lower()
        client_auth = None
        if auth_type == "basic":
            user = auth_config.get("username", "")
            pwd = auth_config.get("password", "")
            client_auth = (user, pwd)
        elif auth_type == "bearer":
            token = auth_config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "header":
            header_name = auth_config.get("header_name", "X-API-Key")
            header_val = auth_config.get("header_value", "")
            headers[header_name] = header_val

        self.log("INFO", f"Sending HTTP {method} request to {url} (timeout: {timeout_seconds}s)")

        start_time = time.time()
        try:
            with httpx.Client(timeout=timeout_seconds, verify=verify_ssl, follow_redirects=True) as client:
                req_kwargs: Dict[str, Any] = {"headers": headers}
                if client_auth:
                    req_kwargs["auth"] = client_auth

                if body is not None and method in ("POST", "PUT", "PATCH", "DELETE"):
                    if isinstance(body, (dict, list)):
                        req_kwargs["json"] = body
                    else:
                        req_kwargs["content"] = str(body)

                response = client.request(method, url, **req_kwargs)
                duration = round(time.time() - start_time, 2)

                # Attempt JSON decode
                try:
                    response_payload = response.json()
                except Exception:
                    response_payload = response.text

                output_vars = {
                    "response": response_payload,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "duration_seconds": duration
                }

                if response.is_error:
                    error_msg = f"Web request failed with HTTP {response.status_code}: {response.text[:200]}"
                    self.log("ERROR", error_msg)
                    return ActivityExecutionResult(
                        status="Failed",
                        error_message=error_msg,
                        output_variables=output_vars,
                        metrics={"status_code": response.status_code, "duration_seconds": duration}
                    )

                self.log("INFO", f"HTTP {method} to {url} succeeded with HTTP {response.status_code} ({duration}s)")
                return ActivityExecutionResult(
                    status="Succeeded",
                    output_variables=output_vars,
                    metrics={"status_code": response.status_code, "duration_seconds": duration}
                )

        except httpx.TimeoutException:
            duration = round(time.time() - start_time, 2)
            error_msg = f"Web request to {url} timed out after {timeout_seconds}s."
            self.log("ERROR", error_msg)
            return ActivityExecutionResult(
                status="Failed",
                error_message=error_msg,
                metrics={"duration_seconds": duration}
            )
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            self.log("ERROR", f"Web request failed: {str(e)}")
            return ActivityExecutionResult(
                status="Failed",
                error_message=str(e),
                metrics={"duration_seconds": duration}
            )
