"""Safe formula evaluation for dataset-cleaning rules.

This module deliberately does not use ``eval`` or ``exec``. User expressions are
parsed with :mod:`ast` and evaluated node by node using a small allow-list.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from datetime import date, datetime
from typing import Any, Callable

import numpy as np
import pandas as pd


class SafeExpressionError(ValueError):
    """Raised when a user formula contains invalid or forbidden syntax."""


_MAX_EXPRESSION_LENGTH = 500
_MAX_AST_NODES = 100
_MAX_POWER_EXPONENT = 100
_MAX_RESULT_STRING_LENGTH = 100_000


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARISON_OPERATORS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

_SAFE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
}

_SAFE_STRING_METHODS = {
    "lower",
    "upper",
    "strip",
    "lstrip",
    "rstrip",
    "title",
    "capitalize",
    "replace",
    "startswith",
    "endswith",
}

_SAFE_DATE_ATTRIBUTES = {"year", "month", "day"}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False

    return isinstance(result, (bool, np.bool_)) and bool(result)


def _normalize_value(value: Any) -> Any:
    """Convert missing scalar values to None while keeping ordinary values."""
    return None if _is_missing(value) else value


def _check_result_size(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_RESULT_STRING_LENGTH:
        raise SafeExpressionError("Formula result is too large.")
    return value


class _SafeAstEvaluator:
    def __init__(self, variables: dict[str, Any]):
        self.variables = {
            str(name): _normalize_value(value)
            for name, value in variables.items()
        }

    def evaluate(self, expression: str) -> Any:
        if not isinstance(expression, str) or not expression.strip():
            raise SafeExpressionError("Formula cannot be empty.")

        if len(expression) > _MAX_EXPRESSION_LENGTH:
            raise SafeExpressionError("Formula is too long.")

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise SafeExpressionError("Invalid formula syntax.") from exc

        if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
            raise SafeExpressionError("Formula is too complex.")

        return _check_result_size(self._visit(tree.body))

    def _visit(self, node: ast.AST) -> Any:
        method = getattr(self, f"_visit_{type(node).__name__}", None)
        if method is None:
            raise SafeExpressionError(
                f"Expression element '{type(node).__name__}' is not allowed."
            )
        return method(node)

    def _visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        raise SafeExpressionError("This literal value is not allowed.")

    def _visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("__"):
            raise SafeExpressionError("Private names are not allowed.")
        if node.id not in self.variables:
            raise SafeExpressionError(f"Unknown column or variable: {node.id}")
        return self.variables[node.id]

    def _visit_List(self, node: ast.List) -> list[Any]:
        return [self._visit(item) for item in node.elts]

    def _visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        return tuple(self._visit(item) for item in node.elts)

    def _visit_Set(self, node: ast.Set) -> set[Any]:
        return {self._visit(item) for item in node.elts}

    def _visit_BinOp(self, node: ast.BinOp) -> Any:
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise SafeExpressionError("This arithmetic operator is not allowed.")

        left = self._visit(node.left)
        right = self._visit(node.right)

        if isinstance(node.op, ast.Pow):
            if not isinstance(right, (int, float)) or abs(right) > _MAX_POWER_EXPONENT:
                raise SafeExpressionError("Exponent is outside the allowed range.")

        if isinstance(node.op, ast.Mult):
            if isinstance(left, str) and isinstance(right, int):
                if len(left) * max(right, 0) > _MAX_RESULT_STRING_LENGTH:
                    raise SafeExpressionError("Formula result is too large.")
            if isinstance(right, str) and isinstance(left, int):
                if len(right) * max(left, 0) > _MAX_RESULT_STRING_LENGTH:
                    raise SafeExpressionError("Formula result is too large.")

        try:
            return _check_result_size(operation(left, right))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise SafeExpressionError("Invalid arithmetic operation.") from exc

    def _visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise SafeExpressionError("This unary operator is not allowed.")
        try:
            return operation(self._visit(node.operand))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise SafeExpressionError("Invalid unary operation.") from exc

    def _visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            result = self._visit(node.values[0])
            for value_node in node.values[1:]:
                if not bool(result):
                    return result
                result = self._visit(value_node)
            return result

        if isinstance(node.op, ast.Or):
            result = self._visit(node.values[0])
            for value_node in node.values[1:]:
                if bool(result):
                    return result
                result = self._visit(value_node)
            return result

        raise SafeExpressionError("This boolean operator is not allowed.")

    def _visit_Compare(self, node: ast.Compare) -> bool:
        left = self._visit(node.left)

        for operator_node, comparator_node in zip(node.ops, node.comparators):
            operation = _COMPARISON_OPERATORS.get(type(operator_node))
            if operation is None:
                raise SafeExpressionError("This comparison is not allowed.")

            right = self._visit(comparator_node)
            try:
                if not bool(operation(left, right)):
                    return False
            except (TypeError, ValueError) as exc:
                raise SafeExpressionError("Invalid comparison.") from exc
            left = right

        return True

    def _visit_IfExp(self, node: ast.IfExp) -> Any:
        branch = node.body if bool(self._visit(node.test)) else node.orelse
        return self._visit(branch)

    def _visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr.startswith("_"):
            raise SafeExpressionError("Private attributes are not allowed.")

        value = self._visit(node.value)
        if isinstance(value, (date, datetime, pd.Timestamp)) and node.attr in _SAFE_DATE_ATTRIBUTES:
            return getattr(value, node.attr)

        raise SafeExpressionError("Direct attribute access is not allowed.")

    def _visit_Call(self, node: ast.Call) -> Any:
        if any(keyword.arg is None for keyword in node.keywords):
            raise SafeExpressionError("Expanded keyword arguments are not allowed.")

        args = [self._visit(arg) for arg in node.args]
        kwargs = {
            keyword.arg: self._visit(keyword.value)
            for keyword in node.keywords
        }

        if isinstance(node.func, ast.Name):
            function_name = node.func.id

            if function_name == "col":
                if kwargs or len(args) != 1 or not isinstance(args[0], str):
                    raise SafeExpressionError("col() expects one column name string.")
                if args[0] not in self.variables:
                    raise SafeExpressionError(f"Unknown column: {args[0]}")
                return self.variables[args[0]]

            if function_name == "is_missing":
                if kwargs or len(args) != 1:
                    raise SafeExpressionError("is_missing() expects one value.")
                return _is_missing(args[0])

            function = _SAFE_FUNCTIONS.get(function_name)
            if function is None:
                raise SafeExpressionError(f"Function '{function_name}' is not allowed.")

            try:
                return _check_result_size(function(*args, **kwargs))
            except (ArithmeticError, TypeError, ValueError) as exc:
                raise SafeExpressionError(f"Invalid call to {function_name}().") from exc

        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name.startswith("_") or method_name not in _SAFE_STRING_METHODS:
                raise SafeExpressionError(f"Method '{method_name}' is not allowed.")

            value = self._visit(node.func.value)
            if not isinstance(value, str):
                raise SafeExpressionError(
                    f"Method '{method_name}' can only be used on text values."
                )

            if kwargs:
                raise SafeExpressionError("Keyword arguments are not allowed for text methods.")

            try:
                result = getattr(value, method_name)(*args)
                return _check_result_size(result)
            except (TypeError, ValueError) as exc:
                raise SafeExpressionError(f"Invalid call to {method_name}().") from exc

        raise SafeExpressionError("Only approved functions and text methods are allowed.")


def _safe_eval_expression(expr: str, row: dict[str, Any]) -> Any:
    """Evaluate a user expression without executing arbitrary Python code.

    Column names that are valid Python identifiers can be used directly. For
    names containing spaces or punctuation, use ``col("Column name")``.
    """
    return _SafeAstEvaluator(row).evaluate(expr)


def _evaluate_braced_expression(inner: str, row: dict[str, Any]) -> Any:
    """Evaluate the contents of ``{...}``, including exact non-identifier names."""
    expression = inner.strip()
    if expression in row:
        return _normalize_value(row[expression])
    return _safe_eval_expression(expression, row)


def _bind_braced_expressions(
    expression: str,
    row: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Replace each ``{...}`` expression with an internal safe variable."""
    bound_values: dict[str, Any] = {}

    def replacer(match: re.Match[str]) -> str:
        variable_name = f"_formula_value_{len(bound_values)}"
        bound_values[variable_name] = _evaluate_braced_expression(
            match.group(1), row
        )
        return variable_name

    rendered = re.sub(r"\{(.*?)}", replacer, expression)
    return rendered, bound_values


def _render_text_template(template: str, row: dict[str, Any]) -> str:
    def replacer(match: re.Match[str]) -> str:
        try:
            value = _evaluate_braced_expression(match.group(1), row)
            return "" if _is_missing(value) else str(value)
        except SafeExpressionError as exc:
            return f"[ERROR: {exc}]"

    return re.sub(r"\{(.*?)}", replacer, template)


def _apply_null_formula_text(
    df: pd.DataFrame,
    column_name: str,
    template: str,
) -> pd.DataFrame:
    df = df.copy()
    mask = df[column_name].isna()
    if not mask.any():
        return df

    df.loc[mask, column_name] = df.loc[mask].apply(
        lambda row: _render_text_template(template, row.to_dict()),
        axis=1,
    )
    return df


def _apply_null_formula_numeric(
    df: pd.DataFrame,
    column_name: str,
    expr: str,
) -> pd.DataFrame:
    df = df.copy()
    mask = df[column_name].isna()
    if not mask.any():
        return df

    def compute(row: pd.Series) -> Any:
        row_dict = row.to_dict()
        try:
            rendered, bound_values = _bind_braced_expressions(expr, row_dict)
            variables = {**row_dict, **bound_values}
            value = _safe_eval_expression(rendered, variables)
            if _is_missing(value) or isinstance(value, bool):
                return np.nan
            return pd.to_numeric(value, errors="coerce")
        except (SafeExpressionError, TypeError, ValueError):
            return np.nan

    df.loc[mask, column_name] = df.loc[mask].apply(compute, axis=1)
    return df


def _apply_null_formula_boolean(
    df: pd.DataFrame,
    column_name: str,
    expr: str,
) -> pd.DataFrame:
    df = df.copy()
    mask = df[column_name].isna()
    if not mask.any():
        return df

    # A column containing only NaN values is often float64. Convert it before
    # assigning booleans to avoid incompatible-dtype assignments in pandas.
    df[column_name] = df[column_name].astype("object")

    def compute(row: pd.Series) -> Any:
        row_dict = row.to_dict()
        try:
            rendered, bound_values = _bind_braced_expressions(expr, row_dict)
            variables = {**row_dict, **bound_values}
            value = _safe_eval_expression(rendered, variables)
            return np.nan if _is_missing(value) else bool(value)
        except (SafeExpressionError, TypeError, ValueError):
            return np.nan

    df.loc[mask, column_name] = df.loc[mask].apply(compute, axis=1)
    return df
