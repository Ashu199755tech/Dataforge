import re
from typing import Any, Dict, List, Optional


class ExpressionEvaluator:
    """
    Evaluates dynamic expressions within pipeline configurations.
    Supported syntaxes:
      @parameters('name')
      @variables('name')
      @activity('name').output.path.to.field
      @equals(a, b)
      @greater(a, b)
      @less(a, b)
      @not(a)
      @concat(a, b, c)
    """

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
        activity_outputs: Optional[Dict[str, Any]] = None,
        item: Optional[Any] = None,
        pipeline_info: Optional[Dict[str, Any]] = None
    ):
        self.parameters = parameters or {}
        self.variables = variables or {}
        self.activity_outputs = activity_outputs or {}
        self.item = item
        self.pipeline_info = pipeline_info or {}

    def evaluate(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self.evaluate(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.evaluate(v) for v in value]
        elif isinstance(value, str):
            return self._evaluate_string(value)
        return value

    def _evaluate_string(self, expr_str: str) -> Any:
        expr_str = expr_str.strip()

        # Support ADF nested function calls that omit the leading '@' inside outer expressions
        if expr_str.startswith((
            "activity(", "parameters(", "variables(", "item(", "pipeline(",
            "equals(", "greater(", "less(", "not(", "concat("
        )):
            expr_str = "@" + expr_str

        if not expr_str.startswith("@"):
            return expr_str

        # Exact parameter expression: @parameters('name')
        match_param = re.fullmatch(r"@parameters\('([^']+)'\)", expr_str)
        if match_param:
            param_key = match_param.group(1)
            return self.parameters.get(param_key)

        # Exact variable expression: @variables('name')
        match_var = re.fullmatch(r"@variables\('([^']+)'\)", expr_str)
        if match_var:
            var_key = match_var.group(1)
            return self.variables.get(var_key)

        # Loop item expression: @item() or @item().prop.nested
        match_item = re.fullmatch(r"@item\(\)(?:\.([a-zA-Z0-9_.]+))?", expr_str)
        if match_item:
            field_path = match_item.group(1)
            val = self.item
            if field_path and isinstance(val, dict):
                for part in field_path.split("."):
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = None
                        break
            return val

        # Pipeline runtime metadata: @pipeline().RunId, @pipeline().Pipeline
        match_pipe = re.fullmatch(r"@pipeline\(\)(?:\.([a-zA-Z0-9_.]+))?", expr_str)
        if match_pipe:
            field_path = match_pipe.group(1) or "RunId"
            return self.pipeline_info.get(field_path)

        # Exact activity output expression with arbitrary nested dot notation:
        # e.g., @activity('act_lookup').output.first_row.max_date
        match_act = re.fullmatch(r"@activity\('([^']+)'\)\.output(?:\.([a-zA-Z0-9_.]+))?", expr_str)
        if match_act:
            act_id = match_act.group(1)
            field_path = match_act.group(2)
            out = self.activity_outputs.get(act_id, {})
            if field_path:
                for part in field_path.split("."):
                    if isinstance(out, dict):
                        out = out.get(part)
                    else:
                        out = None
                        break
                return out
            return out

        # Equality expression: @equals(val1, val2)
        match_equals = re.fullmatch(r"@equals\((.+),\s*(.+)\)", expr_str)
        if match_equals:
            val1 = self.evaluate(match_equals.group(1).strip())
            val2 = self.evaluate(match_equals.group(2).strip())
            return str(val1).strip("'\"") == str(val2).strip("'\"")

        # Greater comparison: @greater(val1, val2)
        match_greater = re.fullmatch(r"@greater\((.+),\s*(.+)\)", expr_str)
        if match_greater:
            raw1 = self.evaluate(match_greater.group(1).strip())
            raw2 = self.evaluate(match_greater.group(2).strip())
            try:
                return float(raw1) > float(raw2)
            except (ValueError, TypeError):
                return False

        # Less comparison: @less(val1, val2)
        match_less = re.fullmatch(r"@less\((.+),\s*(.+)\)", expr_str)
        if match_less:
            raw1 = self.evaluate(match_less.group(1).strip())
            raw2 = self.evaluate(match_less.group(2).strip())
            try:
                return float(raw1) < float(raw2)
            except (ValueError, TypeError):
                return False

        # Boolean negation: @not(val)
        match_not = re.fullmatch(r"@not\((.+)\)", expr_str)
        if match_not:
            val = self.evaluate(match_not.group(1).strip())
            return not bool(val)

        # String concatenation: @concat(a, b, c)
        match_concat = re.fullmatch(r"@concat\((.+)\)", expr_str)
        if match_concat:
            parts = [p.strip().strip("'\"") for p in match_concat.group(1).split(",")]
            evaluated_parts = [str(self.evaluate(p)).strip("'\"") for p in parts]
            return "".join(evaluated_parts)

        # Fallback: String interpolation for embedded expressions in text
        def _replace_embedded(m):
            sub_expr = m.group(0)
            res = self._evaluate_string(sub_expr)
            return str(res) if res is not None else ""

        pattern = r"@(?:parameters|variables|activity|item|pipeline)\([^)]*\)(?:\.output(?:\.[a-zA-Z0-9_.]+)?)?(?:\.[a-zA-Z0-9_.]+)?"
        return re.sub(pattern, _replace_embedded, expr_str)
