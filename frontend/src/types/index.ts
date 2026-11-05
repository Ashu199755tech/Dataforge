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
  created_at: string;
  updated_at: string;
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
  error_message?: string;
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
  error_summary?: string;
  activity_runs: ActivityRun[];
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
