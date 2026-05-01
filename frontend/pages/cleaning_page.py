import io
from datetime import datetime

import pandas as pd
import streamlit as st

from api.dataset_api import upload_dataset
from components.cleaning.column_editor import render_column_editor
from constants.navigation import PAGE_EDITOR
from services.cleaning.config_builder import (
    build_default_config,
    generate_form_options_from_config,
)
from services.cleaning.profiles import profile_dataset
from services.cleaning.transforms import apply_user_config
from services.cleaning.formulas import _safe_eval_expression, _render_text_template
from utils.ui_helpers import show_http_error

from utils.ui_helpers import sanitize_column_name


def _resolve_cleaning_context():
    """
    Source of truth for cleaning page:

    1. If there is an upload preview, use it.
    2. Otherwise use the currently selected/saved dataset (df).
    3. cleaning_* stores only metadata/config for the active base dataframe.
    """

    # Fresh upload preview has priority
    upload_df = st.session_state.get("upload_preview_df")
    if upload_df is not None:
        df = upload_df.copy()
        dataset_name = st.session_state.get("last_uploaded_name", "cleaned_dataset.xlsx")

        profiles = st.session_state.get("upload_profiles")
        if profiles is None:
            profiles = profile_dataset(df)
            st.session_state.upload_profiles = profiles

        config = st.session_state.get("upload_config")
        if config is None:
            config = build_default_config(df, profiles)
            st.session_state.upload_config = config

        _ensure_global_cleaning_config(config)
        return df, profiles, config, dataset_name

    # Otherwise use the current selected/saved dataset
    current_df = st.session_state.get("df")
    if current_df is not None:
        df = current_df.copy()
        dataset_name = st.session_state.get("dataset_name", "cleaned_dataset.xlsx")

        # Rebuild cleaning metadata if missing or stale
        cleaning_base_name = st.session_state.get("cleaning_dataset_name")
        if cleaning_base_name != dataset_name:
            profiles = profile_dataset(df)
            config = build_default_config(df, profiles)

            st.session_state.cleaning_profiles = profiles
            st.session_state.cleaning_config = config
            st.session_state.cleaning_dataset_name = dataset_name
        else:
            profiles = st.session_state.get("cleaning_profiles")
            if profiles is None:
                profiles = profile_dataset(df)
                st.session_state.cleaning_profiles = profiles

            config = st.session_state.get("cleaning_config")
            if config is None:
                config = build_default_config(df, profiles)
                st.session_state.cleaning_config = config

        _ensure_global_cleaning_config(st.session_state.cleaning_config)
        return df, st.session_state.cleaning_profiles, st.session_state.cleaning_config, dataset_name

    return None, None, None, None

def _ensure_global_cleaning_config(config: dict):
    config.setdefault("_drop_columns", [])
    config.setdefault("_case_rules", [])
    config.setdefault("_derived_columns", [])
    config.setdefault("_conditional_rules", [])


def _coerce_value_by_type(value, result_type: str):
    if value is None or value == "":
        return None

    try:
        if result_type == "number":
            return float(value)
        if result_type == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in ["true", "1", "yes", "y"]:
                return True
            if text in ["false", "0", "no", "n"]:
                return False
            return bool(value)
        if result_type == "date":
            return pd.to_datetime(value, errors="coerce")
        return str(value)
    except Exception:
        return value


def _apply_case_rules(df: pd.DataFrame, case_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in case_rules or []:
        col = rule.get("column")
        mode = rule.get("mode", "lower")

        if not col or col not in df.columns:
            continue

        s = df[col]

        def _convert(x):
            if pd.isna(x):
                return x
            text = str(x)
            if mode == "lower":
                return text.lower()
            if mode == "upper":
                return text.upper()
            if mode == "title":
                return text.title()
            if mode == "capitalize":
                return text.capitalize()
            return text

        df[col] = s.map(_convert)

    return df


def _apply_derived_columns(df: pd.DataFrame, derived_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in derived_rules or []:
        new_col = (rule.get("name") or "").strip()
        result_type = rule.get("type", "text")
        formula = (rule.get("formula") or "").strip()

        if not new_col or not formula:
            continue

        if result_type == "text":
            df[new_col] = df.apply(
                lambda row: _render_text_template(formula, row.to_dict()),
                axis=1,
            )
        else:
            values = df.apply(
                lambda row: _safe_eval_expression(formula, row.to_dict()),
                axis=1,
            )
            df[new_col] = values.map(lambda x: _coerce_value_by_type(x, result_type))

    return df


def _apply_conditional_rules(df: pd.DataFrame, conditional_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in conditional_rules or []:
        target_column = (rule.get("target_column") or "").strip()
        result_type = rule.get("result_type", "text")
        condition = (rule.get("condition") or "").strip()

        true_value = rule.get("true_value", "")
        false_value = rule.get("false_value", "")

        if not target_column or not condition:
            continue

        def _compute(row):
            row_dict = row.to_dict()
            result = _safe_eval_expression(condition, row_dict)
            chosen = true_value if bool(result) else false_value
            return _coerce_value_by_type(chosen, result_type)

        df[target_column] = df.apply(_compute, axis=1)

    return df


def _apply_drop_columns(df: pd.DataFrame, drop_columns: list) -> pd.DataFrame:
    df = df.copy()
    valid_drop_cols = [c for c in (drop_columns or []) if c in df.columns]
    if valid_drop_cols:
        df = df.drop(columns=valid_drop_cols)
    return df


def _build_cleaned_dataframe(df_uploaded: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df_uploaded.copy()

    _ensure_global_cleaning_config(config)

    # 1. global derived columns
    df = _apply_derived_columns(df, config.get("_derived_columns", []))

    # 2. global conditional rules
    df = _apply_conditional_rules(df, config.get("_conditional_rules", []))

    for col, cfg in list(config.items()):

        if not isinstance(cfg, dict):
            continue

        if col not in df.columns:
            continue

        # =========================
        # TEXT CLEANING
        # =========================
        if cfg.get("remove_special_chars"):
            df[col] = df[col].astype(str).str.replace(
                r"[^a-zA-Z0-9\s]",
                "",
                regex=True
            )

        # =========================
        # MULTI HOT (UNA SOLA VEZ)
        # =========================
        if cfg.get("multi_hot_enabled"):

            raw = cfg.get("multi_hot_keywords", "")

            keywords = [
                k.strip().lower()
                for k in raw.splitlines()
                if k.strip()
            ]

            base = df[col].astype(str).str.lower()

            for k in keywords:
                new_col = sanitize_column_name(k)

                if new_col in df.columns:
                    new_col = f"{col}_{new_col}"


                df[new_col] = base.str.contains(
                    k,
                    na=False,
                    regex=False
                )

            if not cfg.get("multi_hot_keep_original", True):
                df = df.drop(columns=[col])

        # =========================
        # SPLIT
        # =========================
        if cfg.get("split_enabled"):

            delimiter = cfg.get("split_delimiter", " ")

            new_cols = [
                c.strip()
                for c in cfg.get("split_new_cols", "").split(",")
                if c.strip()
            ]

            if new_cols:
                split_df = df[col].astype(str).str.split(delimiter, expand=True)

                for i, new_col in enumerate(new_cols):
                    if i < split_df.shape[1]:
                        df[new_col] = split_df[i]
    df = apply_user_config(df, config)
    # ==================================================

    # 4. global text case rules
    df = _apply_case_rules(df, config.get("_case_rules", []))

    # 5. drop columns at the end
    df = _apply_drop_columns(df, config.get("_drop_columns", []))
    for col in df.columns:
        if col not in config:
            config[col] = {
                "final_type": "boolean" if df[col].dtype == bool else "text",
                "form_type": "checkbox" if df[col].dtype == bool else "text",
                "use_auto_choices": False,
                "null_strategy": "keep",
                "replacements": [],
                "replacements_text": "",
                "true_value": True,
                "false_value": False,
                "other_values_strategy": "null",
            }
    return df

def _save_cleaned_dataset(df_uploaded: pd.DataFrame, config: dict, uploaded_name: str):
    clean_df = _build_cleaned_dataframe(df_uploaded, config)
    form_options = generate_form_options_from_config(clean_df, config)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        clean_df.to_excel(writer, index=False, sheet_name="Sheet1")
    output.seek(0)
    output.name = uploaded_name

    with st.spinner("Uploading cleaned dataset..."):
        response = upload_dataset(
            output,
            options=form_options,
            columns=clean_df.columns.tolist(),
        )

    if response.ok:
        payload = response.json()

        st.session_state.dataset_id = payload.get("dataset_id")
        st.session_state.dataset_name = payload.get("dataset_name", uploaded_name)
        st.session_state.df = clean_df.copy()

        meta = payload.get("meta", {})
        meta["options"] = form_options
        meta["columns"] = clean_df.columns.tolist()

        st.session_state.dataset_meta = meta
        st.session_state.generated_form_schema = form_options
        st.session_state.cleaned_upload_df = clean_df.copy()

        # Clear upload context because the cleaned dataset is now the active saved dataset
        st.session_state.pop("upload_preview_df", None)
        st.session_state.pop("upload_profiles", None)
        st.session_state.pop("upload_config", None)
        st.session_state.pop("last_uploaded_name", None)

        # Rebuild cleaning context from the saved clean dataset
        st.session_state.cleaning_profiles = profile_dataset(clean_df)
        st.session_state.cleaning_config = build_default_config(
            clean_df, st.session_state.cleaning_profiles
        )
        _ensure_global_cleaning_config(st.session_state.cleaning_config)
        st.session_state.cleaning_dataset_name = st.session_state.dataset_name

        st.success("Dataset uploaded successfully.")
        st.session_state.page = PAGE_EDITOR
        st.rerun()
    else:
        show_http_error(response)


def render_cleaning_page():
    df_uploaded, profiles, config, uploaded_name = _resolve_cleaning_context()

    if df_uploaded is None:
        st.warning("No dataset loaded.")
        if st.button("Go back"):
            st.session_state.page = "Datasets"
            st.rerun()
        return

    _ensure_global_cleaning_config(config)



    st.markdown("## Column configuration")
    st.caption("Review detected types, missing value handling, replacements, and form behavior.")

    for col in df_uploaded.columns:
        if col not in config.get("_drop_columns", []):
            render_column_editor(col, df_uploaded, profiles[col], config)

    action_bottom_1, action_bottom_2 = st.columns(2)

    with action_bottom_1:
        if st.button("Preview cleaned dataset", use_container_width=True, key="preview_cleaned_bottom_btn"):
            try:
                clean_df = _build_cleaned_dataframe(df_uploaded, config)
                st.session_state.cleaned_upload_df = clean_df

                st.success("Cleaned dataset preview generated successfully.")
                st.dataframe(clean_df.head(20), use_container_width=True)

                form_options = generate_form_options_from_config(clean_df, config)
                st.markdown("### Generated form schema preview")
                st.json(form_options)

            except Exception as e:
                st.error(f"Error while applying configuration: {e}")

    with action_bottom_2:
        if st.button("Save cleaned dataset", use_container_width=True, key="save_cleaned_bottom_btn"):
            try:
                _save_cleaned_dataset(df_uploaded, config, uploaded_name)
            except Exception as e:
                st.error(f"Error while uploading dataset: {e}")