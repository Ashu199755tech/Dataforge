from backend.app.execution.expressions import ExpressionEvaluator


def test_expression_evaluator():
    evaluator = ExpressionEvaluator(
        parameters={"env": "staging", "limit": 100},
        variables={"watermark": "2026-01-01 00:00:00", "is_active": True},
        activity_outputs={
            "act_lookup": {
                "count": 42,
                "first_row": {"id": 999, "name": "Acme Global"}
            }
        }
    )

    # Parameter resolution
    assert evaluator.evaluate("@parameters('env')") == "staging"
    assert evaluator.evaluate("@parameters('limit')") == 100

    # Variable resolution
    assert evaluator.evaluate("@variables('watermark')") == "2026-01-01 00:00:00"

    # Activity output resolution
    assert evaluator.evaluate("@activity('act_lookup').output.count") == 42
    assert evaluator.evaluate("@activity('act_lookup').output.first_row") == {"id": 999, "name": "Acme Global"}

    # Equality check
    assert evaluator.evaluate("@equals(@parameters('env'), 'staging')") is True
    assert evaluator.evaluate("@equals(@parameters('env'), 'prod')") is False

    # Comparison check
    assert evaluator.evaluate("@greater(@activity('act_lookup').output.count, 10)") is True
    assert evaluator.evaluate("@greater(@activity('act_lookup').output.count, 50)") is False

    # Concat
    assert evaluator.evaluate("@concat('data_', @parameters('env'))") == "data_staging"

    # Dictionary recursion
    config = {
        "target": "@concat('tbl_', @parameters('env'))",
        "nested": {
            "val": "@variables('watermark')"
        }
    }
    resolved = evaluator.evaluate(config)
    assert resolved["target"] == "tbl_staging"
    assert resolved["nested"]["val"] == "2026-01-01 00:00:00"
