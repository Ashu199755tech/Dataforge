import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.models.data_quality import DataQualityResult


class AlertEngine:
    """
    Evaluates enterprise alert rules against execution states
    and dispatches notifications across Webhooks, Slack, and Event Logs.
    """

    @staticmethod
    def evaluate_pipeline_run(pipeline_run: PipelineRun, db: Session) -> List[AlertEvent]:
        """Evaluates all matching alert rules when a pipeline run finishes."""
        triggered_events: List[AlertEvent] = []

        # Find rules matching pipeline_id or global rules
        rules = db.query(AlertRule).filter(
            AlertRule.is_enabled == True,
            (AlertRule.pipeline_id == pipeline_run.pipeline_id) | (AlertRule.target_type == "Global")
        ).all()

        for rule in rules:
            is_triggered = False
            title = ""
            severity = "Warning"
            message = ""

            cond = rule.condition_type

            if cond == "OnFailure" and pipeline_run.status == "Failed":
                is_triggered = True
                severity = "Critical"
                title = f"Pipeline Execution Failed: {pipeline_run.pipeline_id}"
                message = f"Pipeline run '{pipeline_run.id}' failed. Error summary: {pipeline_run.error_summary or 'No error summary provided.'}"

            elif cond == "OnSuccess" and pipeline_run.status == "Succeeded":
                is_triggered = True
                severity = "Info"
                title = f"Pipeline Execution Succeeded: {pipeline_run.pipeline_id}"
                message = f"Pipeline run '{pipeline_run.id}' completed successfully in {pipeline_run.duration_seconds}s."

            elif cond in ("DurationExceeded", "SLAThreshold"):
                threshold = float(rule.threshold_value or 0)
                if pipeline_run.duration_seconds > threshold:
                    is_triggered = True
                    severity = "Warning"
                    title = f"SLA / Duration Threshold Exceeded: {pipeline_run.pipeline_id}"
                    message = f"Pipeline run '{pipeline_run.id}' duration ({pipeline_run.duration_seconds}s) exceeded SLA threshold of {threshold}s."

            elif cond == "DQScoreThreshold":
                # Check DataQualityResults for this run
                dq_results = db.query(DataQualityResult).filter(
                    DataQualityResult.pipeline_run_id == pipeline_run.id
                ).all()
                if dq_results:
                    scores = [r.dq_score for r in dq_results if r.dq_score is not None]
                    if scores:
                        avg_score = sum(scores) / len(scores)
                        min_threshold = float(rule.threshold_value or 80.0)
                        if avg_score < min_threshold:
                            is_triggered = True
                            severity = "Critical"
                            title = f"Data Quality Threshold Breach: {pipeline_run.pipeline_id}"
                            message = f"Pipeline run '{pipeline_run.id}' average DQ score {round(avg_score, 1)}% fell below minimum threshold {min_threshold}%."

            if is_triggered:
                event = AlertEvent(
                    alert_rule_id=rule.id,
                    pipeline_run_id=pipeline_run.id,
                    title=title,
                    severity=severity,
                    message=message,
                    payload={
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "pipeline_id": pipeline_run.pipeline_id,
                        "run_id": pipeline_run.id,
                        "status": pipeline_run.status,
                        "duration_seconds": pipeline_run.duration_seconds,
                        "rows_written": pipeline_run.total_rows_written,
                        "action_type": rule.action_type
                    },
                    status="Triggered"
                )
                db.add(event)
                db.commit()
                db.refresh(event)

                # Dispatch notification
                AlertEngine.dispatch_notification(event, rule, db)
                triggered_events.append(event)

        return triggered_events

    @staticmethod
    def dispatch_notification(event: AlertEvent, rule: AlertRule, db: Session):
        """Dispatches an alert notification to the configured target (Webhook, Slack, Log)."""
        action_type = (rule.action_type or "Log").lower()
        config = rule.action_config or {}

        try:
            if action_type in ("webhook", "slack"):
                webhook_url = config.get("webhook_url") or config.get("url")
                if webhook_url:
                    payload_data = {
                        "event_id": event.id,
                        "title": event.title,
                        "severity": event.severity,
                        "message": event.message,
                        "text": f"*{event.title}* [{event.severity}]\n{event.message}",
                        "timestamp": event.created_at.isoformat() if event.created_at else datetime.now(timezone.utc).isoformat(),
                        "payload": event.payload
                    }
                    req = urllib.request.Request(
                        webhook_url,
                        data=json.dumps(payload_data).encode("utf-8"),
                        headers={"Content-Type": "application/json", "User-Agent": "DataFlow-Enterprise-AlertEngine"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=5) as response:
                        if 200 <= response.status < 300:
                            event.status = "Delivered"
                            event.delivered_at = datetime.now(timezone.utc)
                        else:
                            event.status = "Failed"
                            event.error_message = f"Webhook HTTP status {response.status}"
                else:
                    event.status = "Delivered"
                    event.delivered_at = datetime.now(timezone.utc)
            else:
                # Default "log"
                print(f"[ALERT DISPATCH] [{event.severity}] {event.title} - {event.message}")
                event.status = "Delivered"
                event.delivered_at = datetime.now(timezone.utc)

        except Exception as e:
            event.status = "Failed"
            event.error_message = f"Dispatch failed: {str(e)}"
        finally:
            db.commit()
