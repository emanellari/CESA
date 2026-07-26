import pandas as pd
import streamlit as st

from services.cleaning.formulas import (
    _apply_null_formula_text,
    _apply_null_formula_numeric,
    _apply_null_formula_boolean,
)

from services.cleaning.formulas import _render_text_template
from services.cleaning.profiles import get_mode_value, get_median_value


def parse_replacements_text(text: str) -> dict:
    replacements = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue

        old, new = line.split("=", 1)
        old = old.strip()
        new = new.strip()

        if old:
            replacements[old] = new

    return replacements

def parse_replacements(replacements_list: list) -> dict:
    replacements = {}

    for item in replacements_list or []:
        if not isinstance(item, dict):
            continue

        old_values = item.get("old_values", [])
        new_value = item.get("new", "")

        if not isinstance(old_values, list):
            old_values = []

        for old in old_values:
            if old is None or str(old).strip() == "":
                continue
            replacements[old] = new_value

    return replacements

def apply_replacements(series: pd.Series, replacements: dict) -> pd.Series:
    return series.replace(replacements) if replacements else series

def get_mean_value(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 0
    return float(s.mean())

def handle_nulls(
    df: pd.DataFrame,
    column_name: str,
    strategy: str,
    fill_value=None,
    column_config: dict | None = None,
) -> pd.DataFrame:
    """Apply the configured null strategy to one column."""
    if column_name not in df.columns:
        return df

    df = df.copy()
    column_config = column_config or {}

    if strategy == "keep":
        return df

    if strategy == "drop":
        return df.loc[df[column_name].notna()].copy()

    if strategy == "fill":
        df[column_name] = df[column_name].fillna(fill_value)
        return df

    if strategy == "fill_true":
        df[column_name] = df[column_name].fillna(True)
        return df

    if strategy == "fill_false":
        df[column_name] = df[column_name].fillna(False)
        return df

    if strategy == "fill_mode":
        mode_value = get_mode_value(df[column_name])
        df[column_name] = df[column_name].fillna(mode_value)
        return df

    if strategy == "fill_mean":
        mean_value = get_mean_value(df[column_name])
        df[column_name] = df[column_name].fillna(mean_value)
        return df

    if strategy == "fill_median":
        median_value = get_median_value(df[column_name])
        df[column_name] = df[column_name].fillna(median_value)
        return df

    if strategy == "fill_formula_text":
        template = column_config.get("null_formula_text", "").strip()
        if template:
            return _apply_null_formula_text(df, column_name, template)
        return df

    if strategy == "fill_formula_numeric":
        expression = column_config.get("null_formula_numeric", "").strip()
        if expression:
            return _apply_null_formula_numeric(df, column_name, expression)
        return df

    if strategy == "fill_formula_boolean":
        expression = column_config.get("null_formula_boolean", "").strip()
        if expression:
            return _apply_null_formula_boolean(df, column_name, expression)
        return df

    return df

def convert_series_to_boolean(series: pd.Series, true_value: str, false_value: str, other_strategy: str = "null") -> pd.Series:
    true_value_norm = str(true_value).strip().lower()
    false_value_norm = str(false_value).strip().lower()

    def mapper(x):
        if pd.isna(x):
            return None

        x_norm = str(x).strip().lower()

        if x_norm == true_value_norm:
            return True
        if x_norm == false_value_norm:
            return False

        if other_strategy == "true":
            return True
        if other_strategy == "false":
            return False
        if other_strategy == "drop":
            return "__DROP__"

        return None

    return series.map(mapper)

def get_numeric_outlier_info(series: pd.Series, multiplier: float = 1.5) -> dict:
    s = pd.to_numeric(series, errors="coerce").dropna()

    if s.empty:
        return {
            "count": 0,
            "lower_bound": None,
            "upper_bound": None,
            "examples": [],
        }

    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1

    if pd.isna(iqr) or iqr == 0:
        return {
            "count": 0,
            "lower_bound": q1,
            "upper_bound": q3,
            "examples": [],
        }

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    outliers = s[(s < lower) | (s > upper)]

    return {
        "count": int(outliers.shape[0]),
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "examples": outliers.sort_values().tolist()[:10],
    }

def apply_user_config(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Apply column cleaning rules in a predictable two-pass pipeline."""
    clean_df = df.copy()

    column_configs = {
        col: cfg
        for col, cfg in config.items()
        if isinstance(cfg, dict) and col in clean_df.columns
    }

    # First pass:
    # Apply replacements and convert every column to its selected type.
    for col, cfg in column_configs.items():
        visual_replacements = parse_replacements(
            cfg.get("replacements", [])
        )

        # Backwards compatibility with the old:
        # {"old": ..., "new": ...}
        for item in cfg.get("replacements", []) or []:
            if isinstance(item, dict) and item.get("old") is not None:
                visual_replacements[item["old"]] = item.get("new")

        manual_replacements = parse_replacements_text(
            cfg.get("replacements_text", "")
        )

        all_replacements = {
            **visual_replacements,
            **manual_replacements,
        }

        clean_df[col] = apply_replacements(
            clean_df[col],
            all_replacements,
        )

        final_type = cfg.get("final_type", "text")

        if final_type == "number":
            clean_df[col] = pd.to_numeric(
                clean_df[col],
                errors="coerce",
            )

        elif final_type == "date":
            clean_df[col] = pd.to_datetime(
                clean_df[col],
                errors="coerce",
            )

        elif final_type == "boolean":
            mapped = convert_series_to_boolean(
                clean_df[col],
                cfg.get("true_value", ""),
                cfg.get("false_value", ""),
                cfg.get("other_values_strategy", "null"),
            )

            if cfg.get("other_values_strategy") == "drop":
                keep_mask = mapped != "__DROP__"

                clean_df = clean_df.loc[keep_mask].copy()
                mapped = mapped.loc[keep_mask]

            clean_df[col] = (
                mapped
                .replace("__DROP__", pd.NA)
                .astype("boolean")
            )

        else:
            clean_df[col] = clean_df[col].astype("string")

    # Second pass:
    # Apply null handling after all columns have their selected types.
    for col, cfg in column_configs.items():
        if col not in clean_df.columns:
            continue

        clean_df = handle_nulls(
            clean_df,
            column_name=col,
            strategy=cfg.get("null_strategy", "keep"),
            fill_value=cfg.get("null_fill_value"),
            column_config=cfg,
        )

        final_type = cfg.get("final_type", "text")

        # Restore selected dtype after filling null values.
        if final_type == "number":
            clean_df[col] = pd.to_numeric(
                clean_df[col],
                errors="coerce",
            )

            clean_df = handle_outliers(
                clean_df,
                col,
                col_config=cfg,
            )

        elif final_type == "date":
            clean_df[col] = pd.to_datetime(
                clean_df[col],
                errors="coerce",
            )

        elif final_type == "boolean":
            clean_df[col] = clean_df[col].astype("boolean")

        elif final_type in ["text", "categorical"]:
            clean_df[col] = clean_df[col].astype("string")

            text_case = cfg.get("text_case")

            if text_case == "lower":
                clean_df[col] = clean_df[col].str.lower()

            elif text_case == "upper":
                clean_df[col] = clean_df[col].str.upper()

            elif text_case == "title":
                clean_df[col] = clean_df[col].str.title()

    return clean_df

def detect_duplicate_columns(df: pd.DataFrame) -> list[tuple[str, str]]:
    duplicates = []
    cols = df.columns.tolist()
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            if df[cols[i]].equals(df[cols[j]]):
                duplicates.append((cols[i], cols[j]))
    return duplicates

def handle_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    df_clean = df.copy()
    # Lista e kolonave të fshira
    cols_to_drop = []
    cols = df_clean.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            if cols[i] in cols_to_drop or cols[j] in cols_to_drop:
                continue
            if df_clean[cols[i]].equals(df_clean[cols[j]]):
                st.warning(f"Columns `{cols[i]}` and `{cols[j]}` are identical. `{cols[j]}` will be removed automatically.")
                cols_to_drop.append(cols[j])
    df_clean.drop(columns=cols_to_drop, inplace=True)
    return df_clean


def handle_outliers(df: pd.DataFrame, column_name: str, col_config: dict) -> pd.DataFrame:
    strategy = col_config.get("outlier_strategy", "none")
    if strategy == "none":
        return df

    series = pd.to_numeric(df[column_name], errors="coerce")

    if strategy in ["cap_iqr", "drop_iqr"]:
        multiplier = float(col_config.get("outlier_iqr_multiplier", 1.5))
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if pd.isna(iqr) or iqr == 0:
            return df

        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        if strategy == "cap_iqr":
            df[column_name] = series.clip(lower=lower, upper=upper)
            return df

        if strategy == "drop_iqr":
            return df[(series.isna()) | ((series >= lower) & (series <= upper))]

    if strategy in ["cap_zscore", "drop_zscore"]:
        threshold = float(col_config.get("outlier_zscore_threshold", 3.0))
        mean = series.mean()
        std = series.std()

        if pd.isna(std) or std == 0:
            return df

        zscores = (series - mean) / std

        if strategy == "cap_zscore":
            lower = mean - threshold * std
            upper = mean + threshold * std
            df[column_name] = series.clip(lower=lower, upper=upper)
            return df

        if strategy == "drop_zscore":
            return df[(series.isna()) | (zscores.abs() <= threshold)]

    return df

def read_uploaded_dataset(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if filename.endswith(".tsv"):
        return pd.read_csv(uploaded_file, sep="\t")

    raise ValueError("Unsupported file format")