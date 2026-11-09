import time
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Iterator, Optional

from backend.app.connectors.base import (
    BaseConnector,
    ColumnMetadata,
    TableMetadata,
    ConnectionTestResult
)


class ReverseETLConnector(BaseConnector):
    """
    Enterprise Reverse ETL Connector.
    Synchronizes transformed analytical models (from Snowflake, DuckDB, BigQuery, Redshift, Postgres)
    directly into downstream operational SaaS applications:
      1. Salesforce (SObjects REST API with external ID upsert)
      2. HubSpot (CRM v3 Batch Upsert API)
      3. Slack (Operational alerts, metric cards, channel notifications)
      4. Webhook (Generic REST dispatch with custom authorization headers and payloads)
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.destination_type = str(config.get("destination_type") or config.get("target_app") or "webhook").lower().strip()
        self.mock_mode = config.get("mock_mode", False)
        
        # Salesforce Config
        self.sf_instance_url = config.get("instance_url", "").rstrip("/")
        self.sf_access_token = config.get("access_token") or config.get("token")
        self.sf_api_version = config.get("api_version", "v58.0")

        # HubSpot Config
        self.hubspot_token = config.get("hubspot_token") or config.get("api_token") or config.get("token")

        # Slack Config
        self.slack_webhook_url = config.get("webhook_url") or config.get("slack_webhook")
        self.slack_channel = config.get("channel", "#general")

        # Generic Webhook Config
        self.webhook_url = config.get("url") or config.get("webhook_url")
        self.webhook_method = config.get("method", "POST").upper()
        self.webhook_headers = config.get("headers", {})

        # Storage for mock test verification
        self._mock_synced_records: List[Dict[str, Any]] = []

    def test_connection(self) -> ConnectionTestResult:
        start_time = time.time()
        if self.mock_mode:
            return ConnectionTestResult(
                success=True,
                message=f"Connected to Reverse ETL Destination '{self.destination_type.upper()}' (Mock Mode)",
                latency_ms=14.2,
                server_version=f"{self.destination_type.title()} API v1"
            )

        if self.destination_type == "salesforce":
            if not self.sf_instance_url or not self.sf_access_token:
                return ConnectionTestResult(
                    success=False,
                    message="Salesforce requires 'instance_url' and 'access_token'."
                )
            try:
                # Query Salesforce versions to verify connectivity
                url = f"{self.sf_instance_url}/services/data/{self.sf_api_version}/sobjects"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.sf_access_token}"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    latency = (time.time() - start_time) * 1000.0
                    return ConnectionTestResult(
                        success=True,
                        message=f"Connected successfully to Salesforce instance '{self.sf_instance_url}'.",
                        latency_ms=round(latency, 2),
                        server_version=f"Salesforce REST {self.sf_api_version}"
                    )
            except Exception as ex:
                return ConnectionTestResult(success=False, message=f"Salesforce connection failed: {str(ex)}")

        elif self.destination_type == "hubspot":
            if not self.hubspot_token:
                return ConnectionTestResult(success=False, message="HubSpot requires 'hubspot_token' / Private App Token.")
            return ConnectionTestResult(
                success=True,
                message="HubSpot Private App Token configured.",
                latency_ms=12.0,
                server_version="HubSpot CRM v3"
            )

        elif self.destination_type == "slack":
            if not self.slack_webhook_url:
                return ConnectionTestResult(success=False, message="Slack destination requires 'webhook_url'.")
            return ConnectionTestResult(
                success=True,
                message=f"Slack destination configured for channel '{self.slack_channel}'.",
                latency_ms=8.5,
                server_version="Slack Incoming Webhook"
            )

        elif self.destination_type == "webhook":
            if not self.webhook_url:
                return ConnectionTestResult(success=False, message="Webhook destination requires target 'url'.")
            return ConnectionTestResult(
                success=True,
                message=f"Webhook endpoint configured ({self.webhook_method} {self.webhook_url}).",
                latency_ms=5.0,
                server_version="HTTP Webhook"
            )

        return ConnectionTestResult(
            success=False,
            message=f"Unsupported Reverse ETL destination type '{self.destination_type}'."
        )

    def discover_schemas(self) -> List[str]:
        if self.destination_type == "salesforce":
            return ["Contact", "Lead", "Account", "Opportunity", "CustomObject__c"]
        elif self.destination_type == "hubspot":
            return ["contacts", "companies", "deals", "tickets"]
        elif self.destination_type == "slack":
            return [self.slack_channel]
        return ["default"]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        schemas = self.discover_schemas()
        return [
            TableMetadata(
                name=s,
                schema_name=self.destination_type,
                table_type="REVERSE_ETL_SINK",
                columns=self.discover_columns(s)
            )
            for s in schemas
        ]

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        if self.destination_type == "salesforce":
            return [
                ColumnMetadata(name="Id", data_type="id", is_nullable=True, is_primary_key=True),
                ColumnMetadata(name="External_Id__c", data_type="string", is_nullable=False),
                ColumnMetadata(name="Email", data_type="email", is_nullable=True),
                ColumnMetadata(name="Name", data_type="string", is_nullable=True)
            ]
        elif self.destination_type == "hubspot":
            return [
                ColumnMetadata(name="id", data_type="string", is_nullable=True, is_primary_key=True),
                ColumnMetadata(name="email", data_type="string", is_nullable=False),
                ColumnMetadata(name="firstname", data_type="string", is_nullable=True),
                ColumnMetadata(name="lastname", data_type="string", is_nullable=True),
                ColumnMetadata(name="company", data_type="string", is_nullable=True)
            ]
        elif self.destination_type == "slack":
            return [
                ColumnMetadata(name="text", data_type="string", is_nullable=False),
                ColumnMetadata(name="channel", data_type="string", is_nullable=True)
            ]
        return [
            ColumnMetadata(name="id", data_type="string", is_nullable=True, is_primary_key=True),
            ColumnMetadata(name="payload", data_type="json", is_nullable=False)
        ]

    def sync_batch(
        self,
        records: List[Dict[str, Any]],
        object_name: str,
        sync_mode: str = "upsert",
        external_id_field: Optional[str] = None,
        field_mappings: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a batch of records to the target operational SaaS platform.
        """
        if not records:
            return {"synced": 0, "failed": 0, "errors": []}

        # Apply field mappings
        transformed_records = []
        for r in records:
            mapped_row = {}
            if field_mappings:
                for m in field_mappings:
                    src = m.get("source")
                    dst = m.get("destination") or src
                    if src in r:
                        mapped_row[dst] = r[src]
            else:
                mapped_row = dict(r)
            transformed_records.append(mapped_row)

        if self.mock_mode:
            self._mock_synced_records.extend(transformed_records)
            return {
                "synced": len(transformed_records),
                "failed": 0,
                "errors": [],
                "destination": self.destination_type,
                "object": object_name
            }

        if self.destination_type == "salesforce":
            return self._sync_salesforce(transformed_records, object_name, external_id_field)
        elif self.destination_type == "hubspot":
            return self._sync_hubspot(transformed_records, object_name, external_id_field)
        elif self.destination_type == "slack":
            return self._sync_slack(transformed_records, object_name)
        else:
            return self._sync_webhook(transformed_records, object_name)

    def _sync_salesforce(self, records: List[Dict[str, Any]], object_name: str, external_id_field: Optional[str]) -> Dict[str, Any]:
        id_field = external_id_field or "External_Id__c"
        synced = 0
        failed = 0
        errors = []

        headers = {
            "Authorization": f"Bearer {self.sf_access_token}",
            "Content-Type": "application/json",
            "User-Agent": "DataForge-ReverseETL/1.0"
        }

        for r in records:
            ext_val = r.get(id_field)
            if ext_val:
                url = f"{self.sf_instance_url}/services/data/{self.sf_api_version}/sobjects/{object_name}/{id_field}/{ext_val}"
                method = "PATCH"
            else:
                url = f"{self.sf_instance_url}/services/data/{self.sf_api_version}/sobjects/{object_name}"
                method = "POST"

            body_bytes = json.dumps(r).encode("utf-8")
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30):
                    synced += 1
            except urllib.error.HTTPError as e:
                failed += 1
                errors.append(f"Salesforce error ({e.code}): {e.read().decode('utf-8')[:200]}")
            except Exception as ex:
                failed += 1
                errors.append(str(ex))

        return {"synced": synced, "failed": failed, "errors": errors, "destination": "salesforce", "object": object_name}

    def _sync_hubspot(self, records: List[Dict[str, Any]], object_name: str, external_id_field: Optional[str]) -> Dict[str, Any]:
        url = f"https://api.hubapi.com/crm/v3/objects/{object_name}/batch/upsert"
        id_prop = external_id_field or "email"
        inputs = []
        for r in records:
            inputs.append({
                "id": str(r.get(id_prop, "")),
                "idProperty": id_prop,
                "properties": r
            })

        headers = {
            "Authorization": f"Bearer {self.hubspot_token}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, data=json.dumps({"inputs": inputs}).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30):
                return {"synced": len(records), "failed": 0, "errors": [], "destination": "hubspot", "object": object_name}
        except Exception as ex:
            return {"synced": 0, "failed": len(records), "errors": [str(ex)], "destination": "hubspot", "object": object_name}

    def _sync_slack(self, records: List[Dict[str, Any]], object_name: str) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        summary_text = f":white_check_mark: *DataForge Reverse ETL Sync: {object_name}*\nDispatched {len(records)} updated operational records."
        if len(records) <= 3:
            summary_text += "\n" + "\n".join([f"• `{json.dumps(r)}`" for r in records])

        payload = {"text": summary_text, "channel": self.slack_channel}
        req = urllib.request.Request(self.slack_webhook_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15):
                return {"synced": len(records), "failed": 0, "errors": [], "destination": "slack", "object": object_name}
        except Exception as ex:
            return {"synced": 0, "failed": len(records), "errors": [str(ex)], "destination": "slack", "object": object_name}

    def _sync_webhook(self, records: List[Dict[str, Any]], object_name: str) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json", **self.webhook_headers}
        payload = {"object": object_name, "count": len(records), "records": records}
        req = urllib.request.Request(self.webhook_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method=self.webhook_method)
        try:
            with urllib.request.urlopen(req, timeout=30):
                return {"synced": len(records), "failed": 0, "errors": [], "destination": "webhook", "object": object_name}
        except Exception as ex:
            return {"synced": 0, "failed": len(records), "errors": [str(ex)], "destination": "webhook", "object": object_name}

    def read_data_stream(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[Any] = None,
        batch_size: int = 5000,
        schema_name: Optional[str] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        if self._mock_synced_records:
            yield list(self._mock_synced_records)

    def write_data_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        write_mode: str = "append",
        key_columns: Optional[List[str]] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
        schema_name: Optional[str] = None,
        auto_create_table: bool = True
    ) -> int:
        res = self.sync_batch(
            records=records,
            object_name=table_name,
            sync_mode=write_mode,
            external_id_field=key_columns[0] if key_columns else None,
            field_mappings=column_mappings
        )
        return res.get("synced", 0)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return [{"destination_type": self.destination_type, "synced_count": len(self._mock_synced_records)}]
