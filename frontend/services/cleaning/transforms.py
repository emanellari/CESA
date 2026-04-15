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


def get_mean_value(param):
    pass


def handle_nulls(
    df: pd.DataFrame,
    column_name: str,
    strategy: str,
    fill_value=None,
    column_config: dict | None = None
) -> pd.DataFrame:
    df = df.copy()

    print("---- HANDLE_NULLS ----")
    print("column_name:", column_name)
    print("strategy:", strategy)
    print("fill_value:", fill_value)
    print("column_config:", column_config)

    if strategy == "keep":
        return df

    if strategy == "drop":
        return df[df[column_name].notna()]

    if strategy == "fill":
        df[column_name] = df[column_name].fillna(fill_value)
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
        print("ENTERED fill_formula_text")
        if column_config:
            template = column_config.get("null_formula_text", "")
            print("template:", template)
            print("BEFORE")
            print(df[[column_name]].head(10))
            if template:
                mask = df[column_name].isna()
                print("null_count:", int(mask.sum()))
                df.loc[mask, column_name] = df.loc[mask].apply(
                    lambda row: _render_text_template(template, row.to_dict()),
                    axis=1
                )
                print("after handle_nulls sample:")
                print(df[[column_name]].head(10))

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

def apply_user_config(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()

    for col_name, col_cfg in config.items():
        if col_name not in df.columns:
            continue

        # 1) Handle nulls first
        df = handle_nulls(
            df,
            column_name=col_name,
            strategy=col_cfg.get("null_strategy", "keep"),
            fill_value=col_cfg.get("null_fill_value"),
            column_config=col_cfg
        )

        # 2) Apply manual replacements if any
        replacements = col_cfg.get("replacements", [])
        if replacements:
            replace_map = {}
            for item in replacements:
                old_value = item.get("old")
                new_value = item.get("new")
                if old_value is not None:
                    replace_map[old_value] = new_value

            if replace_map:
                df[col_name] = df[col_name].replace(replace_map)

        # 3) Type conversions
        final_type = col_cfg.get("final_type", "text")

        if final_type == "number":
            df[col_name] = pd.to_numeric(df[col_name], errors="coerce")

        elif final_type == "date":
            df[col_name] = pd.to_datetime(df[col_name], errors="coerce")

        elif final_type == "boolean":
            true_value = col_cfg.get("true_value", "")
            false_value = col_cfg.get("false_value", "")
            other_strategy = col_cfg.get("other_values_strategy", "null")

            def map_boolean(v):
                if pd.isna(v):
                    return pd.NA

                if str(v) == str(true_value):
                    return True
                if str(v) == str(false_value):
                    return False

                if other_strategy == "true":
                    return True
                if other_strategy == "false":
                    return False
                if other_strategy == "drop":
                    return "__DROP_ROW__"

                return pd.NA

            mapped = df[col_name].apply(map_boolean)

            if other_strategy == "drop":
                keep_mask = mapped != "__DROP_ROW__"
                df = df[keep_mask].copy()
                mapped = mapped[keep_mask]

            df[col_name] = mapped.replace("__DROP_ROW__", pd.NA)

        else:
            df[col_name] = df[col_name].astype("string")

    return df
    clean_df = df.copy()
    for col, cfg in config.items():
        visual_replacements = parse_replacements(cfg.get("replacements", []))
        manual_replacements = parse_replacements_text(cfg.get("replacements_text", ""))

        # si hay conflicto, el manual pisa al visual
        all_replacements = {**visual_replacements, **manual_replacements}

        clean_df[col] = apply_replacements(clean_df[col], all_replacements)

        if cfg.get("final_type") == "date":
            clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce")

        if cfg.get("final_type") == "boolean":
            clean_df[col] = convert_series_to_boolean(
                clean_df[col],
                cfg.get("true_value", ""),
                cfg.get("false_value", ""),
                cfg.get("other_values_strategy", "null")
            )
            if cfg.get("other_values_strategy") == "drop":
                clean_df = clean_df[clean_df[col] != "__DROP__"]

        if cfg.get("final_type") == "number":
            clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")

        clean_df = handle_nulls(
            df,
            column_name=col,
            strategy=config[col].get("null_strategy", "keep"),
            fill_value=config[col].get("null_fill_value"),
            column_config=config[col])

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

def read_uploaded_dataset(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return pd.read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if filename.endswith(".tsv"):
        return pd.read_csv(uploaded_file, sep="\t")

    raise ValueError("Unsupported file format")