import re
import datetime
import uuid
import base64
import json
from typing import Any, Dict, List, Optional, Tuple, Union


class TokenType:
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    NULL = "NULL"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COMMA = "COMMA"
    DOT = "DOT"
    AT = "AT"
    EOF = "EOF"


class Token:
    def __init__(self, type_: str, value: Any, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)}, pos={self.pos})"


class Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.pos < self.length:
            ch = self.text[self.pos]

            if ch.isspace():
                self.pos += 1
                continue

            if ch == '@':
                tokens.append(Token(TokenType.AT, '@', self.pos))
                self.pos += 1
                continue

            if ch == '(':
                tokens.append(Token(TokenType.LPAREN, '(', self.pos))
                self.pos += 1
                continue

            if ch == ')':
                tokens.append(Token(TokenType.RPAREN, ')', self.pos))
                self.pos += 1
                continue

            if ch == '[':
                tokens.append(Token(TokenType.LBRACKET, '[', self.pos))
                self.pos += 1
                continue

            if ch == ']':
                tokens.append(Token(TokenType.RBRACKET, ']', self.pos))
                self.pos += 1
                continue

            if ch == ',':
                tokens.append(Token(TokenType.COMMA, ',', self.pos))
                self.pos += 1
                continue

            if ch == '.':
                tokens.append(Token(TokenType.DOT, '.', self.pos))
                self.pos += 1
                continue

            # Strings: 'single-quoted' or "double-quoted"
            if ch in ("'", '"'):
                start_pos = self.pos
                quote_char = ch
                self.pos += 1
                val_chars = []
                while self.pos < self.length:
                    c = self.text[self.pos]
                    if c == '\\' and self.pos + 1 < self.length:
                        val_chars.append(self.text[self.pos + 1])
                        self.pos += 2
                    elif c == quote_char:
                        self.pos += 1
                        break
                    else:
                        val_chars.append(c)
                        self.pos += 1
                tokens.append(Token(TokenType.STRING, "".join(val_chars), start_pos))
                continue

            # Numbers: integer or float (including negative if preceded by operator or start)
            if ch.isdigit() or (ch == '-' and self.pos + 1 < self.length and self.text[self.pos + 1].isdigit()):
                start_pos = self.pos
                if ch == '-':
                    self.pos += 1
                while self.pos < self.length and (self.text[self.pos].isdigit() or self.text[self.pos] == '.'):
                    self.pos += 1
                num_str = self.text[start_pos:self.pos]
                num_val = float(num_str) if '.' in num_str else int(num_str)
                tokens.append(Token(TokenType.NUMBER, num_val, start_pos))
                continue

            # Identifiers / Keywords
            if ch.isalpha() or ch == '_':
                start_pos = self.pos
                while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
                    self.pos += 1
                ident = self.text[start_pos:self.pos]
                lower_ident = ident.lower()
                if lower_ident == "true":
                    tokens.append(Token(TokenType.BOOLEAN, True, start_pos))
                elif lower_ident == "false":
                    tokens.append(Token(TokenType.BOOLEAN, False, start_pos))
                elif lower_ident == "null":
                    tokens.append(Token(TokenType.NULL, None, start_pos))
                else:
                    tokens.append(Token(TokenType.IDENTIFIER, ident, start_pos))
                continue

            raise ValueError(f"Unexpected character '{ch}' at position {self.pos}")

        tokens.append(Token(TokenType.EOF, None, self.pos))
        return tokens


def _format_datetime_str(dt: datetime.datetime, fmt: Optional[str] = None) -> str:
    if not fmt:
        return dt.isoformat()
    py_fmt = fmt.replace("yyyy", "%Y").replace("yy", "%y")
    py_fmt = py_fmt.replace("MM", "%m").replace("dd", "%d")
    py_fmt = py_fmt.replace("HH", "%H").replace("hh", "%I")
    py_fmt = py_fmt.replace("mm", "%M").replace("ss", "%S")
    py_fmt = py_fmt.replace("tt", "%p")
    return dt.strftime(py_fmt)


def _parse_datetime(val: Any) -> datetime.datetime:
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time.min)
    if isinstance(val, str):
        val = val.strip().replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(val)
        except Exception:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                try:
                    return datetime.datetime.strptime(val, fmt)
                except Exception:
                    pass
    raise ValueError(f"Unable to parse timestamp from: {val}")


class ExpressionContext:
    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        global_parameters: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
        activity_outputs: Optional[Dict[str, Any]] = None,
        item: Optional[Any] = None,
        pipeline_info: Optional[Dict[str, Any]] = None
    ):
        self.parameters = parameters or {}
        self.global_parameters = global_parameters or {}
        self.variables = variables or {}
        self.activity_outputs = activity_outputs or {}
        self.item = item
        self.pipeline_info = pipeline_info or {}


class ExpressionParser:
    def __init__(self, tokens: List[Token], context: ExpressionContext):
        self.tokens = tokens
        self.context = context
        self.pos = 0

    def current_token(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def consume(self, expected_type: Optional[str] = None) -> Token:
        tok = self.current_token()
        if expected_type and tok.type != expected_type:
            raise ValueError(f"Expected {expected_type} at position {tok.pos}, got {tok.type} ({repr(tok.value)})")
        self.pos += 1
        return tok

    def parse_expression(self) -> Any:
        if self.current_token().type == TokenType.AT:
            self.consume(TokenType.AT)

        res = self.parse_primary()
        res = self.parse_tail(res)
        return res

    def parse_primary(self) -> Any:
        if self.current_token().type == TokenType.AT:
            self.consume(TokenType.AT)

        tok = self.current_token()

        if tok.type == TokenType.STRING:
            self.consume()
            return tok.value
        elif tok.type == TokenType.NUMBER:
            self.consume()
            return tok.value
        elif tok.type == TokenType.BOOLEAN:
            self.consume()
            return tok.value
        elif tok.type == TokenType.NULL:
            self.consume()
            return None
        elif tok.type == TokenType.LPAREN:
            self.consume(TokenType.LPAREN)
            val = self.parse_expression()
            self.consume(TokenType.RPAREN)
            return val
        elif tok.type == TokenType.IDENTIFIER:
            func_name = tok.value
            self.consume(TokenType.IDENTIFIER)
            # Function call: func_name(...)
            if self.current_token().type == TokenType.LPAREN:
                self.consume(TokenType.LPAREN)
                args = []
                if self.current_token().type != TokenType.RPAREN:
                    while True:
                        args.append(self.parse_expression())
                        if self.current_token().type == TokenType.COMMA:
                            self.consume(TokenType.COMMA)
                        else:
                            break
                self.consume(TokenType.RPAREN)
                return self.execute_function(func_name, args)
            else:
                if func_name in self.context.variables:
                    return self.context.variables[func_name]
                if func_name in self.context.parameters:
                    return self.context.parameters[func_name]
                return func_name

        raise ValueError(f"Unexpected token in expression at pos {tok.pos}: {tok.type} ({repr(tok.value)})")

    def parse_tail(self, base_val: Any) -> Any:
        curr = base_val
        while True:
            tok = self.current_token()
            if tok.type == TokenType.DOT:
                self.consume(TokenType.DOT)
                member_tok = self.consume(TokenType.IDENTIFIER)
                member_name = member_tok.value
                if isinstance(curr, dict):
                    curr = curr.get(member_name)
                elif hasattr(curr, member_name):
                    curr = getattr(curr, member_name)
                else:
                    curr = None
            elif tok.type == TokenType.LBRACKET:
                self.consume(TokenType.LBRACKET)
                idx_expr = self.parse_expression()
                self.consume(TokenType.RBRACKET)
                if isinstance(curr, dict):
                    curr = curr.get(idx_expr)
                elif isinstance(curr, (list, tuple)):
                    try:
                        curr = curr[int(idx_expr)]
                    except (IndexError, ValueError, TypeError):
                        curr = None
                else:
                    curr = None
            else:
                break
        return curr

    def execute_function(self, name: str, args: List[Any]) -> Any:
        lower = name.lower()

        # Context scope functions
        if lower == "parameters":
            key = args[0] if args else ""
            return self.context.parameters.get(key)
        elif lower == "variables":
            key = args[0] if args else ""
            return self.context.variables.get(key)
        elif lower == "activity":
            key = args[0] if args else ""
            out = self.context.activity_outputs.get(key, {})
            return {"output": out}
        elif lower == "item":
            return self.context.item
        elif lower == "pipeline":
            p_dict = dict(self.context.pipeline_info)
            p_dict["parameters"] = self.context.parameters
            p_dict["globalParameters"] = self.context.global_parameters
            p_dict["RunId"] = self.context.pipeline_info.get("RunId", "local-run")
            p_dict["Pipeline"] = self.context.pipeline_info.get("Pipeline", "Pipeline")
            p_dict["WorkspaceId"] = self.context.pipeline_info.get("WorkspaceId", "ws-default")
            p_dict["TriggerType"] = self.context.pipeline_info.get("TriggerType", "Manual")
            p_dict["TriggerTime"] = self.context.pipeline_info.get("TriggerTime", datetime.datetime.now(datetime.timezone.utc).isoformat())
            return p_dict

        # String functions
        elif lower == "concat":
            return "".join(str(a) if a is not None else "" for a in args)
        elif lower == "substring":
            text = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            start = int(args[1]) if len(args) > 1 else 0
            length = int(args[2]) if len(args) > 2 else len(text)
            return text[start:start + length]
        elif lower == "toupper":
            return str(args[0]).upper() if args and args[0] is not None else ""
        elif lower == "tolower":
            return str(args[0]).lower() if args and args[0] is not None else ""
        elif lower == "trim":
            return str(args[0]).strip() if args and args[0] is not None else ""
        elif lower == "replace":
            text = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            old = str(args[1]) if len(args) > 1 else ""
            new = str(args[2]) if len(args) > 2 else ""
            return text.replace(old, new)
        elif lower == "split":
            text = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            delimiter = str(args[1]) if len(args) > 1 else ","
            return text.split(delimiter)
        elif lower == "join":
            arr = args[0] if len(args) > 0 and isinstance(args[0], (list, tuple)) else []
            delimiter = str(args[1]) if len(args) > 1 else ","
            return delimiter.join(str(x) for x in arr)
        elif lower == "startswith":
            text = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            prefix = str(args[1]) if len(args) > 1 else ""
            return text.startswith(prefix)
        elif lower == "endswith":
            text = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            suffix = str(args[1]) if len(args) > 1 else ""
            return text.endswith(suffix)
        elif lower == "contains":
            target = args[0] if len(args) > 0 else None
            item = args[1] if len(args) > 1 else None
            if target is None:
                return False
            if isinstance(target, (list, tuple, set)):
                return item in target
            if isinstance(target, dict):
                return item in target
            return str(item) in str(target)
        elif lower == "length":
            val = args[0] if args else ""
            return len(val) if hasattr(val, "__len__") else 0
        elif lower == "base64":
            text = str(args[0]) if args and args[0] is not None else ""
            return base64.b64encode(text.encode("utf-8")).decode("utf-8")
        elif lower == "base64tostring":
            b64_str = str(args[0]) if args and args[0] is not None else ""
            return base64.b64decode(b64_str.encode("utf-8")).decode("utf-8")
        elif lower == "guid":
            return str(uuid.uuid4())

        # Math functions
        elif lower == "add":
            return float(args[0]) + float(args[1]) if len(args) >= 2 else (args[0] if args else 0)
        elif lower == "sub":
            return float(args[0]) - float(args[1]) if len(args) >= 2 else 0
        elif lower == "mul":
            return float(args[0]) * float(args[1]) if len(args) >= 2 else 0
        elif lower == "div":
            denom = float(args[1]) if len(args) >= 2 else 1
            if denom == 0:
                raise ZeroDivisionError("Division by zero in expression div()")
            res = float(args[0]) / denom
            return int(res) if res.is_integer() else res
        elif lower == "mod":
            return float(args[0]) % float(args[1]) if len(args) >= 2 else 0
        elif lower == "min":
            return min(args) if args else None
        elif lower == "max":
            return max(args) if args else None
        elif lower == "abs":
            return abs(float(args[0])) if args else 0
        elif lower == "round":
            decimals = int(args[1]) if len(args) > 1 else 0
            return round(float(args[0]), decimals) if args else 0
        elif lower == "rand":
            import random
            low = int(args[0]) if len(args) > 0 else 0
            high = int(args[1]) if len(args) > 1 else 100
            return random.randint(low, high)

        # Comparison & Logical functions
        elif lower == "equals":
            if len(args) < 2:
                return False
            val1 = args[0]
            val2 = args[1]
            if str(val1).strip("'\"") == str(val2).strip("'\""):
                return True
            return val1 == val2
        elif lower == "greater":
            try:
                return float(args[0]) > float(args[1]) if len(args) >= 2 else False
            except (ValueError, TypeError):
                return False
        elif lower == "greaterorequals":
            try:
                return float(args[0]) >= float(args[1]) if len(args) >= 2 else False
            except (ValueError, TypeError):
                return False
        elif lower == "less":
            try:
                return float(args[0]) < float(args[1]) if len(args) >= 2 else False
            except (ValueError, TypeError):
                return False
        elif lower == "lessorequals":
            try:
                return float(args[0]) <= float(args[1]) if len(args) >= 2 else False
            except (ValueError, TypeError):
                return False
        elif lower == "and":
            return all(bool(a) for a in args)
        elif lower == "or":
            return any(bool(a) for a in args)
        elif lower == "not":
            return not bool(args[0]) if args else True
        elif lower == "if":
            cond = bool(args[0]) if len(args) > 0 else False
            true_val = args[1] if len(args) > 1 else None
            false_val = args[2] if len(args) > 2 else None
            return true_val if cond else false_val
        elif lower == "bool":
            return bool(args[0]) if args else False

        # Date & Time functions
        elif lower == "utcnow":
            now = datetime.datetime.now(datetime.timezone.utc)
            fmt = args[0] if args else None
            return _format_datetime_str(now, fmt)
        elif lower == "adddays":
            dt = _parse_datetime(args[0])
            days = float(args[1]) if len(args) > 1 else 0
            fmt = args[2] if len(args) > 2 else None
            res = dt + datetime.timedelta(days=days)
            return _format_datetime_str(res, fmt)
        elif lower == "addhours":
            dt = _parse_datetime(args[0])
            hours = float(args[1]) if len(args) > 1 else 0
            fmt = args[2] if len(args) > 2 else None
            res = dt + datetime.timedelta(hours=hours)
            return _format_datetime_str(res, fmt)
        elif lower == "addminutes":
            dt = _parse_datetime(args[0])
            minutes = float(args[1]) if len(args) > 1 else 0
            fmt = args[2] if len(args) > 2 else None
            res = dt + datetime.timedelta(minutes=minutes)
            return _format_datetime_str(res, fmt)
        elif lower == "addseconds":
            dt = _parse_datetime(args[0])
            secs = float(args[1]) if len(args) > 1 else 0
            fmt = args[2] if len(args) > 2 else None
            res = dt + datetime.timedelta(seconds=secs)
            return _format_datetime_str(res, fmt)
        elif lower == "formatdatetime":
            dt = _parse_datetime(args[0])
            fmt = args[1] if len(args) > 1 else "%Y-%m-%d %H:%M:%S"
            return _format_datetime_str(dt, fmt)
        elif lower == "dayofweek":
            dt = _parse_datetime(args[0])
            return dt.isoweekday()
        elif lower == "dayofmonth":
            dt = _parse_datetime(args[0])
            return dt.day
        elif lower == "dayofyear":
            dt = _parse_datetime(args[0])
            return dt.timetuple().tm_yday
        elif lower == "startofday":
            dt = _parse_datetime(args[0]).replace(hour=0, minute=0, second=0, microsecond=0)
            fmt = args[1] if len(args) > 1 else None
            return _format_datetime_str(dt, fmt)
        elif lower == "startofmonth":
            dt = _parse_datetime(args[0]).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fmt = args[1] if len(args) > 1 else None
            return _format_datetime_str(dt, fmt)

        # Collection functions
        elif lower == "first":
            col = args[0] if args else []
            return col[0] if len(col) > 0 else None
        elif lower == "last":
            col = args[0] if args else []
            return col[-1] if len(col) > 0 else None
        elif lower == "take":
            col = args[0] if args else []
            n = int(args[1]) if len(args) > 1 else 0
            return col[:n]
        elif lower == "skip":
            col = args[0] if args else []
            n = int(args[1]) if len(args) > 1 else 0
            return col[n:]
        elif lower == "empty":
            col = args[0] if args else None
            return True if col is None or (hasattr(col, "__len__") and len(col) == 0) else False
        elif lower == "createarray":
            return list(args)
        elif lower == "union":
            l1 = args[0] if len(args) > 0 and isinstance(args[0], list) else []
            l2 = args[1] if len(args) > 1 and isinstance(args[1], list) else []
            res = []
            for item in l1 + l2:
                if item not in res:
                    res.append(item)
            return res
        elif lower == "intersection":
            l1 = args[0] if len(args) > 0 and isinstance(args[0], list) else []
            l2 = args[1] if len(args) > 1 and isinstance(args[1], list) else []
            return [item for item in l1 if item in l2]

        # Conversion & Null handling
        elif lower == "coalesce":
            for a in args:
                if a is not None:
                    return a
            return None
        elif lower == "json":
            raw = args[0] if args else ""
            if isinstance(raw, (dict, list)):
                return raw
            return json.loads(str(raw))
        elif lower == "string":
            return str(args[0]) if args and args[0] is not None else ""
        elif lower == "int":
            return int(float(args[0])) if args and args[0] is not None else 0
        elif lower == "float":
            return float(args[0]) if args and args[0] is not None else 0.0

        raise ValueError(f"Unknown function '{name}' in expression")


class ExpressionEvaluator:
    """
    Production-grade Expression Evaluator for DataFlow Enterprise pipelines.
    Supports complete ADF dynamic content expressions:
      - Parameters: @parameters('name'), @pipeline().parameters.name
      - Global parameters: @pipeline().globalParameters.name
      - Variables: @variables('name')
      - Activity output navigation: @activity('act').output.prop[0].subprop
      - System metadata: @pipeline().RunId, @pipeline().Pipeline, @pipeline().TriggerTime
      - Loop item: @item(), @item().prop
      - String, Math, Logical, Date/Time, Collection, and Type Conversion functions
      - String interpolation: dataset_@{pipeline().parameters.env}_@{activity('act').output.id}.csv
    """

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
        activity_outputs: Optional[Dict[str, Any]] = None,
        item: Optional[Any] = None,
        pipeline_info: Optional[Dict[str, Any]] = None,
        global_parameters: Optional[Dict[str, Any]] = None
    ):
        self.context = ExpressionContext(
            parameters=parameters,
            global_parameters=global_parameters,
            variables=variables,
            activity_outputs=activity_outputs,
            item=item,
            pipeline_info=pipeline_info
        )

    # Backwards compatibility properties
    @property
    def parameters(self):
        return self.context.parameters

    @property
    def variables(self):
        return self.context.variables

    @property
    def activity_outputs(self):
        return self.context.activity_outputs

    @property
    def item(self):
        return self.context.item

    @property
    def pipeline_info(self):
        return self.context.pipeline_info

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

        # Check for escaped '@' in ADF: '@@' represents literal '@'
        if expr_str.startswith("@@"):
            return expr_str[1:]

        # Support nested calls that omit leading '@'
        if expr_str.startswith((
            "activity(", "parameters(", "variables(", "item(", "pipeline(",
            "equals(", "greater(", "less(", "not(", "concat("
        )):
            expr_str = "@" + expr_str

        # If it starts with '@', evaluate as an expression
        if expr_str.startswith("@"):
            try:
                tokens = Tokenizer(expr_str).tokenize()
                parser = ExpressionParser(tokens, self.context)
                return parser.parse_expression()
            except Exception:
                # If pure parsing fails, fall back to string interpolation below
                pass

        # String interpolation with explicit @{...} delimiters
        if "@{" in expr_str:
            def _replace_braced(m):
                sub_expr = m.group(1).strip()
                if not sub_expr.startswith("@"):
                    sub_expr = "@" + sub_expr
                try:
                    tokens = Tokenizer(sub_expr).tokenize()
                    parser = ExpressionParser(tokens, self.context)
                    res = parser.parse_expression()
                    return str(res) if res is not None else ""
                except Exception:
                    return ""

            return re.sub(r"@\{([^}]+)\}", _replace_braced, expr_str)

        # Fallback string interpolation for embedded @activity(...) in freeform SQL/text
        def _replace_embedded(m):
            sub_expr = m.group(0)
            try:
                tokens = Tokenizer(sub_expr).tokenize()
                parser = ExpressionParser(tokens, self.context)
                res = parser.parse_expression()
                return str(res) if res is not None else ""
            except Exception:
                return sub_expr

        pattern = r"@(?:parameters|variables|activity|item|pipeline)\([^)]*\)(?:\.output(?:\.[a-zA-Z0-9_.]+)?)?(?:\.[a-zA-Z0-9_.]+)?"
        return re.sub(pattern, _replace_embedded, expr_str)


def validate_expression(expr_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validates syntax of an ADF expression without executing it.
    """
    expr_str = expr_str.strip()
    if not expr_str:
        return True, None

    if expr_str.startswith("@@"):
        return True, None

    if "@{" in expr_str:
        braced = re.findall(r"@\{([^}]+)\}", expr_str)
        for b in braced:
            sub = b.strip()
            if not sub.startswith("@"):
                sub = "@" + sub
            try:
                tokens = Tokenizer(sub).tokenize()
                dummy_ctx = ExpressionContext()
                parser = ExpressionParser(tokens, dummy_ctx)
                parser.parse_expression()
            except Exception as e:
                return False, f"Syntax error in @{{{b}}}: {str(e)}"
        return True, None

    if expr_str.startswith("@") or expr_str.startswith((
        "activity(", "parameters(", "variables(", "item(", "pipeline(",
        "equals(", "greater(", "less(", "not(", "concat("
    )):
        if not expr_str.startswith("@"):
            expr_str = "@" + expr_str
        try:
            tokens = Tokenizer(expr_str).tokenize()
            dummy_ctx = ExpressionContext()
            parser = ExpressionParser(tokens, dummy_ctx)
            parser.parse_expression()
            return True, None
        except Exception as e:
            return False, str(e)

    return True, None


# Autocomplete and documentation catalog for frontend expression builder
EXPRESSION_FUNCTIONS_CATALOG = [
    # System & Scopes
    {
        "name": "parameters",
        "category": "System & Scope",
        "signature": "parameters('name')",
        "description": "Returns the value of a pipeline parameter.",
        "example": "@parameters('batch_size')",
        "return_type": "any"
    },
    {
        "name": "variables",
        "category": "System & Scope",
        "signature": "variables('name')",
        "description": "Returns the current value of a pipeline variable.",
        "example": "@variables('watermark')",
        "return_type": "any"
    },
    {
        "name": "activity",
        "category": "System & Scope",
        "signature": "activity('activityName').output.property",
        "description": "References output properties returned by an upstream activity.",
        "example": "@activity('LookupCustomer').output.first_row.id",
        "return_type": "any"
    },
    {
        "name": "item",
        "category": "System & Scope",
        "signature": "item() or item().propertyName",
        "description": "References the current iterated item in a ForEach activity loop.",
        "example": "@item().filePath",
        "return_type": "any"
    },
    {
        "name": "pipeline",
        "category": "System & Scope",
        "signature": "pipeline().RunId or pipeline().Pipeline",
        "description": "Returns system metadata for the current running pipeline execution.",
        "example": "@pipeline().RunId",
        "return_type": "object"
    },
    # String Functions
    {
        "name": "concat",
        "category": "String",
        "signature": "concat(text1, text2, ...)",
        "description": "Concatenates multiple strings together.",
        "example": "@concat('prefix_', parameters('env'), '.csv')",
        "return_type": "string"
    },
    {
        "name": "substring",
        "category": "String",
        "signature": "substring(text, startIndex, length)",
        "description": "Extracts characters from a string starting at the specified index.",
        "example": "@substring('2026-11-05', 0, 4)",
        "return_type": "string"
    },
    {
        "name": "toUpper",
        "category": "String",
        "signature": "toUpper(text)",
        "description": "Converts a string to upper case.",
        "example": "@toUpper(parameters('countryCode'))",
        "return_type": "string"
    },
    {
        "name": "toLower",
        "category": "String",
        "signature": "toLower(text)",
        "description": "Converts a string to lower case.",
        "example": "@toLower(parameters('email'))",
        "return_type": "string"
    },
    {
        "name": "trim",
        "category": "String",
        "signature": "trim(text)",
        "description": "Removes leading and trailing whitespace from a string.",
        "example": "@trim('  sample text  ')",
        "return_type": "string"
    },
    {
        "name": "replace",
        "category": "String",
        "signature": "replace(text, oldString, newString)",
        "description": "Replaces all occurrences of a substring with another string.",
        "example": "@replace('path/to/file', '/', '_')",
        "return_type": "string"
    },
    {
        "name": "split",
        "category": "String",
        "signature": "split(text, delimiter)",
        "description": "Splits a string into an array of substrings.",
        "example": "@split('apple,banana,orange', ',')",
        "return_type": "array"
    },
    {
        "name": "join",
        "category": "String",
        "signature": "join(array, delimiter)",
        "description": "Joins array elements into a single delimited string.",
        "example": "@join(createArray('a', 'b', 'c'), '-')",
        "return_type": "string"
    },
    {
        "name": "startsWith",
        "category": "String",
        "signature": "startsWith(text, prefix)",
        "description": "Checks if a string begins with the specified prefix.",
        "example": "@startsWith(parameters('filename'), 'raw_')",
        "return_type": "boolean"
    },
    {
        "name": "endsWith",
        "category": "String",
        "signature": "endsWith(text, suffix)",
        "description": "Checks if a string ends with the specified suffix.",
        "example": "@endsWith(parameters('filename'), '.parquet')",
        "return_type": "boolean"
    },
    {
        "name": "guid",
        "category": "String",
        "signature": "guid()",
        "description": "Generates a unique v4 UUID string.",
        "example": "@guid()",
        "return_type": "string"
    },
    # Math Functions
    {
        "name": "add",
        "category": "Math",
        "signature": "add(value1, value2)",
        "description": "Adds two numbers together.",
        "example": "@add(parameters('limit'), 10)",
        "return_type": "number"
    },
    {
        "name": "sub",
        "category": "Math",
        "signature": "sub(value1, value2)",
        "description": "Subtracts the second number from the first number.",
        "example": "@sub(variables('totalCount'), 1)",
        "return_type": "number"
    },
    {
        "name": "mul",
        "category": "Math",
        "signature": "mul(value1, value2)",
        "description": "Multiplies two numbers together.",
        "example": "@mul(parameters('batchSize'), 2)",
        "return_type": "number"
    },
    {
        "name": "div",
        "category": "Math",
        "signature": "div(value1, value2)",
        "description": "Divides the first number by the second number.",
        "example": "@div(100, 4)",
        "return_type": "number"
    },
    {
        "name": "mod",
        "category": "Math",
        "signature": "mod(value1, value2)",
        "description": "Calculates the remainder of dividing value1 by value2.",
        "example": "@mod(17, 5)",
        "return_type": "number"
    },
    # Logical & Comparison
    {
        "name": "equals",
        "category": "Logical",
        "signature": "equals(value1, value2)",
        "description": "Returns true if both arguments are equal.",
        "example": "@equals(parameters('env'), 'prod')",
        "return_type": "boolean"
    },
    {
        "name": "greater",
        "category": "Logical",
        "signature": "greater(value1, value2)",
        "description": "Returns true if value1 is greater than value2.",
        "example": "@greater(activity('Lookup').output.count, 0)",
        "return_type": "boolean"
    },
    {
        "name": "less",
        "category": "Logical",
        "signature": "less(value1, value2)",
        "description": "Returns true if value1 is less than value2.",
        "example": "@less(variables('retryCount'), 3)",
        "return_type": "boolean"
    },
    {
        "name": "if",
        "category": "Logical",
        "signature": "if(condition, valueIfTrue, valueIfFalse)",
        "description": "Conditional ternary operator returning one of two values.",
        "example": "@if(equals(parameters('env'), 'prod'), 'warehouse_prod', 'warehouse_dev')",
        "return_type": "any"
    },
    {
        "name": "not",
        "category": "Logical",
        "signature": "not(value)",
        "description": "Inverts a boolean value.",
        "example": "@not(variables('isProcessed'))",
        "return_type": "boolean"
    },
    {
        "name": "and",
        "category": "Logical",
        "signature": "and(cond1, cond2, ...)",
        "description": "Returns true if all conditions are true.",
        "example": "@and(greater(5, 2), not(false))",
        "return_type": "boolean"
    },
    {
        "name": "or",
        "category": "Logical",
        "signature": "or(cond1, cond2, ...)",
        "description": "Returns true if any condition is true.",
        "example": "@or(equals(parameters('tier'), 'gold'), equals(parameters('tier'), 'platinum'))",
        "return_type": "boolean"
    },
    # Date & Time
    {
        "name": "utcNow",
        "category": "Date & Time",
        "signature": "utcNow(format?)",
        "description": "Returns the current UTC timestamp, optionally formatted.",
        "example": "@utcNow('yyyy-MM-dd HH:mm:ss')",
        "return_type": "string"
    },
    {
        "name": "addDays",
        "category": "Date & Time",
        "signature": "addDays(timestamp, days, format?)",
        "description": "Adds or subtracts days to a timestamp.",
        "example": "@addDays(utcNow(), -1, 'yyyy-MM-dd')",
        "return_type": "string"
    },
    {
        "name": "addHours",
        "category": "Date & Time",
        "signature": "addHours(timestamp, hours, format?)",
        "description": "Adds or subtracts hours to a timestamp.",
        "example": "@addHours(utcNow(), 2)",
        "return_type": "string"
    },
    {
        "name": "formatDateTime",
        "category": "Date & Time",
        "signature": "formatDateTime(timestamp, format)",
        "description": "Formats a timestamp string using a specified date-time format.",
        "example": "@formatDateTime('2026-11-05T00:00:00Z', 'yyyyMMdd')",
        "return_type": "string"
    },
    # Collections & Conversion
    {
        "name": "coalesce",
        "category": "Conversion & Null",
        "signature": "coalesce(val1, val2, ...)",
        "description": "Returns the first non-null argument.",
        "example": "@coalesce(activity('Lookup').output.first_row.email, 'unknown@domain.com')",
        "return_type": "any"
    },
    {
        "name": "createArray",
        "category": "Collection",
        "signature": "createArray(item1, item2, ...)",
        "description": "Constructs an array from arguments.",
        "example": "@createArray('bronze', 'silver', 'gold')",
        "return_type": "array"
    },
    {
        "name": "empty",
        "category": "Collection",
        "signature": "empty(collectionOrString)",
        "description": "Returns true if a collection or string is empty or null.",
        "example": "@empty(activity('Lookup').output.value)",
        "return_type": "boolean"
    },
    {
        "name": "first",
        "category": "Collection",
        "signature": "first(collection)",
        "description": "Returns the first element of an array.",
        "example": "@first(activity('Lookup').output.value)",
        "return_type": "any"
    },
    {
        "name": "last",
        "category": "Collection",
        "signature": "last(collection)",
        "description": "Returns the last element of an array.",
        "example": "@last(variables('batchList'))",
        "return_type": "any"
    },
    {
        "name": "json",
        "category": "Conversion & Null",
        "signature": "json(jsonString)",
        "description": "Parses a JSON string into an object or array.",
        "example": "@json('{\"key\": \"value\"}')",
        "return_type": "object"
    },
    {
        "name": "string",
        "category": "Conversion & Null",
        "signature": "string(value)",
        "description": "Converts any value into a string.",
        "example": "@string(12345)",
        "return_type": "string"
    },
    {
        "name": "int",
        "category": "Conversion & Null",
        "signature": "int(value)",
        "description": "Converts a string or float into an integer.",
        "example": "@int('42')",
        "return_type": "number"
    }
]
