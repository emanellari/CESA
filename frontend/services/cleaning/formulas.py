import re
import pandas as pd
import numpy as np

def _safe_eval_expression(expr: str, row: dict):
    safe_locals = {}
    for k, v in row.items():
        if pd.isna(v):
            safe_locals[k] = ""
        else:
            safe_locals[k] = v
    return eval(expr, {"__builtins__": {}}, safe_locals)

def _render_text_template(template: str, row: dict) -> str:
    def replacer(match):
        expr = match.group(1).strip()
        try:
            value = _safe_eval_expression(expr, row)
            return "" if pd.isna(value) else str(value)
        except Exception as e:
            return f"[ERROR: {e}]"

    return re.sub(r"\{(.*?)}", replacer, template)

def _apply_null_formula_text(df: pd.DataFrame, column_name: str, template: str) -> pd.DataFrame:
    mask = df[column_name].isna()
    if not mask.any():
        print("No nulls found for", column_name)
        return df

    before = df.loc[mask, [column_name]].copy()

    df.loc[mask, column_name] = df.loc[mask].apply(
        lambda row: _render_text_template(template, row.to_dict()),
        axis=1
    )

    after = df.loc[mask, [column_name]].copy()

    print("---- APPLY_TEXT_FORMULA ----")
    print("column:", column_name)
    print("template:", template)
    print("rows changed:", len(after))
    print("before sample:")
    print(before.head(5))
    print("after sample:")
    print(after.head(5))

    return df

def _apply_null_formula_numeric(df: pd.DataFrame, column_name: str, expr: str) -> pd.DataFrame:
    mask = df[column_name].isna()
    if not mask.any():
        return df

    def compute(row):
        row_dict = row.to_dict()

        def replacer(match):
            inner = match.group(1).strip()
            try:
                value = _safe_eval_expression(inner, row_dict)
                return str(value)
            except Exception:
                return "np.nan"

        rendered = re.sub(r"\{(.*?)}", replacer, expr)

        try:
            value = eval(rendered, {"__builtins__": {}, "np": np}, {})
            return pd.to_numeric(value, errors="coerce")
        except Exception:
            return np.nan

    df.loc[mask, column_name] = df.loc[mask].apply(compute, axis=1)
    return df

def _apply_null_formula_boolean(df: pd.DataFrame, column_name: str, expr: str) -> pd.DataFrame:
    mask = df[column_name].isna()
    if not mask.any():
        return df

    def compute(row):
        row_dict = row.to_dict()

        def replacer(match):
            inner = match.group(1).strip()
            try:
                value = _safe_eval_expression(inner, row_dict)
                return repr(value)
            except Exception:
                return "None"

        rendered = re.sub(r"\{(.*?)}", replacer, expr)

        try:
            return bool(eval(rendered, {"__builtins__": {}}, {}))
        except Exception:
            return np.nan

    df.loc[mask, column_name] = df.loc[mask].apply(compute, axis=1)
    return df

