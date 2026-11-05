import pytest
from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext, ActivityExecutionResult
from backend.app.activities.registry import activity_registry, ActivityMetadata
from backend.app.activities.factory import get_activity_instance
from backend.app.core.database import SessionLocal


def test_builtin_activities_registered():
    """Verify that all core built-in activities are registered in the global ActivityRegistry."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}

    expected_types = {
        "CopyData",
        "Lookup",
        "DataQualityCheck",
        "IfCondition",
        "SetVariable",
        "Wait",
        "SqlScript",
        "RestApi"
    }

    assert expected_types.issubset(types), f"Missing activities: {expected_types - types}"

    # Verify metadata fields
    copy_meta = activity_registry.get_metadata("CopyData")
    assert copy_meta is not None
    assert copy_meta.display_name == "Copy Data"
    assert copy_meta.category == "Move & Transform"
    assert "source" in copy_meta.config_schema.get("required", [])
    assert copy_meta.supports_retry is True


def test_activity_alias_resolution():
    """Verify that case variations and aliases resolve to the correct executor class."""
    db: Session = SessionLocal()
    try:
        # Test copy_data alias
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_1",
            activity_name="Test Copy",
            activity_type="copy_data",
            config={"source": {}, "destination": {}}
        )
        instance = get_activity_instance(ctx, db)
        assert instance.__class__.__name__ == "CopyDataActivity"

        # Test waitactivity alias (case insensitive)
        ctx_wait = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_2",
            activity_name="Test Wait",
            activity_type="WaitActivity",
            config={"wait_time_in_seconds": 1}
        )
        instance_wait = get_activity_instance(ctx_wait, db)
        assert instance_wait.__class__.__name__ == "WaitActivity"
    finally:
        db.close()


def test_dynamic_plugin_registration():
    """
    Acceptance Criteria Test:
    Verify that a new custom/plugin activity can be registered dynamically
    and executed without modifying any core orchestrator or engine code.
    """
    @activity_registry.register_activity(
        activity_type="CustomPluginSample",
        display_name="Custom Plugin Sample",
        category="Compute & External",
        description="Dynamic plugin activity registered at runtime",
        version="1.0.0",
        icon="Cpu",
        config_schema={
            "type": "object",
            "required": ["multiplier"]
        },
        aliases=["sample_plugin"]
    )
    class CustomPluginSampleActivity(BaseActivity):
        def execute(self) -> ActivityExecutionResult:
            multiplier = self.context.config.get("multiplier", 1)
            self.log("INFO", f"Executing custom plugin with multiplier {multiplier}")
            return ActivityExecutionResult(
                status="Succeeded",
                rows_written=10 * multiplier,
                output_variables={"plugin_result": 42 * multiplier}
            )

    # 1. Verify discovery in catalog
    meta = activity_registry.get_metadata("CustomPluginSample")
    assert meta is not None
    assert meta.display_name == "Custom Plugin Sample"
    assert meta.category == "Compute & External"

    # 2. Verify instantiation via factory/registry
    db: Session = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_plugin_test",
            activity_id="act_plugin",
            activity_name="Sample Plugin Node",
            activity_type="sample_plugin",  # via alias
            config={"multiplier": 3}
        )
        instance = get_activity_instance(ctx, db)
        assert isinstance(instance, CustomPluginSampleActivity)

        # 3. Verify successful execution
        result = instance.execute()
        assert result.status == "Succeeded"
        assert result.rows_written == 30
        assert result.output_variables["plugin_result"] == 126
    finally:
        db.close()


def test_config_schema_validation():
    """Verify that configuration validation detects missing required fields."""
    # Valid CopyData config
    valid, err = activity_registry.validate_config("CopyData", {
        "source": {"table_name": "users"},
        "destination": {"table_name": "dest_users"}
    })
    assert valid is True
    assert err is None

    # Invalid CopyData config (missing destination)
    invalid, err = activity_registry.validate_config("CopyData", {
        "source": {"table_name": "users"}
    })
    assert invalid is False
    assert "Missing required configuration field: 'destination'" in err


def test_unknown_activity_raises_error():
    """Verify that attempting to instantiate an unregistered activity raises ValueError."""
    db: Session = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_invalid",
            activity_name="Unknown Node",
            activity_type="NonExistentActivityType",
            config={}
        )
        with pytest.raises(ValueError, match="Unknown or unsupported activity type"):
            get_activity_instance(ctx, db)
    finally:
        db.close()
