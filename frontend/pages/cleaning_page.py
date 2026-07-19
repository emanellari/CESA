from pathlib import Path
import io

import pandas as pd
import streamlit as st

from api.dataset_api import upload_dataset
from components.cleaning.column_editor import render_column_editor
from constants.navigation import PAGE_EDITOR
from services.cleaning.config_builder import (
    build_default_config,
    generate_form_options_from_config,
)
from services.cleaning.formulas import _safe_eval_expression, _render_text_template
from services.cleaning.profiles import profile_dataset
from services.cleaning.transforms import apply_user_config
from utils.ui_helpers import sanitize_column_name, show_http_error


# ============================================================
# CONFIG / CONTEXT HELPERS
# ============================================================


def _ensure_global_cleaning_config(config: dict) -> None:
    config.setdefault("_drop_columns", [])
    config.setdefault("_case_rules", [])
    config.setdefault("_derived_columns", [])
    config.setdefault("_conditional_rules", [])
    config.setdefault("_row_filters", [])
    config.setdefault("_rename_columns", [])
    config.setdefault("_constant_columns", [])

    dataset_rules = config.setdefault("_dataset_rules", {})
    dataset_rules.setdefault("use_row_as_header", False)
    dataset_rules.setdefault("header_row_index", 0)
    dataset_rules.setdefault("drop_rows_above_header", True)
    dataset_rules.setdefault("drop_duplicate_rows", False)
    dataset_rules.setdefault("drop_empty_rows", False)
    dataset_rules.setdefault("drop_empty_columns", False)
    dataset_rules.setdefault("trim_text_cells", True)
    dataset_rules.setdefault("standardize_missing_values", True)
    dataset_rules.setdefault("normalize_column_names", False)


def _get_column_only_config(df: pd.DataFrame, config: dict) -> dict:
    """Return only configs that belong to real dataframe columns."""
    return {
        col: config[col]
        for col in df.columns
        if isinstance(config.get(col), dict)
    }


def _resolve_cleaning_context():
    """Resolve the dataframe and cleaning config currently active in Streamlit."""
    upload_df = st.session_state.get("upload_preview_df")

    if upload_df is not None:
        df = upload_df.copy()
        dataset_name = st.session_state.get(
            "last_uploaded_name", "cleaned_dataset.xlsx"
        )

        profiles = st.session_state.get("upload_profiles")
        if profiles is None:
            profiles = profile_dataset(df)
            st.session_state.upload_profiles = profiles

        config = st.session_state.get("upload_config")
        if config is None:
            config = build_default_config(df, profiles)
            st.session_state.upload_config = config

        _ensure_global_cleaning_config(config)
        return df, profiles, config, dataset_name, "Upload preview"

    current_df = st.session_state.get("df")

    if current_df is not None:
        df = current_df.copy()
        dataset_name = st.session_state.get(
            "dataset_name", "cleaned_dataset.xlsx"
        )

        if st.session_state.get("cleaning_dataset_name") != dataset_name:
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
        return (
            df,
            st.session_state.cleaning_profiles,
            st.session_state.cleaning_config,
            dataset_name,
            "Active dataset",
        )

    return None, None, None, None, None


# ============================================================
# UI HELPERS
# ============================================================


def _render_cleaning_header(
    dataset_name: str,
    source_label: str,
    df: pd.DataFrame,
) -> None:
    st.markdown(
        f"""
        <div class="clean-header">
            <div class="clean-title">Data cleaning</div>
            <div class="clean-subtitle">
                Clean rows, columns, missing values, transformations,
                derived fields, and output structure before analysis.
            </div>
            <div class="clean-badge">{source_label}: <b>{dataset_name}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_clean_kpi("Rows", f"{len(df):,}", "Original rows")
    with k2:
        _render_clean_kpi("Columns", f"{len(df.columns):,}", "Original columns")
    with k3:
        _render_clean_kpi(
            "Missing cells",
            f"{int(df.isna().sum().sum()):,}",
            "Before cleaning",
        )
    with k4:
        _render_clean_kpi(
            "Duplicates",
            f"{int(df.duplicated().sum()):,}",
            "Full-row duplicates",
        )


def _render_clean_kpi(title: str, value: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="clean-card clean-kpi">
            <div class="clean-kpi-title">{title}</div>
            <div class="clean-kpi-value">{value}</div>
            <div class="clean-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str) -> None:
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    safe_kind = kind if kind in valid_kinds else "info"
    st.markdown(
        f'<div class="clean-{safe_kind}">{message}</div>',
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="clean-panel-title">{title}</div>
        <div class="clean-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# GENERAL TRANSFORM HELPERS
# ============================================================


def _make_unique_column_name(existing_columns, desired_name: str) -> str:
    base_name = sanitize_column_name(desired_name) or "new_column"
    existing_set = set(existing_columns)
    new_name = base_name
    counter = 2

    while new_name in existing_set:
        new_name = f"{base_name}_{counter}"
        counter += 1

    return new_name


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
            if text in {"true", "1", "yes", "y"}:
                return True
            if text in {"false", "0", "no", "n"}:
                return False
            return bool(value)
        if result_type == "date":
            return pd.to_datetime(value, errors="coerce")
        return str(value)
    except Exception:
        return value


def _standardize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    missing_like = {
        "",
        "na",
        "n/a",
        "n.a",
        "nan",
        "null",
        "none",
        "missing",
        "-",
        "--",
    }

    for col in result.columns:
        if result[col].dtype == object:
            series = result[col].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            lower = series.astype("string").str.lower()
            result[col] = series.mask(lower.isin(missing_like), pd.NA)

    return result


def _trim_text_cells(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in result.columns:
        if result[col].dtype == object:
            result[col] = result[col].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    return result


def _normalize_output_column_names(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    rename_map = {}
    used_names = set()

    for col in result.columns:
        base_name = sanitize_column_name(col) or "column"
        new_name = base_name
        counter = 2
        while new_name in used_names:
            new_name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(new_name)
        rename_map[col] = new_name

    return result.rename(columns=rename_map)


def _apply_header_row_rule(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    result = df.copy()
    if not rules.get("use_row_as_header", False) or result.empty:
        return result

    row_index = int(rules.get("header_row_index", 0))
    if row_index < 0 or row_index >= len(result):
        return result

    raw_header = result.iloc[row_index].tolist()
    new_columns = []
    used_names = set()

    for index, value in enumerate(raw_header):
        if pd.isna(value) or str(value).strip() == "":
            base_name = f"column_{index + 1}"
        else:
            base_name = (
                sanitize_column_name(str(value).strip()) or f"column_{index + 1}"
            )

        new_name = base_name
        counter = 2
        while new_name in used_names:
            new_name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(new_name)
        new_columns.append(new_name)

    if rules.get("drop_rows_above_header", True):
        result = result.iloc[row_index + 1 :].copy()

    result.columns = new_columns
    return result.reset_index(drop=True)


def _apply_dataset_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    result = _apply_header_row_rule(df, rules)

    if rules.get("trim_text_cells", True):
        result = _trim_text_cells(result)
    if rules.get("standardize_missing_values", True):
        result = _standardize_missing_values(result)
    if rules.get("drop_empty_rows", False):
        result = result.dropna(how="all")
    if rules.get("drop_empty_columns", False):
        result = result.dropna(axis=1, how="all")
    if rules.get("drop_duplicate_rows", False):
        result = result.drop_duplicates()

    return result.reset_index(drop=True)


def _apply_case_rules(df: pd.DataFrame, case_rules: list) -> pd.DataFrame:
    result = df.copy()

    for rule in case_rules or []:
        col = rule.get("column")
        mode = rule.get("mode", "lower")
        if not col or col not in result.columns:
            continue

        def convert(value):
            if pd.isna(value):
                return value
            text = str(value)
            if mode == "lower":
                return text.lower()
            if mode == "upper":
                return text.upper()
            if mode == "title":
                return text.title()
            if mode == "capitalize":
                return text.capitalize()
            return text

        result[col] = result[col].map(convert)

    return result


def _apply_drop_columns(df: pd.DataFrame, drop_columns: list) -> pd.DataFrame:
    valid = [col for col in (drop_columns or []) if col in df.columns]
    return df.drop(columns=valid) if valid else df.copy()


# ============================================================
# ROW FILTER HELPERS
# ============================================================


def _coerce_comparison_value(series: pd.Series, value):
    numeric_series = pd.to_numeric(series, errors="coerce")
    numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]

    if pd.notna(numeric_value) and numeric_series.notna().sum() > 0:
        return numeric_series, numeric_value
    return series.astype(str), str(value)


def _build_row_filter_mask(df: pd.DataFrame, rule: dict) -> pd.Series:
    col = rule.get("column")
    operator = rule.get("operator", "equals")
    value = rule.get("value", "")
    value_2 = rule.get("value_2", "")

    if not col or col not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[col]
    empty_mask = series.isna() | (series.astype(str).str.strip() == "")

    if operator == "is_empty":
        return empty_mask
    if operator == "is_not_empty":
        return ~empty_mask
    if operator == "contains":
        return series.astype(str).str.contains(
            str(value), case=False, na=False, regex=False
        )
    if operator == "not_contains":
        return ~series.astype(str).str.contains(
            str(value), case=False, na=False, regex=False
        )
    if operator in {"equals", "not_equals"}:
        mask = (
            series.astype(str).str.strip().str.lower()
            == str(value).strip().lower()
        )
        return ~mask if operator == "not_equals" else mask
    if operator in {
        "greater_than",
        "greater_equal",
        "less_than",
        "less_equal",
    }:
        comparable, comparable_value = _coerce_comparison_value(series, value)
        if operator == "greater_than":
            return comparable > comparable_value
        if operator == "greater_equal":
            return comparable >= comparable_value
        if operator == "less_than":
            return comparable < comparable_value
        return comparable <= comparable_value
    if operator == "between":
        numeric_series = pd.to_numeric(series, errors="coerce")
        low = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        high = pd.to_numeric(pd.Series([value_2]), errors="coerce").iloc[0]
        if pd.isna(low) or pd.isna(high):
            return pd.Series(False, index=df.index)
        return numeric_series.between(low, high, inclusive="both")

    return pd.Series(False, index=df.index)


def _apply_row_filters(df: pd.DataFrame, row_filters: list) -> pd.DataFrame:
    result = df.copy()
    for rule in row_filters or []:
        if not rule.get("enabled", True):
            continue
        mask = _build_row_filter_mask(result, rule)
        result = result[mask].copy() if rule.get("action") == "keep" else result[~mask].copy()
    return result.reset_index(drop=True)


# ============================================================
# NEW COLUMN HELPERS
# ============================================================


def _apply_constant_columns(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    result = df.copy()
    for rule in rules or []:
        raw_name = (rule.get("name") or "").strip()
        if not rule.get("enabled", True) or not raw_name:
            continue
        new_col = _make_unique_column_name(result.columns, raw_name)
        result[new_col] = _coerce_value_by_type(
            rule.get("value", ""), rule.get("type", "text")
        )
    return result


def _apply_derived_columns(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    result = df.copy()
    for rule in rules or []:
        raw_name = (rule.get("name") or "").strip()
        formula = (rule.get("formula") or "").strip()
        result_type = rule.get("type", "text")

        if not rule.get("enabled", True) or not raw_name or not formula:
            continue

        new_col = _make_unique_column_name(result.columns, raw_name)
        if result_type == "text":
            result[new_col] = result.apply(
                lambda row: _render_text_template(formula, row.to_dict()),
                axis=1,
            )
        else:
            values = result.apply(
                lambda row: _safe_eval_expression(formula, row.to_dict()),
                axis=1,
            )
            result[new_col] = values.map(
                lambda value: _coerce_value_by_type(value, result_type)
            )
    return result


def _apply_conditional_rules(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    result = df.copy()
    for rule in rules or []:
        target = (rule.get("target_column") or "").strip()
        condition = (rule.get("condition") or "").strip()
        result_type = rule.get("result_type", "text")

        if not rule.get("enabled", True) or not target or not condition:
            continue

        if target not in result.columns:
            target = _make_unique_column_name(result.columns, target)

        def compute(row):
            row_dict = row.to_dict()
            matched = bool(_safe_eval_expression(condition, row_dict))
            chosen = (
                rule.get("true_value", "")
                if matched
                else rule.get("false_value", "")
            )
            return _coerce_value_by_type(chosen, result_type)

        result[target] = result.apply(compute, axis=1)
    return result


# ============================================================
# COLUMN PRE-RULE HELPERS
# ============================================================


def _apply_multi_hot_rules(
    df: pd.DataFrame,
    col: str,
    cfg: dict,
) -> pd.DataFrame:
    result = df.copy()
    if not cfg.get("multi_hot_enabled"):
        return result

    keywords = [
        item.strip().lower()
        for item in cfg.get("multi_hot_keywords", "").splitlines()
        if item.strip()
    ]
    if not keywords:
        return result

    base = result[col].astype(str).str.lower()
    for keyword in keywords:
        new_col = sanitize_column_name(keyword)
        if not new_col:
            continue
        if new_col in result.columns:
            new_col = _make_unique_column_name(
                result.columns, f"{col}_{new_col}"
            )
        result[new_col] = base.str.contains(keyword, na=False, regex=False)

    if not cfg.get("multi_hot_keep_original", True) and col in result.columns:
        result = result.drop(columns=[col])

    return result


def _apply_split_rule(df: pd.DataFrame, col: str, cfg: dict) -> pd.DataFrame:
    result = df.copy()
    if not cfg.get("split_enabled"):
        return result

    new_cols = [
        item.strip()
        for item in cfg.get("split_new_cols", "").split(",")
        if item.strip()
    ]
    if not new_cols:
        return result

    split_df = result[col].astype(str).str.split(
        cfg.get("split_delimiter", " "), expand=True
    )
    for index, desired_name in enumerate(new_cols):
        if index >= split_df.shape[1]:
            break
        new_col = _make_unique_column_name(result.columns, desired_name)
        result[new_col] = split_df[index]

    return result


def _apply_column_level_pre_rules(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    result = df.copy()
    for col, cfg in list(config.items()):
        if not isinstance(cfg, dict) or col not in result.columns:
            continue

        if cfg.get("remove_special_chars"):
            result[col] = result[col].astype(str).str.replace(
                r"[^a-zA-Z0-9\s]", "", regex=True
            )

        result = _apply_multi_hot_rules(result, col, cfg)
        if col in result.columns:
            result = _apply_split_rule(result, col, cfg)

    return result


def _apply_rename_columns(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    result = df.copy()
    rename_map = {}

    for rule in rules or []:
        old_name = rule.get("old_name")
        new_name = (rule.get("new_name") or "").strip()
        if (
            rule.get("enabled", True)
            and old_name in result.columns
            and new_name
        ):
            rename_map[old_name] = sanitize_column_name(new_name) or new_name

    if not rename_map:
        return result

    result = result.rename(columns=rename_map)
    final_columns = []
    used_names = set()
    for col in result.columns:
        base_name = str(col)
        new_name = base_name
        counter = 2
        while new_name in used_names:
            new_name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(new_name)
        final_columns.append(new_name)
    result.columns = final_columns
    return result


def _ensure_config_for_new_columns(df: pd.DataFrame, config: dict) -> None:
    for col in df.columns:
        if isinstance(config.get(col), dict):
            continue
        is_bool = pd.api.types.is_bool_dtype(df[col])
        config[col] = {
            "final_type": "boolean" if is_bool else "text",
            "form_type": "checkbox" if is_bool else "text",
            "use_auto_choices": False,
            "null_strategy": "keep",
            "replacements": [],
            "replacements_text": "",
            "true_value": True,
            "false_value": False,
            "other_values_strategy": "null",
        }


def _build_cleaned_dataframe(
    df_uploaded: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    _ensure_global_cleaning_config(config)
    result = _apply_dataset_rules(
        df_uploaded.copy(), config.get("_dataset_rules", {})
    )
    result = _apply_row_filters(result, config.get("_row_filters", []))
    result = _apply_constant_columns(result, config.get("_constant_columns", []))
    result = _apply_derived_columns(result, config.get("_derived_columns", []))
    result = _apply_conditional_rules(
        result, config.get("_conditional_rules", [])
    )
    result = _apply_column_level_pre_rules(result, config)

    _ensure_config_for_new_columns(result, config)
    result = apply_user_config(
        result, _get_column_only_config(result, config)
    )
    result = _apply_case_rules(result, config.get("_case_rules", []))
    result = _apply_drop_columns(result, config.get("_drop_columns", []))
    result = _apply_rename_columns(result, config.get("_rename_columns", []))

    if config.get("_dataset_rules", {}).get(
        "normalize_column_names", False
    ):
        result = _normalize_output_column_names(result)

    _ensure_config_for_new_columns(result, config)
    return result.reset_index(drop=True)


# ============================================================
# SAVE / PREVIEW HELPERS
# ============================================================


def _build_excel_buffer(
    clean_df: pd.DataFrame,
    uploaded_name: str,
) -> io.BytesIO:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        clean_df.to_excel(writer, index=False, sheet_name="Sheet1")
    output.seek(0)
    output.name = f"{Path(uploaded_name).stem}_cleaned.xlsx"
    return output


def _save_cleaned_dataset(
    df_uploaded: pd.DataFrame,
    config: dict,
    uploaded_name: str,
) -> None:
    clean_df = _build_cleaned_dataframe(df_uploaded, config)
    column_config = _get_column_only_config(clean_df, config)
    form_options = generate_form_options_from_config(clean_df, column_config)
    output = _build_excel_buffer(clean_df, uploaded_name)

    with st.spinner("Uploading cleaned dataset..."):
        response = upload_dataset(
            output,
            options=form_options,
            columns=clean_df.columns.tolist(),
        )

    if not response.ok:
        show_http_error(response)
        return

    payload = response.json()
    st.session_state.dataset_id = payload.get("dataset_id")
    st.session_state.dataset_name = payload.get(
        "dataset_name", output.name
    )
    st.session_state.df = clean_df.copy()

    meta = payload.get("meta", {})
    meta["options"] = form_options
    meta["columns"] = clean_df.columns.tolist()
    st.session_state.dataset_meta = meta
    st.session_state.generated_form_schema = form_options
    st.session_state.cleaned_upload_df = clean_df.copy()

    for key in (
        "upload_preview_df",
        "upload_profiles",
        "upload_config",
        "last_uploaded_name",
    ):
        st.session_state.pop(key, None)

    profiles = profile_dataset(clean_df)
    cleaning_config = build_default_config(clean_df, profiles)
    _ensure_global_cleaning_config(cleaning_config)
    st.session_state.cleaning_profiles = profiles
    st.session_state.cleaning_config = cleaning_config
    st.session_state.cleaning_dataset_name = st.session_state.dataset_name

    st.success("Dataset uploaded successfully.")
    st.session_state.page = PAGE_EDITOR
    st.rerun()


def _generate_preview(df_uploaded: pd.DataFrame, config: dict):
    clean_df = _build_cleaned_dataframe(df_uploaded, config)
    column_config = _get_column_only_config(clean_df, config)
    form_options = generate_form_options_from_config(clean_df, column_config)
    st.session_state.cleaned_upload_df = clean_df
    st.session_state.generated_form_schema = form_options
    return clean_df, form_options


def _render_preview_panel(
    original_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    form_options: dict,
) -> None:
    _render_section_title(
        "Cleaned dataset preview",
        "Preview the first rows after applying the current cleaning configuration.",
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_clean_kpi(
            "Rows",
            f"{len(clean_df):,}",
            f"{len(original_df) - len(clean_df):,} removed",
        )
    with k2:
        _render_clean_kpi(
            "Columns",
            f"{len(clean_df.columns):,}",
            f"{len(clean_df.columns) - len(original_df.columns):+,} change",
        )
    with k3:
        _render_clean_kpi(
            "Missing cells",
            f"{int(clean_df.isna().sum().sum()):,}",
            "After cleaning",
        )
    with k4:
        _render_clean_kpi(
            "Duplicates",
            f"{int(clean_df.duplicated().sum()):,}",
            "After cleaning",
        )

    st.dataframe(clean_df.head(30), use_container_width=True)
    with st.expander("Generated form schema", expanded=False):
        st.json(form_options)


# ============================================================
# RULE UI RENDERERS
# ============================================================


def _render_dataset_rules(config: dict, df_uploaded: pd.DataFrame) -> None:
    _render_section_title(
        "Dataset rules",
        "Apply global cleaning operations before column-specific configuration.",
    )
    rules = config.setdefault("_dataset_rules", {})

    st.markdown("#### Header row")
    rules["use_row_as_header"] = st.checkbox(
        "Use a row as the real header",
        value=rules.get("use_row_as_header", False),
        key="clean_rule_use_row_as_header",
    )

    if rules["use_row_as_header"]:
        max_header_row = max(len(df_uploaded) - 1, 0)
        rules["header_row_index"] = st.number_input(
            "Header row number",
            min_value=0,
            max_value=max_header_row,
            value=min(
                int(rules.get("header_row_index", 0)), max_header_row
            ),
            step=1,
            key="clean_rule_header_row_index",
        )
        rules["drop_rows_above_header"] = st.checkbox(
            "Ignore rows above the selected header",
            value=rules.get("drop_rows_above_header", True),
            key="clean_rule_drop_rows_above_header",
        )

    st.divider()
    st.markdown("#### General cleaning")
    c1, c2, c3 = st.columns(3)

    with c1:
        rules["trim_text_cells"] = st.checkbox(
            "Trim text cells",
            value=rules.get("trim_text_cells", True),
            key="clean_rule_trim_text",
        )
        rules["standardize_missing_values"] = st.checkbox(
            "Standardize missing values",
            value=rules.get("standardize_missing_values", True),
            key="clean_rule_standardize_missing",
        )
    with c2:
        rules["drop_duplicate_rows"] = st.checkbox(
            "Drop duplicate rows",
            value=rules.get("drop_duplicate_rows", False),
            key="clean_rule_drop_duplicates",
        )
        rules["drop_empty_rows"] = st.checkbox(
            "Drop fully empty rows",
            value=rules.get("drop_empty_rows", False),
            key="clean_rule_drop_empty_rows",
        )
    with c3:
        rules["drop_empty_columns"] = st.checkbox(
            "Drop fully empty columns",
            value=rules.get("drop_empty_columns", False),
            key="clean_rule_drop_empty_columns",
        )
        rules["normalize_column_names"] = st.checkbox(
            "Normalize final column names",
            value=rules.get("normalize_column_names", False),
            key="clean_rule_normalize_columns",
        )


def _render_drop_columns_ui(df_uploaded: pd.DataFrame, config: dict) -> None:
    _render_section_title(
        "Drop columns",
        "Select columns that should be removed from the cleaned output.",
    )
    current = config.setdefault("_drop_columns", [])
    config["_drop_columns"] = st.multiselect(
        "Columns to remove",
        options=list(df_uploaded.columns),
        default=[col for col in current if col in df_uploaded.columns],
        key="clean_drop_columns_multiselect",
    )


def _render_rename_columns_ui(df_uploaded: pd.DataFrame, config: dict) -> None:
    _render_section_title(
        "Rename columns",
        "Create clearer output names for analysis.",
    )
    rules = config.setdefault("_rename_columns", [])
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Add rename rule", use_container_width=True, key="add_rename_rule_btn"
        ):
            rules.append(
                {
                    "enabled": True,
                    "old_name": df_uploaded.columns[0]
                    if len(df_uploaded.columns)
                    else "",
                    "new_name": "",
                }
            )
            st.rerun()
    with c2:
        if rules and st.button(
            "Clear rename rules",
            use_container_width=True,
            key="clear_rename_rules_btn",
        ):
            config["_rename_columns"] = []
            st.rerun()

    if not rules:
        _render_alert("info", "No rename rules yet.")

    for index, rule in enumerate(rules):
        with st.expander(f"Rename rule {index + 1}", expanded=True):
            r1, r2, r3, r4 = st.columns([0.8, 1.4, 1.4, 0.8])
            with r1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"rename_enabled_{index}",
                )
            with r2:
                options = list(df_uploaded.columns)
                rule["old_name"] = st.selectbox(
                    "Original column",
                    options,
                    index=options.index(rule.get("old_name"))
                    if rule.get("old_name") in options
                    else 0,
                    key=f"rename_old_{index}",
                )
            with r3:
                rule["new_name"] = st.text_input(
                    "New name",
                    value=rule.get("new_name", ""),
                    key=f"rename_new_{index}",
                )
            with r4:
                if st.button(
                    "Remove",
                    key=f"remove_rename_{index}",
                    use_container_width=True,
                ):
                    rules.pop(index)
                    st.rerun()


def _render_row_filters_ui(df_uploaded: pd.DataFrame, config: dict) -> None:
    _render_section_title(
        "Row filters",
        "Drop or keep rows based on conditions.",
    )
    rules = config.setdefault("_row_filters", [])
    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "Add row filter", use_container_width=True, key="add_row_filter_btn"
        ):
            rules.append(
                {
                    "enabled": True,
                    "action": "drop",
                    "column": df_uploaded.columns[0]
                    if len(df_uploaded.columns)
                    else "",
                    "operator": "equals",
                    "value": "",
                    "value_2": "",
                }
            )
            st.rerun()
    with c2:
        if rules and st.button(
            "Clear row filters",
            use_container_width=True,
            key="clear_row_filters_btn",
        ):
            config["_row_filters"] = []
            st.rerun()

    if not rules:
        _render_alert("info", "No row filters yet.")

    operators = [
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "is_empty",
        "is_not_empty",
        "greater_than",
        "greater_equal",
        "less_than",
        "less_equal",
        "between",
    ]

    for index, rule in enumerate(rules):
        with st.expander(f"Row filter {index + 1}", expanded=True):
            r1, r2, r3, r4 = st.columns([0.8, 1, 1.3, 1.2])
            with r1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"row_filter_enabled_{index}",
                )
            with r2:
                rule["action"] = st.selectbox(
                    "Action",
                    ["drop", "keep"],
                    index=["drop", "keep"].index(rule.get("action", "drop")),
                    key=f"row_filter_action_{index}",
                )
            with r3:
                columns = list(df_uploaded.columns)
                rule["column"] = st.selectbox(
                    "Column",
                    columns,
                    index=columns.index(rule.get("column"))
                    if rule.get("column") in columns
                    else 0,
                    key=f"row_filter_column_{index}",
                )
            with r4:
                current_operator = rule.get("operator", "equals")
                rule["operator"] = st.selectbox(
                    "Condition",
                    operators,
                    index=operators.index(current_operator)
                    if current_operator in operators
                    else 0,
                    key=f"row_filter_operator_{index}",
                )

            if rule["operator"] not in {"is_empty", "is_not_empty"}:
                v1, v2, v3 = st.columns([1.4, 1.4, 0.8])
                with v1:
                    rule["value"] = st.text_input(
                        "Value",
                        value=str(rule.get("value", "")),
                        key=f"row_filter_value_{index}",
                    )
                with v2:
                    if rule["operator"] == "between":
                        rule["value_2"] = st.text_input(
                            "Second value",
                            value=str(rule.get("value_2", "")),
                            key=f"row_filter_value_2_{index}",
                        )
                with v3:
                    if st.button(
                        "Remove",
                        key=f"remove_row_filter_{index}",
                        use_container_width=True,
                    ):
                        rules.pop(index)
                        st.rerun()
            elif st.button(
                "Remove filter",
                key=f"remove_row_filter_{index}",
                use_container_width=True,
            ):
                rules.pop(index)
                st.rerun()


def _render_constant_columns_ui(config: dict) -> None:
    _render_section_title(
        "Constant columns",
        "Add a new column with the same value in every row.",
    )
    rules = config.setdefault("_constant_columns", [])
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Add constant column",
            use_container_width=True,
            key="add_constant_col_btn",
        ):
            rules.append(
                {"enabled": True, "name": "", "type": "text", "value": ""}
            )
            st.rerun()
    with c2:
        if rules and st.button(
            "Clear constant columns",
            use_container_width=True,
            key="clear_constant_cols_btn",
        ):
            config["_constant_columns"] = []
            st.rerun()

    if not rules:
        _render_alert("info", "No constant columns yet.")

    for index, rule in enumerate(rules):
        with st.expander(f"Constant column {index + 1}", expanded=True):
            c1, c2, c3, c4 = st.columns([0.7, 1.2, 1, 1.4])
            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"constant_enabled_{index}",
                )
            with c2:
                rule["name"] = st.text_input(
                    "Column name",
                    value=rule.get("name", ""),
                    key=f"constant_name_{index}",
                )
            with c3:
                types = ["text", "number", "boolean", "date"]
                rule["type"] = st.selectbox(
                    "Type",
                    types,
                    index=types.index(rule.get("type", "text")),
                    key=f"constant_type_{index}",
                )
            with c4:
                rule["value"] = st.text_input(
                    "Value",
                    value=str(rule.get("value", "")),
                    key=f"constant_value_{index}",
                )
            if st.button(
                "Remove constant column",
                key=f"remove_constant_{index}",
                use_container_width=True,
            ):
                rules.pop(index)
                st.rerun()


def _render_derived_columns_ui(config: dict) -> None:
    _render_section_title(
        "Formula / template columns",
        "Create columns from formulas or text templates.",
    )
    rules = config.setdefault("_derived_columns", [])
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Add derived column",
            use_container_width=True,
            key="add_derived_col_btn",
        ):
            rules.append(
                {"enabled": True, "name": "", "type": "text", "formula": ""}
            )
            st.rerun()
    with c2:
        if rules and st.button(
            "Clear derived columns",
            use_container_width=True,
            key="clear_derived_cols_btn",
        ):
            config["_derived_columns"] = []
            st.rerun()

    if not rules:
        _render_alert(
            "info",
            "No derived columns yet. Example: price * quantity or {first_name} {last_name}.",
        )

    for index, rule in enumerate(rules):
        with st.expander(f"Derived column {index + 1}", expanded=True):
            c1, c2, c3 = st.columns([0.7, 1.2, 1])
            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"derived_enabled_{index}",
                )
            with c2:
                rule["name"] = st.text_input(
                    "Column name",
                    value=rule.get("name", ""),
                    key=f"derived_name_{index}",
                )
            with c3:
                types = ["text", "number", "boolean", "date"]
                rule["type"] = st.selectbox(
                    "Result type",
                    types,
                    index=types.index(rule.get("type", "text")),
                    key=f"derived_type_{index}",
                )
            rule["formula"] = st.text_area(
                "Formula or text template",
                value=rule.get("formula", ""),
                key=f"derived_formula_{index}",
                height=90,
            )
            if st.button(
                "Remove derived column",
                key=f"remove_derived_{index}",
                use_container_width=True,
            ):
                rules.pop(index)
                st.rerun()


def _render_conditional_columns_ui(config: dict) -> None:
    _render_section_title(
        "Conditional columns",
        "Create a column using an if/else rule.",
    )
    rules = config.setdefault("_conditional_rules", [])
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Add conditional column",
            use_container_width=True,
            key="add_conditional_col_btn",
        ):
            rules.append(
                {
                    "enabled": True,
                    "target_column": "",
                    "result_type": "text",
                    "condition": "",
                    "true_value": "",
                    "false_value": "",
                }
            )
            st.rerun()
    with c2:
        if rules and st.button(
            "Clear conditional columns",
            use_container_width=True,
            key="clear_conditional_cols_btn",
        ):
            config["_conditional_rules"] = []
            st.rerun()

    if not rules:
        _render_alert("info", "No conditional columns yet.")

    for index, rule in enumerate(rules):
        with st.expander(f"Conditional column {index + 1}", expanded=True):
            c1, c2, c3 = st.columns([0.7, 1.2, 1])
            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"conditional_enabled_{index}",
                )
            with c2:
                rule["target_column"] = st.text_input(
                    "Target column",
                    value=rule.get("target_column", ""),
                    key=f"conditional_target_{index}",
                )
            with c3:
                types = ["text", "number", "boolean", "date"]
                rule["result_type"] = st.selectbox(
                    "Result type",
                    types,
                    index=types.index(rule.get("result_type", "text")),
                    key=f"conditional_type_{index}",
                )
            rule["condition"] = st.text_area(
                "Condition",
                value=rule.get("condition", ""),
                key=f"conditional_condition_{index}",
                height=80,
            )
            v1, v2 = st.columns(2)
            with v1:
                rule["true_value"] = st.text_input(
                    "Value if true",
                    value=str(rule.get("true_value", "")),
                    key=f"conditional_true_{index}",
                )
            with v2:
                rule["false_value"] = st.text_input(
                    "Value if false",
                    value=str(rule.get("false_value", "")),
                    key=f"conditional_false_{index}",
                )
            if st.button(
                "Remove conditional column",
                key=f"remove_conditional_{index}",
                use_container_width=True,
            ):
                rules.pop(index)
                st.rerun()


def _render_column_configuration(
    df_uploaded: pd.DataFrame,
    profiles: dict,
    config: dict,
) -> None:
    _render_section_title(
        "Column configuration",
        "Review detected types, missing values, replacements, transformations, and form behavior.",
    )
    visible_columns = [
        col
        for col in df_uploaded.columns
        if col not in config.get("_drop_columns", [])
    ]

    if not visible_columns:
        _render_alert(
            "warning",
            "All original columns are marked for removal. Keep at least one before saving.",
        )
        return

    for col in visible_columns:
        col_profile = profiles.get(col)
        if col_profile is None:
            col_profile = profile_dataset(df_uploaded[[col]]).get(col, {})
        render_column_editor(col, df_uploaded, col_profile, config)


# ============================================================
# MAIN PAGE
# ============================================================


def render_cleaning_page() -> None:
    (
        df_uploaded,
        profiles,
        config,
        uploaded_name,
        source_label,
    ) = _resolve_cleaning_context()

    if df_uploaded is None:
        st.warning("No dataset loaded.")
        if st.button("Go back", use_container_width=True):
            st.session_state.page = "Datasets"
            st.rerun()
        return

    _ensure_global_cleaning_config(config)
    _render_cleaning_header(uploaded_name, source_label, df_uploaded)

    tabs = st.tabs(
        [
            "Overview",
            "Dataset rules",
            "Row filters",
            "Columns",
            "New columns",
            "Preview",
            "Save",
        ]
    )

    with tabs[0]:
        _render_section_title(
            "Cleaning overview",
            "Start with global rules, then row filters, column configuration, preview, and save.",
        )
        _render_alert(
            "info",
            "Recommended workflow: header → dataset rules → row filters → columns → new columns → preview → save.",
        )
        st.dataframe(df_uploaded.head(20), use_container_width=True)

    with tabs[1]:
        _render_dataset_rules(config, df_uploaded)
        st.divider()
        _render_drop_columns_ui(df_uploaded, config)
        st.divider()
        _render_rename_columns_ui(df_uploaded, config)

    with tabs[2]:
        _render_row_filters_ui(df_uploaded, config)

    with tabs[3]:
        _render_column_configuration(df_uploaded, profiles, config)

    with tabs[4]:
        constant_tab, formula_tab, conditional_tab = st.tabs(
            ["Constant", "Formula / template", "Conditional"]
        )
        with constant_tab:
            _render_constant_columns_ui(config)
        with formula_tab:
            _render_derived_columns_ui(config)
        with conditional_tab:
            _render_conditional_columns_ui(config)

    with tabs[5]:
        _render_section_title(
            "Preview cleaning result",
            "Generate a temporary preview before saving.",
        )
        if st.button(
            "Generate cleaned preview",
            use_container_width=True,
            key="preview_cleaned_btn",
        ):
            try:
                clean_df, form_options = _generate_preview(df_uploaded, config)
                _render_alert("success", "Preview generated successfully.")
                _render_preview_panel(df_uploaded, clean_df, form_options)
            except Exception as exc:
                _render_alert(
                    "danger", f"Error while applying configuration: {exc}"
                )
        elif st.session_state.get("cleaned_upload_df") is not None:
            _render_preview_panel(
                df_uploaded,
                st.session_state.cleaned_upload_df,
                st.session_state.get("generated_form_schema", {}),
            )
        else:
            _render_alert("info", "No preview generated yet.")

    with tabs[6]:
        _render_section_title(
            "Save cleaned dataset",
            "Apply the configuration and upload the cleaned dataset.",
        )
        _render_alert(
            "info",
            "The cleaned file will be uploaded as an .xlsx file and opened in the editor.",
        )
        c1, c2 = st.columns([1.2, 1])
        with c1:
            save_clicked = st.button(
                "Save cleaned dataset",
                use_container_width=True,
                key="save_cleaned_btn",
            )
        with c2:
            preview_first = st.button(
                "Preview before saving",
                use_container_width=True,
                key="preview_from_save_tab_btn",
            )

        if preview_first:
            try:
                clean_df, form_options = _generate_preview(df_uploaded, config)
                _render_alert("success", "Preview generated successfully.")
                _render_preview_panel(df_uploaded, clean_df, form_options)
            except Exception as exc:
                _render_alert(
                    "danger", f"Error while applying configuration: {exc}"
                )

        if save_clicked:
            try:
                _save_cleaned_dataset(df_uploaded, config, uploaded_name)
            except Exception as exc:
                _render_alert(
                    "danger", f"Error while uploading dataset: {exc}"
                )
