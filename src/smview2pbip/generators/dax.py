"""Translate the supported Snowflake metric expression subset to DAX."""

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlglot import exp, parse_one


class UnsupportedExpressionError(ValueError):
    """Raised when a Snowflake metric cannot be translated without guessing."""


def _quote_name(name: str) -> str:
    return name.replace("'", "''")


def _protect_functions(expression: str) -> str:
    return re.sub(r"\bDIV0\s*\(", "SMVIEW_SAFE_DIVIDE(", expression, flags=re.IGNORECASE)


def referenced_columns(expression: str) -> set[str]:
    """Return physical column names referenced by a metric expression."""

    root = parse_one(_protect_functions(expression), read="snowflake")
    return {column.name for column in root.find_all(exp.Column)}


def translate_metric(
    expression: str,
    table_name: str,
    column_mapping: Mapping[str, str],
) -> str:
    """Translate a constrained Snowflake aggregate expression into DAX."""

    root = parse_one(_protect_functions(expression), read="snowflake")
    quoted_table = _quote_name(table_name)

    def render(node: exp.Expression, row_context: bool = False) -> str:
        if isinstance(node, exp.Paren):
            return f"({render(node.this, row_context)})"
        if isinstance(node, exp.Column):
            mapped = column_mapping.get(node.name.upper())
            if mapped is None:
                raise UnsupportedExpressionError(f"Unknown source column '{node.name}'.")
            return f"'{quoted_table}'[{mapped}]"
        if isinstance(node, exp.Literal):
            return str(node.this) if not node.is_string else f'"{node.this}"'
        if isinstance(node, (exp.Add, exp.Sub, exp.Mul, exp.Div)):
            operator = {exp.Add: "+", exp.Sub: "-", exp.Mul: "*", exp.Div: "/"}[type(node)]
            return f"({render(node.left, row_context)} {operator} {render(node.right, row_context)})"
        if isinstance(node, exp.Sum):
            argument = node.this
            if isinstance(argument, exp.Column):
                return f"SUM({render(argument)})"
            return f"SUMX('{quoted_table}', {render(argument, True)})"
        if isinstance(node, exp.Count):
            argument = node.this
            if isinstance(argument, exp.Star):
                return f"COUNTROWS('{quoted_table}')"
            if isinstance(argument, exp.Distinct):
                arguments = list(argument.expressions)
                if len(arguments) != 1 or not isinstance(arguments[0], exp.Column):
                    raise UnsupportedExpressionError(
                        "COUNT DISTINCT is supported only for a single column."
                    )
                return f"DISTINCTCOUNTNOBLANK({render(arguments[0])})"
            return f"COUNTAX('{quoted_table}', {render(argument, True)})"
        if isinstance(node, (exp.Avg, exp.Min, exp.Max)):
            argument = node.this
            aggregate, iterator = {
                exp.Avg: ("AVERAGE", "AVERAGEX"),
                exp.Min: ("MIN", "MINX"),
                exp.Max: ("MAX", "MAXX"),
            }[type(node)]
            if isinstance(argument, exp.Column):
                return f"{aggregate}({render(argument)})"
            return f"{iterator}('{quoted_table}', {render(argument, True)})"
        if isinstance(node, exp.Coalesce):
            arguments = [node.this, *node.expressions]
            return f"COALESCE({', '.join(render(argument, row_context) for argument in arguments)})"
        if isinstance(node, exp.Round):
            decimals = node.args.get("decimals")
            if decimals is None:
                decimals = exp.Literal.number(0)
            return f"ROUND({render(node.this)}, {render(decimals)})"
        if isinstance(node, exp.Anonymous) and node.name.upper() == "SMVIEW_SAFE_DIVIDE":
            arguments = list(node.expressions)
            if len(arguments) != 2:
                raise UnsupportedExpressionError("DIV0 must have exactly two arguments.")
            return f"DIVIDE({render(arguments[0])}, {render(arguments[1])}, 0)"
        raise UnsupportedExpressionError(
            f"Unsupported expression node '{type(node).__name__}': {node.sql()}."
        )

    return render(root)
