from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.sql_script import SqlScriptActivity
from backend.app.activities.dq_check import DataQualityCheckActivity


def get_activity_instance(context: ActivityExecutionContext, db: Session) -> BaseActivity:
    atype = context.activity_type.lower()
    if atype in ("copydata", "copy_data", "copy"):
        return CopyDataActivity(context, db)
    elif atype in ("sqlscript", "sql_script", "sql"):
        return SqlScriptActivity(context, db)
    elif atype in ("dataqualitycheck", "dq_check", "data_quality"):
        return DataQualityCheckActivity(context, db)
    else:
        raise ValueError(f"Unknown or unsupported activity type: '{context.activity_type}'")
