import datetime
import pytest
from backend.app.execution.expressions import (
    ExpressionEvaluator,
    validate_expression,
    EXPRESSION_FUNCTIONS_CATALOG
)


@pytest.fixture
def test_context():
    return ExpressionEvaluator(
        parameters={
            "env": "production",
            "batch_size": 250,
            "region": "us-east",
            "config": {"debug": False, "timeout": 30}
        },
        global_parameters={
            "organization": "Enterprise Data Corp",
            "cluster_tier": "standard"
        },
        variables={
            "watermark": "2026-01-01 00:00:00",
            "retry_count": 2,
            "is_active": True,
            "empty_list": []
        },
        activity_outputs={
            "LookupActivity": {
                "count": 1420,
                "first_row": {
                    "id": 9901,
                    "company": "Acme Global",
                    "tags": ["retail", "vip", "tier1"]
                },
                "status": "COMPLETED"
            }
        },
        pipeline_info={
            "RunId": "run-fedcba-9876",
            "Pipeline": "DailyIngestPipeline",
            "WorkspaceId": "ws-enterprise-01",
            "TriggerType": "Schedule"
        },
        item={"fileName": "orders_20261105.csv", "sizeBytes": 1048576}
    )


def test_parameter_variable_and_system_metadata(test_context):
    # ADF direct parameter syntax
    assert test_context.evaluate("@parameters('env')") == "production"
    assert test_context.evaluate("@parameters('batch_size')") == 250
    assert test_context.evaluate("@parameters('config').timeout") == 30

    # Pipeline object syntax
    assert test_context.evaluate("@pipeline().parameters.env") == "production"
    assert test_context.evaluate("@pipeline().parameters.batch_size") == 250
    assert test_context.evaluate("@pipeline().globalParameters.organization") == "Enterprise Data Corp"

    # System variables
    assert test_context.evaluate("@pipeline().RunId") == "run-fedcba-9876"
    assert test_context.evaluate("@pipeline().Pipeline") == "DailyIngestPipeline"
    assert test_context.evaluate("@pipeline().TriggerType") == "Schedule"

    # Variables
    assert test_context.evaluate("@variables('watermark')") == "2026-01-01 00:00:00"
    assert test_context.evaluate("@variables('retry_count')") == 2

    # Loop item
    assert test_context.evaluate("@item().fileName") == "orders_20261105.csv"
    assert test_context.evaluate("@item().sizeBytes") == 1048576


def test_activity_output_nested_indexing(test_context):
    assert test_context.evaluate("@activity('LookupActivity').output.count") == 1420
    assert test_context.evaluate("@activity('LookupActivity').output.first_row.company") == "Acme Global"
    assert test_context.evaluate("@activity('LookupActivity').output.first_row.tags[0]") == "retail"
    assert test_context.evaluate("@activity('LookupActivity').output.first_row.tags[1]") == "vip"
    assert test_context.evaluate("@activity('LookupActivity').output.first_row.tags[2]") == "tier1"


def test_string_builtins(test_context):
    # concat
    assert test_context.evaluate("@concat('ingest_', parameters('env'), '_', string(parameters('batch_size')))") == "ingest_production_250"

    # substring
    assert test_context.evaluate("@substring('2026-11-05', 0, 4)") == "2026"
    assert test_context.evaluate("@substring('2026-11-05', 5, 2)") == "11"

    # toUpper & toLower & trim
    assert test_context.evaluate("@toUpper(parameters('env'))") == "PRODUCTION"
    assert test_context.evaluate("@toLower('DATAFLOW')") == "dataflow"
    assert test_context.evaluate("@trim('   clean string   ')") == "clean string"

    # replace & split & join
    assert test_context.evaluate("@replace('file_name_raw', '_raw', '_curated')") == "file_name_curated"
    assert test_context.evaluate("@split('a,b,c', ',')") == ["a", "b", "c"]
    assert test_context.evaluate("@join(createArray('x', 'y', 'z'), '/')") == "x/y/z"

    # startsWith, endsWith, contains, length
    assert test_context.evaluate("@startsWith('orders_table', 'orders')") is True
    assert test_context.evaluate("@endsWith('data.parquet', '.parquet')") is True
    assert test_context.evaluate("@contains('enterprise_warehouse', 'prise')") is True
    assert test_context.evaluate("@length('abcdef')") == 6

    # base64 encode/decode & guid
    encoded = test_context.evaluate("@base64('secret_key_123')")
    assert test_context.evaluate(f"@base64ToString('{encoded}')") == "secret_key_123"
    guid_val = test_context.evaluate("@guid()")
    assert isinstance(guid_val, str) and len(guid_val) == 36


def test_math_builtins(test_context):
    assert test_context.evaluate("@add(15, 25)") == 40.0
    assert test_context.evaluate("@sub(100, 35)") == 65.0
    assert test_context.evaluate("@mul(8, 7)") == 56.0
    assert test_context.evaluate("@div(100, 4)") == 25
    assert test_context.evaluate("@mod(17, 5)") == 2.0
    assert test_context.evaluate("@min(12, 5, 88, 3)") == 3
    assert test_context.evaluate("@max(12, 5, 88, 3)") == 88
    assert test_context.evaluate("@abs(-42.5)") == 42.5
    assert test_context.evaluate("@round(3.14159, 2)") == 3.14


def test_logical_and_comparison_builtins(test_context):
    # equals
    assert test_context.evaluate("@equals(parameters('env'), 'production')") is True
    assert test_context.evaluate("@equals(parameters('env'), 'staging')") is False

    # greater, less, greaterOrEquals, lessOrEquals
    assert test_context.evaluate("@greater(activity('LookupActivity').output.count, 1000)") is True
    assert test_context.evaluate("@less(variables('retry_count'), 5)") is True
    assert test_context.evaluate("@greaterOrEquals(250, 250)") is True
    assert test_context.evaluate("@lessOrEquals(10, 20)") is True

    # logical and, or, not
    assert test_context.evaluate("@and(equals(parameters('env'), 'production'), greater(250, 100))") is True
    assert test_context.evaluate("@or(equals(parameters('env'), 'staging'), equals(parameters('env'), 'production'))") is True
    assert test_context.evaluate("@not(equals(parameters('env'), 'staging'))") is True

    # if (ternary)
    assert test_context.evaluate("@if(greater(parameters('batch_size'), 100), 'large_batch', 'small_batch')") == "large_batch"
    assert test_context.evaluate("@if(false, 'yes', 'no')") == "no"


def test_datetime_builtins(test_context):
    now_str = test_context.evaluate("@utcNow('yyyy-MM-dd')")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    assert now_str == today

    # addDays
    future_date = test_context.evaluate("@addDays('2026-01-01', 10, 'yyyy-MM-dd')")
    assert future_date == "2026-01-11"

    # addHours
    res_hour = test_context.evaluate("@addHours('2026-01-01 10:00:00', 5, 'yyyy-MM-dd HH:mm:ss')")
    assert res_hour == "2026-01-01 15:00:00"

    # formatDateTime
    formatted = test_context.evaluate("@formatDateTime('2026-11-05 14:30:00', 'yyyyMMdd')")
    assert formatted == "20261105"

    # dayOfWeek & dayOfMonth
    assert test_context.evaluate("@dayOfMonth('2026-11-05')") == 5


def test_collection_and_null_handling(test_context):
    # array operations
    arr = test_context.evaluate("@createArray('alpha', 'beta', 'gamma')")
    assert arr == ["alpha", "beta", "gamma"]
    assert test_context.evaluate("@first(createArray('first_item', 'second'))") == "first_item"
    assert test_context.evaluate("@last(createArray('first_item', 'second', 'last_item'))") == "last_item"
    assert test_context.evaluate("@take(createArray(1, 2, 3, 4), 2)") == [1, 2]
    assert test_context.evaluate("@skip(createArray(1, 2, 3, 4), 2)") == [3, 4]
    assert test_context.evaluate("@empty(variables('empty_list'))") is True
    assert test_context.evaluate("@empty(createArray('non_empty'))") is False

    # union & intersection
    assert test_context.evaluate("@union(createArray('a', 'b'), createArray('b', 'c'))") == ["a", "b", "c"]
    assert test_context.evaluate("@intersection(createArray('a', 'b', 'c'), createArray('b', 'c', 'd'))") == ["b", "c"]

    # coalesce & null handling
    assert test_context.evaluate("@coalesce(null, null, 'third_non_null')") == "third_non_null"
    assert test_context.evaluate("@coalesce(parameters('missing_param'), 'fallback')") == "fallback"

    # type casting
    assert test_context.evaluate("@int('1234')") == 1234
    assert test_context.evaluate("@float('99.95')") == 99.95
    assert test_context.evaluate("@string(42)") == "42"


def test_string_interpolation_and_escaped_at(test_context):
    # Explicit @{...} interpolation
    interpolated = test_context.evaluate("s3://bucket_@{pipeline().parameters.env}/orders_@{pipeline().RunId}.parquet")
    assert interpolated == "s3://bucket_production/orders_run-fedcba-9876.parquet"

    # Escaped '@@' in ADF
    escaped = test_context.evaluate("@@literal_at_symbol")
    assert escaped == "@literal_at_symbol"


def test_expression_syntax_validation():
    # Valid expressions
    valid, err = validate_expression("@concat('a', 'b')")
    assert valid is True and err is None

    valid, err = validate_expression("@add(1, 2)")
    assert valid is True and err is None

    valid, err = validate_expression("dataset_@{utcNow('yyyyMMdd')}.csv")
    assert valid is True and err is None

    # Invalid expression: unbalanced parentheses
    valid, err = validate_expression("@concat('a', 'b'")
    assert valid is False and err is not None

    # Invalid expression: invalid syntax in @{...}
    valid, err = validate_expression("file_@{add(1,)}.csv")
    assert valid is False and err is not None


def test_expression_functions_catalog():
    assert len(EXPRESSION_FUNCTIONS_CATALOG) >= 25
    categories = {f["category"] for f in EXPRESSION_FUNCTIONS_CATALOG}
    assert "String" in categories
    assert "Math" in categories
    assert "Logical" in categories
    assert "Date & Time" in categories
    assert "System & Scope" in categories
    for fn in EXPRESSION_FUNCTIONS_CATALOG:
        assert "name" in fn
        assert "signature" in fn
        assert "description" in fn
        assert "example" in fn
