export interface Workspace {
  id: string;
  name: string;
  description?: string;
  created_at: string;
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description?: string;
  created_at: string;
}

export interface Connection {
  id: string;
  project_id: string;
  name: string;
  connector_type: 'postgres' | 'mysql' | 'sqlite' | string;
  description?: string;
  status: 'Active' | 'Failed' | 'Unverified';
  config_masked: Record<string, any>;
  last_tested_at?: string;
  created_at: string;
}

export interface Trigger {
  id: string;
  pipeline_id?: string;
  name: string;
  description?: string;
  trigger_type: 'manual' | 'schedule' | 'cron' | 'tumbling_window' | 'storage_event' | 'pipeline_dependency';
  pipelines_to_run?: Array<{
    pipeline_id: string;
    pipeline_name?: string;
    parameters?: Record<string, any>;
  }>;
  cron_expression?: string;
  schedule_config?: {
    timezone?: string;
    frequency?: string;
    interval?: number;
    start_time?: string;
    end_time?: string;
  };
  tumbling_window_config?: {
    frequency?: string;
    interval?: number;
    start_time?: string;
    end_time?: string;
    delay_minutes?: number;
    max_concurrency?: number;
    retry_count?: number;
    retry_interval_seconds?: number;
    depends_on_prior_window?: boolean;
  };
  storage_event_config?: {
    connection_id?: string;
    container?: string;
    prefix?: string;
    suffix?: string;
    blob_path_regex?: string;
    event_types?: string[];
    ignore_empty_blobs?: boolean;
  };
  pipeline_dependency_config?: {
    upstream_pipeline_id?: string;
    upstream_pipeline_name?: string;
    fire_on_status?: string[];
    forward_parameters?: boolean;
    timeout_minutes?: number;
  };
  window_state?: Record<string, any>;
  is_active: boolean;
  parameters: Record<string, any>;
  last_fired_at?: string;
  next_fire_time?: string;
  created_at: string;
  updated_at?: string;
}

export interface TriggerRun {
  id: string;
  trigger_id: string;
  run_status: string;
  fired_at: string;
  completed_at?: string;
  duration_ms: number;
  triggered_pipeline_runs: Array<{
    pipeline_id: string;
    pipeline_name?: string;
    pipeline_run_id: string;
    status: string;
  }>;
  event_payload: Record<string, any>;
  error_message?: string;
  created_at: string;
}

export interface ActivityNodeConfig {
  source?: {
    connection_id?: string;
    table_name?: string;
    schema_name?: string;
    batch_size?: number;
    incremental?: {
      mode: 'watermark' | 'full';
      column?: string;
      watermark_value?: string;
    };
  };
  destination?: {
    connection_id?: string;
    table_name?: string;
    schema_name?: string;
    write_mode?: 'append' | 'overwrite' | 'upsert';
    key_columns?: string[];
    auto_create_table?: boolean;
  };
  column_mappings?: Array<{
    source_column: string;
    target_column: string;
  }>;
  sql?: string;
  rules?: Array<{
    rule_type: string;
    column: string;
    threshold_percent: number;
  }>;
}

export interface ActivityDefinition {
  id: string;
  name: string;
  type: 'CopyData' | 'SqlScript' | 'DataQualityCheck';
  depends_on?: Array<{ activity_id: string; condition: string } | string>;
  retry_policy?: {
    max_retries: number;
    retry_interval_seconds: number;
  };
  config: ActivityNodeConfig;
}

export interface PipelineDefinition {
  parameters?: Record<string, any>;
  variables?: Record<string, any>;
  activities: ActivityDefinition[];
  nodes?: any[];
  edges?: any[];
}

export interface Pipeline {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  status: 'Draft' | 'Published' | 'Archived';
  definition_json: PipelineDefinition;
  current_version: number;
  concurrency_limit?: number;
  environment_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineVersion {
  id: string;
  pipeline_id: string;
  version_number: number;
  definition_json: PipelineDefinition;
  changelog?: string;
  environment_name: string;
  git_commit_hash?: string;
  created_at: string;
}

export interface Environment {
  id: string;
  name: string;
  description?: string;
  is_default: boolean;
  variables: Record<string, any>;
  created_at: string;
}

export interface SecretVaultEntry {
  id: string;
  name: string;
  description?: string;
  vault_provider: string;
  is_masked: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuditLog {
  id: number;
  workspace_id?: string;
  user_id?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details: Record<string, any>;
  created_at: string;
}

export interface ActivityRun {
  id: string;
  pipeline_run_id: string;
  activity_id: string;
  activity_name: string;
  activity_type: string;
  status: 'Pending' | 'Running' | 'Succeeded' | 'Failed' | 'Skipped';
  retry_attempt: number;
  rows_read: number;
  rows_written: number;
  bytes_processed: number;
  duration_seconds: number;
  started_at?: string;
  ended_at?: string;
  metrics: Record<string, any>;
  worker_info?: Record<string, any>;
  error_classification?: string;
  error_message?: string;
  error_stack_trace?: string;
  retry_history?: Array<{
    attempt: number;
    status: string;
    timestamp: string;
    duration_ms: number;
    error?: string;
  }>;
  output_variables?: Record<string, any>;
}

export interface PipelineRun {
  id: string;
  pipeline_id: string;
  run_type: string;
  status: 'Pending' | 'Running' | 'Succeeded' | 'Failed' | 'Cancelled';
  parameters: Record<string, any>;
  started_at: string;
  ended_at?: string;
  duration_seconds: number;
  total_activities: number;
  succeeded_activities: number;
  failed_activities: number;
  total_rows_read: number;
  total_rows_written: number;
  total_bytes_processed?: number;
  worker_info?: Record<string, any>;
  execution_metrics?: Record<string, any>;
  error_summary?: string;
  activity_runs: ActivityRun[];
}

export interface TimelineItem {
  activity_id: string;
  activity_name: string;
  activity_type: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number;
  offset_seconds: number;
  start_percentage: number;
  width_percentage: number;
  retry_attempt: number;
  rows_read: number;
  rows_written: number;
  bytes_processed: number;
  error_classification?: string;
  error_message?: string;
  worker_info?: Record<string, any>;
}

export interface AlertRule {
  id: string;
  name: string;
  description?: string;
  target_type: string;
  pipeline_id?: string;
  condition_type: string;
  threshold_value?: number;
  action_type: string;
  action_config: Record<string, any>;
  cooldown_minutes?: number;
  last_triggered_at?: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CopyDataTransferRecord {
  activity_id: string;
  activity_name: string;
  pipeline_run_id: string;
  pipeline_name: string;
  rows_read: number;
  rows_written: number;
  rejected_rows: number;
  bytes_transferred: number;
  bytes_human: string;
  duration_seconds: number;
  throughput_mb_sec: number;
  status: string;
  ended_at: string | null;
}

export interface CopyDataPerformanceMetrics {
  total_copy_activities: number;
  total_rows_transferred: number;
  total_bytes_transferred: number;
  total_bytes_human: string;
  average_throughput_mb_sec: number;
  peak_throughput_mb_sec: number;
  total_rejected_rows: number;
  throughput_trend: Array<{
    hour: string;
    throughput_mb_sec: number;
    bytes_transferred: number;
    rows_transferred: number;
  }>;
  recent_transfers: CopyDataTransferRecord[];
}

export interface RuntimeAgentTelemetry {
  id: string;
  name: string;
  runtime_type: string;
  status: string;
  cpu_cores: number;
  cpu_usage_pct: number;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_usage_pct: number;
  active_tasks: number;
  concurrency_limit: number;
  agent_version?: string;
  agent_os?: string;
  last_heartbeat_at?: string;
}

export interface RuntimeFleetOverview {
  total_runtimes: number;
  online_count: number;
  offline_count: number;
  fleet_cpu_usage_pct: number;
  fleet_memory_usage_pct: number;
  active_tasks: number;
  total_concurrency_capacity: number;
  runtimes: RuntimeAgentTelemetry[];
}

export interface ErrorCluster {
  error_category: string;
  occurrence_count: number;
  first_seen_at?: string;
  last_seen_at?: string;
  sample_error: string;
  affected_pipelines: string[];
  affected_activities: string[];
  suggested_remediation?: string;
}

export interface FailureDiagnosticsResponse {
  period_days: number;
  total_failures: number;
  clusters: ErrorCluster[];
}

export interface OtelSpan {
  trace_id: string;
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: string;
  start_time_iso: string;
  end_time_iso?: string | null;
  duration_ms: number;
  status_code: string;
  status_message?: string | null;
  attributes: Record<string, any>;
  events: Array<Record<string, any>>;
}

export interface OtelTraceResponse {
  trace_id: string;
  pipeline_run_id: string;
  pipeline_name: string;
  status: string;
  start_time: string;
  end_time?: string | null;
  duration_ms: number;
  spans: OtelSpan[];
}

export interface ObservabilityOverview {
  copy_performance: CopyDataPerformanceMetrics;
  fleet_overview: RuntimeFleetOverview;
  failure_diagnostics: FailureDiagnosticsResponse;
  active_runs_count: number;
  success_rate_24h_pct: number;
}

export interface AlertEvent {
  id: string;
  alert_rule_id: string;
  pipeline_run_id?: string;
  activity_run_id?: string;
  title: string;
  severity: 'Critical' | 'Warning' | 'Info';
  message: string;
  payload: Record<string, any>;
  status: 'Triggered' | 'Delivered' | 'Failed';
  delivered_at?: string;
  error_message?: string;
  created_at: string;
}

export interface ExecutionLog {
  id: number;
  level: string;
  message: string;
  timestamp: string;
}

export interface DashboardMetrics {
  pipelines: {
    total: number;
    active: number;
  };
  runs: {
    total: number;
    successful: number;
    failed: number;
    running: number;
    success_rate_percent: number;
  };
  volume: {
    total_rows_read: number;
    total_rows_written: number;
  };
  connections: {
    total: number;
    active: number;
    failed: number;
  };
  recent_activity: Array<{
    id: string;
    pipeline_id: string;
    status: string;
    run_type: string;
    started_at: string;
    duration_seconds: number;
    rows_written: number;
  }>;
}
