from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.execution.expressions import (
    ExpressionEvaluator,
    validate_expression,
    EXPRESSION_FUNCTIONS_CATALOG
)

router = APIRouter(prefix="/expressions", tags=["expressions"])


class ValidateExpressionRequest(BaseModel):
    expression: str


class ValidateExpressionResponse(BaseModel):
    valid: bool
    error: Optional[str] = None


class EvaluateExpressionRequest(BaseModel):
    expression: str
    parameters: Optional[Dict[str, Any]] = None
    global_parameters: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None
    activity_outputs: Optional[Dict[str, Any]] = None
    pipeline_info: Optional[Dict[str, Any]] = None
    item: Optional[Any] = None


class EvaluateExpressionResponse(BaseModel):
    success: bool
    result: Optional[Any] = None
    data_type: str = "null"
    error: Optional[str] = None


@router.get("/functions")
def get_expression_functions() -> List[Dict[str, Any]]:
    """
    Returns the complete catalog of supported ADF functions, signatures,
    and syntax documentation for the frontend expression builder.
    """
    return EXPRESSION_FUNCTIONS_CATALOG


@router.post("/validate", response_model=ValidateExpressionResponse)
def validate_expression_syntax(payload: ValidateExpressionRequest):
    """
    Validates syntax and token structure of an ADF dynamic content expression.
    """
    is_valid, err = validate_expression(payload.expression)
    return ValidateExpressionResponse(valid=is_valid, error=err)


@router.post("/evaluate", response_model=EvaluateExpressionResponse)
def evaluate_expression_preview(payload: EvaluateExpressionRequest):
    """
    Evaluates an expression with runtime context simulation for interactive debugging.
    """
    try:
        evaluator = ExpressionEvaluator(
            parameters=payload.parameters or {},
            global_parameters=payload.global_parameters or {},
            variables=payload.variables or {},
            activity_outputs=payload.activity_outputs or {},
            item=payload.item,
            pipeline_info=payload.pipeline_info or {}
        )
        res = evaluator.evaluate(payload.expression)
        dtype = type(res).__name__ if res is not None else "null"
        return EvaluateExpressionResponse(success=True, result=res, data_type=dtype)
    except Exception as e:
        return EvaluateExpressionResponse(success=False, error=str(e), data_type="error")
