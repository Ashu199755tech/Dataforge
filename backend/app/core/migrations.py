from sqlalchemy import text
from backend.app.core.database import engine, Base
import backend.app.models  # Ensure all models are registered with Base.metadata


def run_migrations():
    """
    Idempotent schema migration for PostgreSQL and SQLite.
    Ensures newly added columns in pipeline_runs and activity_runs exist.
    """
    Base.metadata.create_all(bind=engine)

    try:
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                # pipeline_runs additions
                conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS total_bytes_processed BIGINT DEFAULT 0 NOT NULL;"))
                conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS worker_info JSON DEFAULT '{}'::json NOT NULL;"))
                conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS execution_metrics JSON DEFAULT '{}'::json NOT NULL;"))

                # activity_runs additions
                conn.execute(text("ALTER TABLE activity_runs ADD COLUMN IF NOT EXISTS worker_info JSON DEFAULT '{}'::json NOT NULL;"))
                conn.execute(text("ALTER TABLE activity_runs ADD COLUMN IF NOT EXISTS error_classification VARCHAR(50);"))
                conn.execute(text("ALTER TABLE activity_runs ADD COLUMN IF NOT EXISTS error_stack_trace TEXT;"))
                conn.execute(text("ALTER TABLE activity_runs ADD COLUMN IF NOT EXISTS retry_history JSON DEFAULT '[]'::json NOT NULL;"))
                conn.execute(text("ALTER TABLE activity_runs ADD COLUMN IF NOT EXISTS output_variables JSON DEFAULT '{}'::json NOT NULL;"))

                # Phase 10 additions: pipelines, pipeline_runs, pipeline_versions
                conn.execute(text("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS concurrency_limit INTEGER DEFAULT 5 NOT NULL;"))
                conn.execute(text("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS environment_id VARCHAR(36);"))
                conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64);"))
                conn.execute(text("ALTER TABLE pipeline_versions ADD COLUMN IF NOT EXISTS created_by_id VARCHAR(36);"))
                conn.execute(text("ALTER TABLE pipeline_versions ADD COLUMN IF NOT EXISTS git_commit_hash VARCHAR(40);"))
                conn.execute(text("ALTER TABLE pipeline_versions ADD COLUMN IF NOT EXISTS environment_name VARCHAR(50) DEFAULT 'Dev' NOT NULL;"))
                conn.commit()
    except Exception as e:
        print(f"[WARN] Schema migration encountered notice/exception (non-fatal): {e}")
