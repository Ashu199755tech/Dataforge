from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.sql_script import SqlScriptActivity
from backend.app.activities.dq_check import DataQualityCheckActivity
from backend.app.activities.lookup import LookupActivity
from backend.app.activities.set_variable import SetVariableActivity
from backend.app.activities.wait import WaitActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.activities.rest_api import RestApiActivity


def get_activity_instance(context: ActivityExecutionContext, db: Session) -> BaseActivity:
    atype = context.activity_type.lower()
    if atype in ("copydata", "copy_data", "copy"):
        return CopyDataActivity(context, db)
    elif atype in ("sqlscript", "sql_script", "sql"):
        return SqlScriptActivity(context, db)
    elif atype in ("dataqualitycheck", "dq_check", "data_quality"):
        return DataQualityCheckActivity(context, db)
    elif atype in ("lookup", "lookupactivity"):
        return LookupActivity(context, db)
    elif atype in ("setvariable", "set_variable"):
        return SetVariableActivity(context, db)
    elif atype in ("wait", "waitactivity"):
        return WaitActivity(context, db)
    elif atype in ("ifcondition", "if_condition", "if"):
        return IfConditionActivity(context, db)
    elif atype in ("restapi", "rest_api", "web", "http"):
        return RestApiActivity(context, db)
    else:
        raise ValueError(f"Unknown or unsupported activity type: '{context.activity_type}'")
