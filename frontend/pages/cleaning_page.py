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

def _ensure_global_cleaning_config(config: dict):
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
    """
    Return only real dataframe column configs.

    Internal cleaning keys start with "_" and must not be passed to older
    column-based functions such as apply_user_config or form schema generation.
    """
    column_config = {}

    for col in df.columns:
        cfg = config.get(col)

        if isinstance(cfg, dict):
            column_config[col] = cfg

    return column_config


def _resolve_cleaning_context():
    """
    Source of truth for cleaning page:

    1. If there is an upload preview, use it.
    2. Otherwise use the currently selected/saved dataset.
    3. cleaning_* stores metadata/config for the active base dataframe.
    """

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
        return df, profiles, config, dataset_name, "Upload preview"

    current_df = st.session_state.get("df")

    if current_df is not None:
        df = current_df.copy()
        dataset_name = st.session_state.get("dataset_name", "cleaned_dataset.xlsx")

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

def _render_cleaning_header(dataset_name: str, source_label: str, df: pd.DataFrame):
    st.markdown(
        f"""
        <div class="clean-header">
            <div class="clean-title">Data cleaning</div>
            <div class="clean-subtitle">
                Clean rows, columns, missing values, transformations, derived fields, and output structure before analysis.
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
        missing_cells = int(df.isna().sum().sum())
        _render_clean_kpi("Missing cells", f"{missing_cells:,}", "Before cleaning")

    with k4:
        duplicated_rows = int(df.duplicated().sum())
        _render_clean_kpi("Duplicates", f"{duplicated_rows:,}", "Full-row duplicates")


def _render_clean_kpi(title: str, value: str, subtitle: str = ""):
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


def _render_alert(kind: str, message: str):
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="clean-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = ""):
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
    new_name = base_name
    counter = 2

    existing_set = set(existing_columns)

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


def _standardize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

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

    for col in df.columns:
        if df[col].dtype == object:
            s = df[col].astype(str).str.strip()
            df[col] = s.mask(s.str.lower().isin(missing_like), pd.NA)

    return df


def _trim_text_cells(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(
                lambda x: x.strip() if isinstance(x, str) else x
            )

    return df


def _normalize_output_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rename_map = {}
    used_names = set()

    for col in df.columns:
        clean_name = sanitize_column_name(col) or "column"
        new_name = clean_name
        counter = 2

        while new_name in used_names:
            new_name = f"{clean_name}_{counter}"
            counter += 1

        used_names.add(new_name)
        rename_map[col] = new_name

    return df.rename(columns=rename_map)


def _apply_header_row_rule(df: pd.DataFrame, dataset_rules: dict) -> pd.DataFrame:
    """
    Promote a selected row to header and optionally remove rows above it.

    Useful when uploaded Excel/CSV files contain title rows, notes,
    empty rows, or metadata before the real table header.
    """
    df = df.copy()

    if not dataset_rules.get("use_row_as_header", False):
        return df

    if df.empty:
        return df

    header_row_index = int(dataset_rules.get("header_row_index", 0))

    if header_row_index < 0 or header_row_index >= len(df):
        return df

    raw_header = df.iloc[header_row_index].tolist()

    new_columns = []
    used_names = set()

    for i, value in enumerate(raw_header):
        if pd.isna(value) or str(value).strip() == "":
            base_name = f"column_{i + 1}"
        else:
            base_name = sanitize_column_name(str(value).strip()) or f"column_{i + 1}"

        new_name = base_name
        counter = 2

        while new_name in used_names:
            new_name = f"{base_name}_{counter}"
            counter += 1

        used_names.add(new_name)
        new_columns.append(new_name)

    if dataset_rules.get("drop_rows_above_header", True):
        df = df.iloc[header_row_index + 1:].copy()
    else:
        df = df.copy()

    df.columns = new_columns
    df = df.reset_index(drop=True)

    return df


def _apply_dataset_rules(df: pd.DataFrame, dataset_rules: dict) -> pd.DataFrame:
    df = df.copy()

    # 1. Promote selected row to header before any other cleaning.
    df = _apply_header_row_rule(df, dataset_rules)

    # 2. Clean text before checking empty rows.
    if dataset_rules.get("trim_text_cells", True):
        df = _trim_text_cells(df)

    if dataset_rules.get("standardize_missing_values", True):
        df = _standardize_missing_values(df)

    # 3. Remove empty structures.
    if dataset_rules.get("drop_empty_rows", False):
        df = df.dropna(how="all")

    if dataset_rules.get("drop_empty_columns", False):
        df = df.dropna(axis=1, how="all")

    # 4. Remove duplicates.
    if dataset_rules.get("drop_duplicate_rows", False):
        df = df.drop_duplicates()

    return df.reset_index(drop=True)


def _apply_case_rules(df: pd.DataFrame, case_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in case_rules or []:
        col = rule.get("column")
        mode = rule.get("mode", "lower")

        if not col or col not in df.columns:
            continue

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

        df[col] = df[col].map(_convert)

    return df


def _apply_drop_columns(df: pd.DataFrame, drop_columns: list) -> pd.DataFrame:
    df = df.copy()
    valid_drop_cols = [c for c in (drop_columns or []) if c in df.columns]

    if valid_drop_cols:
        df = df.drop(columns=valid_drop_cols)

    return df


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

    s = df[col]

    if operator == "is_empty":
        return s.isna() | (s.astype(str).str.strip() == "")

    if operator == "is_not_empty":
        return ~(s.isna() | (s.astype(str).str.strip() == ""))

    if operator == "contains":
        return s.astype(str).str.contains(str(value), case=False, na=False, regex=False)

    if operator == "not_contains":
        return ~s.astype(str).str.contains(str(value), case=False, na=False, regex=False)

    if operator in ["equals", "not_equals"]:
        mask = s.astype(str).str.strip().str.lower() == str(value).strip().lower()
        return ~mask if operator == "not_equals" else mask

    if operator in ["greater_than", "greater_equal", "less_than", "less_equal"]:
        comp_s, comp_value = _coerce_comparison_value(s, value)

        if operator == "greater_than":
            return comp_s > comp_value

        if operator == "greater_equal":
            return comp_s >= comp_value

        if operator == "less_than":
            return comp_s < comp_value

        if operator == "less_equal":
            return comp_s <= comp_value

    if operator == "between":
        numeric_s = pd.to_numeric(s, errors="coerce")
        low = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        high = pd.to_numeric(pd.Series([value_2]), errors="coerce").iloc[0]

        if pd.isna(low) or pd.isna(high):
            return pd.Series(False, index=df.index)

        return numeric_s.between(low, high, inclusive="both")

    return pd.Series(False, index=df.index)


def _apply_row_filters(df: pd.DataFrame, row_filters: list) -> pd.DataFrame:
    df = df.copy()

    for rule in row_filters or []:
        enabled = rule.get("enabled", True)

        if not enabled:
            continue

        action = rule.get("action", "drop")
        mask = _build_row_filter_mask(df, rule)

        if action == "keep":
            df = df[mask].copy()
        else:
            df = df[~mask].copy()

    return df.reset_index(drop=True)


# ============================================================
# NEW COLUMN HELPERS
# ============================================================

def _apply_constant_columns(df: pd.DataFrame, constant_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in constant_rules or []:
        enabled = rule.get("enabled", True)
        raw_name = (rule.get("name") or "").strip()
        value = rule.get("value", "")
        result_type = rule.get("type", "text")

        if not enabled or not raw_name:
            continue

        new_col = _make_unique_column_name(df.columns, raw_name)
        df[new_col] = _coerce_value_by_type(value, result_type)

    return df


def _apply_derived_columns(df: pd.DataFrame, derived_rules: list) -> pd.DataFrame:
    df = df.copy()

    for rule in derived_rules or []:
        enabled = rule.get("enabled", True)
        raw_name = (rule.get("name") or "").strip()
        result_type = rule.get("type", "text")
        formula = (rule.get("formula") or "").strip()

        if not enabled or not raw_name or not formula:
            continue

        new_col = _make_unique_column_name(df.columns, raw_name)

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
        enabled = rule.get("enabled", True)
        raw_target_column = (rule.get("target_column") or "").strip()
        result_type = rule.get("result_type", "text")
        condition = (rule.get("condition") or "").strip()

        true_value = rule.get("true_value", "")
        false_value = rule.get("false_value", "")

        if not enabled or not raw_target_column or not condition:
            continue

        target_column = raw_target_column

        if target_column not in df.columns:
            target_column = _make_unique_column_name(df.columns, target_column)

        def _compute(row):
            row_dict = row.to_dict()
            result = _safe_eval_expression(condition, row_dict)
            chosen = true_value if bool(result) else false_value
            return _coerce_value_by_type(chosen, result_type)

        df[target_column] = df.apply(_compute, axis=1)

    return df


# ============================================================
# COLUMN PRE-RULE HELPERS
# ============================================================

def _apply_multi_hot_rules(df: pd.DataFrame, col: str, cfg: dict) -> pd.DataFrame:
    df = df.copy()

    if not cfg.get("multi_hot_enabled"):
        return df

    raw = cfg.get("multi_hot_keywords", "")

    keywords = [
        k.strip().lower()
        for k in raw.splitlines()
        if k.strip()
    ]

    if not keywords:
        return df

    base = df[col].astype(str).str.lower()

    for keyword in keywords:
        new_col = sanitize_column_name(keyword)

        if not new_col:
            continue

        if new_col in df.columns:
            new_col = _make_unique_column_name(df.columns, f"{col}_{new_col}")

        df[new_col] = base.str.contains(
            keyword,
            na=False,
            regex=False,
        )

    if not cfg.get("multi_hot_keep_original", True) and col in df.columns:
        df = df.drop(columns=[col])

    return df


def _apply_split_rule(df: pd.DataFrame, col: str, cfg: dict) -> pd.DataFrame:
    df = df.copy()

    if not cfg.get("split_enabled"):
        return df

    delimiter = cfg.get("split_delimiter", " ")

    new_cols = [
        c.strip()
        for c in cfg.get("split_new_cols", "").split(",")
        if c.strip()
    ]

    if not new_cols:
        return df

    split_df = df[col].astype(str).str.split(delimiter, expand=True)

    for i, raw_new_col in enumerate(new_cols):
        if i >= split_df.shape[1]:
            continue

        new_col = _make_unique_column_name(df.columns, raw_new_col)
        df[new_col] = split_df[i]

    return df


def _apply_column_level_pre_rules(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()

    for col, cfg in list(config.items()):
        if not isinstance(cfg, dict):
            continue

        if col not in df.columns:
            continue

        if cfg.get("remove_special_chars"):
            df[col] = df[col].astype(str).str.replace(
                r"[^a-zA-Z0-9\s]",
                "",
                regex=True,
            )

        df = _apply_multi_hot_rules(df, col, cfg)

        if col in df.columns:
            df = _apply_split_rule(df, col, cfg)

    return df


def _apply_rename_columns(df: pd.DataFrame, rename_rules: list) -> pd.DataFrame:
    df = df.copy()

    rename_map = {}

    for rule in rename_rules or []:
        enabled = rule.get("enabled", True)
        old_name = rule.get("old_name")
        new_name = (rule.get("new_name") or "").strip()

        if not enabled or not old_name or old_name not in df.columns or not new_name:
            continue

        clean_new_name = sanitize_column_name(new_name) or new_name
        rename_map[old_name] = clean_new_name

    if rename_map:
        df = df.rename(columns=rename_map)

        # Ensure uniqueness after rename by suffixing duplicates.
        new_columns = []
        used_names = set()

        for col in df.columns:
            base_name = str(col)
            new_col = base_name
            counter = 2

            while new_col in used_names:
                new_col = f"{base_name}_{counter}"
                counter += 1

            used_names.add(new_col)
            new_columns.append(new_col)

        df.columns = new_columns

    return df


def _ensure_config_for_new_columns(df: pd.DataFrame, config: dict):
    for col in df.columns:
        if col in config:
            continue

        is_bool = df[col].dtype == bool

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


def _build_cleaned_dataframe(df_uploaded: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df_uploaded.copy()

    _ensure_global_cleaning_config(config)

    # 1. Dataset-level rules, including optional header-row promotion.
    df = _apply_dataset_rules(df, config.get("_dataset_rules", {}))

    # 2. Row filters.
    df = _apply_row_filters(df, config.get("_row_filters", []))

    # 3. New columns.
    df = _apply_constant_columns(df, config.get("_constant_columns", []))
    df = _apply_derived_columns(df, config.get("_derived_columns", []))
    df = _apply_conditional_rules(df, config.get("_conditional_rules", []))

    # 4. Column-level custom rules from column editor.
    df = _apply_column_level_pre_rules(df, config)

    # 5. Ensure newly created columns have safe config before old pipeline.
    _ensure_config_for_new_columns(df, config)

    # 6. Existing user config transform pipeline.
    column_only_config = _get_column_only_config(df, config)
    df = apply_user_config(df, column_only_config)

    # 7. Global text case rules.
    df = _apply_case_rules(df, config.get("_case_rules", []))

    # 8. Drop and rename columns near the end.
    df = _apply_drop_columns(df, config.get("_drop_columns", []))
    df = _apply_rename_columns(df, config.get("_rename_columns", []))

    # 9. Optional final column-name normalization.
    dataset_rules = config.get("_dataset_rules", {})
    if dataset_rules.get("normalize_column_names", False):
        df = _normalize_output_column_names(df)

    # 10. Final config safety after drops/renames/normalization.
    _ensure_config_for_new_columns(df, config)

    return df.reset_index(drop=True)


# ============================================================
# SAVE / PREVIEW HELPERS
# ============================================================

def _build_excel_buffer(clean_df: pd.DataFrame, uploaded_name: str) -> io.BytesIO:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        clean_df.to_excel(writer, index=False, sheet_name="Sheet1")

    output.seek(0)
    output.name = uploaded_name

    return output


def _save_cleaned_dataset(df_uploaded: pd.DataFrame, config: dict, uploaded_name: str):
    clean_df = _build_cleaned_dataframe(df_uploaded, config)

    column_only_config = _get_column_only_config(clean_df, config)
    form_options = generate_form_options_from_config(clean_df, column_only_config)

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
    st.session_state.dataset_name = payload.get("dataset_name", uploaded_name)
    st.session_state.df = clean_df.copy()

    meta = payload.get("meta", {})
    meta["options"] = form_options
    meta["columns"] = clean_df.columns.tolist()

    st.session_state.dataset_meta = meta
    st.session_state.generated_form_schema = form_options
    st.session_state.cleaned_upload_df = clean_df.copy()

    st.session_state.pop("upload_preview_df", None)
    st.session_state.pop("upload_profiles", None)
    st.session_state.pop("upload_config", None)
    st.session_state.pop("last_uploaded_name", None)

    st.session_state.cleaning_profiles = profile_dataset(clean_df)
    st.session_state.cleaning_config = build_default_config(
        clean_df,
        st.session_state.cleaning_profiles,
    )
    _ensure_global_cleaning_config(st.session_state.cleaning_config)

    st.session_state.cleaning_dataset_name = st.session_state.dataset_name

    st.success("Dataset uploaded successfully.")
    st.session_state.page = PAGE_EDITOR
    st.rerun()


def _generate_preview(df_uploaded: pd.DataFrame, config: dict):
    clean_df = _build_cleaned_dataframe(df_uploaded, config)

    column_only_config = _get_column_only_config(clean_df, config)
    form_options = generate_form_options_from_config(clean_df, column_only_config)

    st.session_state.cleaned_upload_df = clean_df
    st.session_state.generated_form_schema = form_options

    return clean_df, form_options


def _render_preview_panel(original_df: pd.DataFrame, clean_df: pd.DataFrame, form_options: dict):
    _render_section_title(
        "Cleaned dataset preview",
        "Preview the first rows after applying the current cleaning configuration.",
    )

    rows_removed = len(original_df) - len(clean_df)
    columns_delta = len(clean_df.columns) - len(original_df.columns)

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        _render_clean_kpi("Rows", f"{len(clean_df):,}", f"{rows_removed:,} removed")

    with k2:
        _render_clean_kpi("Columns", f"{len(clean_df.columns):,}", f"{columns_delta:+,} change")

    with k3:
        missing_cells = int(clean_df.isna().sum().sum())
        _render_clean_kpi("Missing cells", f"{missing_cells:,}", "After cleaning")

    with k4:
        duplicates = int(clean_df.duplicated().sum())
        _render_clean_kpi("Duplicates", f"{duplicates:,}", "After cleaning")

    st.dataframe(clean_df.head(30), use_container_width=True)

    with st.expander("Generated form schema", expanded=False):
        st.json(form_options)


# ============================================================
# RULE UI RENDERERS
# ============================================================

def _render_dataset_rules(config: dict, df_uploaded: pd.DataFrame):
    _render_section_title(
        "Dataset rules",
        "Apply global cleaning operations to the whole dataset before column-specific configuration.",
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
            value=min(int(rules.get("header_row_index", 0)), max_header_row),
            step=1,
            key="clean_rule_header_row_index",
            help="0 means the first visible row, 1 means the second visible row, etc.",
        )

        rules["drop_rows_above_header"] = st.checkbox(
            "Ignore rows above the selected header",
            value=rules.get("drop_rows_above_header", True),
            key="clean_rule_drop_rows_above_header",
        )

        _render_alert(
            "info",
            "The selected row will become the column names. Rows above it can be ignored automatically.",
        )

    st.divider()

    st.markdown("#### General cleaning")

    c1, c2, c3 = st.columns(3)

    with c1:
        rules["trim_text_cells"] = st.checkbox(
            "Trim text cells",
            value=rules.get("trim_text_cells", True),
            key="clean_rule_trim_text",
            help="Removes spaces before and after text values. Example: ' Albania ' becomes 'Albania'.",
        )

        rules["standardize_missing_values"] = st.checkbox(
            "Standardize missing values",
            value=rules.get("standardize_missing_values", True),
            key="clean_rule_standardize_missing",
            help="Converts blank values, NA, null, none, '-', and similar labels into missing values.",
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
            help="Drops only rows where every cell is empty after trimming and missing-value standardization.",
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
            help="Converts final column names to safer names for code and analysis.",
        )

    _render_alert(
        "info",
        "Tip: if empty rows are not being removed, they probably contain spaces or hidden text. Keep Trim text cells and Standardize missing values enabled.",
    )


def _render_drop_columns_ui(df_uploaded: pd.DataFrame, config: dict):
    _render_section_title(
        "Drop columns",
        "Select columns that should be removed from the cleaned output.",
    )

    current_drop = config.setdefault("_drop_columns", [])

    selected = st.multiselect(
        "Columns to remove",
        options=list(df_uploaded.columns),
        default=[c for c in current_drop if c in df_uploaded.columns],
        key="clean_drop_columns_multiselect",
    )

    config["_drop_columns"] = selected

    if selected:
        _render_alert("warning", f"{len(selected)} column(s) are marked for removal.")
    else:
        _render_alert("info", "No columns are currently marked for removal.")


def _render_rename_columns_ui(df_uploaded: pd.DataFrame, config: dict):
    _render_section_title(
        "Rename columns",
        "Create output column names that are clearer and safer for analysis.",
    )

    rename_rules = config.setdefault("_rename_columns", [])

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Add rename rule", use_container_width=True, key="add_rename_rule_btn"):
            rename_rules.append({
                "enabled": True,
                "old_name": df_uploaded.columns[0] if len(df_uploaded.columns) else "",
                "new_name": "",
            })
            st.rerun()

    with c2:
        if rename_rules and st.button("Clear rename rules", use_container_width=True, key="clear_rename_rules_btn"):
            config["_rename_columns"] = []
            st.rerun()

    if not rename_rules:
        _render_alert("info", "No rename rules yet.")

    for i, rule in enumerate(rename_rules):
        with st.expander(f"Rename rule {i + 1}", expanded=True):
            r1, r2, r3, r4 = st.columns([0.8, 1.4, 1.4, 0.8])

            with r1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"rename_enabled_{i}",
                )

            with r2:
                rule["old_name"] = st.selectbox(
                    "Original column",
                    list(df_uploaded.columns),
                    index=list(df_uploaded.columns).index(rule.get("old_name"))
                    if rule.get("old_name") in df_uploaded.columns
                    else 0,
                    key=f"rename_old_{i}",
                )

            with r3:
                rule["new_name"] = st.text_input(
                    "New name",
                    value=rule.get("new_name", ""),
                    key=f"rename_new_{i}",
                )

            with r4:
                if st.button("Remove", key=f"remove_rename_{i}", use_container_width=True):
                    rename_rules.pop(i)
                    st.rerun()


def _render_row_filters_ui(df_uploaded: pd.DataFrame, config: dict):
    _render_section_title(
        "Row filters",
        "Drop or keep rows based on conditions. Useful for removing test rows, invalid records, or unwanted categories.",
    )

    row_filters = config.setdefault("_row_filters", [])

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Add row filter", use_container_width=True, key="add_row_filter_btn"):
            row_filters.append({
                "enabled": True,
                "action": "drop",
                "column": df_uploaded.columns[0] if len(df_uploaded.columns) else "",
                "operator": "equals",
                "value": "",
                "value_2": "",
            })
            st.rerun()

    with c2:
        if row_filters and st.button("Clear row filters", use_container_width=True, key="clear_row_filters_btn"):
            config["_row_filters"] = []
            st.rerun()

    if not row_filters:
        _render_alert(
            "info",
            "No row filters yet. Add one to drop or keep rows matching a condition.",
        )

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

    for i, rule in enumerate(row_filters):
        with st.expander(f"Row filter {i + 1}", expanded=True):
            r1, r2, r3, r4 = st.columns([0.8, 1, 1.3, 1.2])

            with r1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"row_filter_enabled_{i}",
                )

            with r2:
                rule["action"] = st.selectbox(
                    "Action",
                    ["drop", "keep"],
                    index=["drop", "keep"].index(rule.get("action", "drop")),
                    key=f"row_filter_action_{i}",
                )

            with r3:
                rule["column"] = st.selectbox(
                    "Column",
                    list(df_uploaded.columns),
                    index=list(df_uploaded.columns).index(rule.get("column"))
                    if rule.get("column") in df_uploaded.columns
                    else 0,
                    key=f"row_filter_column_{i}",
                )

            with r4:
                rule["operator"] = st.selectbox(
                    "Condition",
                    operators,
                    index=operators.index(rule.get("operator", "equals"))
                    if rule.get("operator", "equals") in operators
                    else 0,
                    key=f"row_filter_operator_{i}",
                )

            if rule["operator"] not in ["is_empty", "is_not_empty"]:
                v1, v2, v3 = st.columns([1.4, 1.4, 0.8])

                with v1:
                    rule["value"] = st.text_input(
                        "Value",
                        value=str(rule.get("value", "")),
                        key=f"row_filter_value_{i}",
                    )

                with v2:
                    if rule["operator"] == "between":
                        rule["value_2"] = st.text_input(
                            "Second value",
                            value=str(rule.get("value_2", "")),
                            key=f"row_filter_value_2_{i}",
                        )
                    else:
                        st.empty()

                with v3:
                    if st.button("Remove", key=f"remove_row_filter_{i}", use_container_width=True):
                        row_filters.pop(i)
                        st.rerun()
            else:
                if st.button("Remove filter", key=f"remove_row_filter_{i}", use_container_width=True):
                    row_filters.pop(i)
                    st.rerun()


def _render_constant_columns_ui(config: dict):
    _render_section_title(
        "Constant columns",
        "Add a new column with the same value in every row.",
    )

    constant_rules = config.setdefault("_constant_columns", [])

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Add constant column", use_container_width=True, key="add_constant_col_btn"):
            constant_rules.append({
                "enabled": True,
                "name": "",
                "type": "text",
                "value": "",
            })
            st.rerun()

    with c2:
        if constant_rules and st.button("Clear constant columns", use_container_width=True, key="clear_constant_cols_btn"):
            config["_constant_columns"] = []
            st.rerun()

    if not constant_rules:
        _render_alert("info", "No constant columns yet.")

    for i, rule in enumerate(constant_rules):
        with st.expander(f"Constant column {i + 1}", expanded=True):
            c1, c2, c3, c4 = st.columns([0.7, 1.2, 1, 1.4])

            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"constant_enabled_{i}",
                )

            with c2:
                rule["name"] = st.text_input(
                    "Column name",
                    value=rule.get("name", ""),
                    key=f"constant_name_{i}",
                )

            with c3:
                rule["type"] = st.selectbox(
                    "Type",
                    ["text", "number", "boolean", "date"],
                    index=["text", "number", "boolean", "date"].index(rule.get("type", "text")),
                    key=f"constant_type_{i}",
                )

            with c4:
                rule["value"] = st.text_input(
                    "Value",
                    value=str(rule.get("value", "")),
                    key=f"constant_value_{i}",
                )

            if st.button("Remove constant column", key=f"remove_constant_{i}", use_container_width=True):
                constant_rules.pop(i)
                st.rerun()


def _render_derived_columns_ui(config: dict):
    _render_section_title(
        "Formula / template columns",
        "Create new columns from formulas or text templates using existing row values.",
    )

    derived_rules = config.setdefault("_derived_columns", [])

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Add derived column", use_container_width=True, key="add_derived_col_btn"):
            derived_rules.append({
                "enabled": True,
                "name": "",
                "type": "text",
                "formula": "",
            })
            st.rerun()

    with c2:
        if derived_rules and st.button("Clear derived columns", use_container_width=True, key="clear_derived_cols_btn"):
            config["_derived_columns"] = []
            st.rerun()

    if not derived_rules:
        _render_alert(
            "info",
            "No derived columns yet. Example numeric formula: price * quantity. Example text template: {first_name} {last_name}.",
        )

    for i, rule in enumerate(derived_rules):
        with st.expander(f"Derived column {i + 1}", expanded=True):
            c1, c2, c3 = st.columns([0.7, 1.2, 1])

            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"derived_enabled_{i}",
                )

            with c2:
                rule["name"] = st.text_input(
                    "Column name",
                    value=rule.get("name", ""),
                    key=f"derived_name_{i}",
                )

            with c3:
                rule["type"] = st.selectbox(
                    "Result type",
                    ["text", "number", "boolean", "date"],
                    index=["text", "number", "boolean", "date"].index(rule.get("type", "text")),
                    key=f"derived_type_{i}",
                )

            rule["formula"] = st.text_area(
                "Formula or text template",
                value=rule.get("formula", ""),
                key=f"derived_formula_{i}",
                height=90,
                placeholder="Examples: price * quantity  OR  {first_name} {last_name}",
            )

            if st.button("Remove derived column", key=f"remove_derived_{i}", use_container_width=True):
                derived_rules.pop(i)
                st.rerun()


def _render_conditional_columns_ui(config: dict):
    _render_section_title(
        "Conditional columns",
        "Create a new column using an if/else rule.",
    )

    conditional_rules = config.setdefault("_conditional_rules", [])

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Add conditional column", use_container_width=True, key="add_conditional_col_btn"):
            conditional_rules.append({
                "enabled": True,
                "target_column": "",
                "result_type": "text",
                "condition": "",
                "true_value": "",
                "false_value": "",
            })
            st.rerun()

    with c2:
        if conditional_rules and st.button("Clear conditional columns", use_container_width=True, key="clear_conditional_cols_btn"):
            config["_conditional_rules"] = []
            st.rerun()

    if not conditional_rules:
        _render_alert(
            "info",
            "No conditional columns yet. Example: condition age >= 18, true Adult, false Minor.",
        )

    for i, rule in enumerate(conditional_rules):
        with st.expander(f"Conditional column {i + 1}", expanded=True):
            c1, c2, c3 = st.columns([0.7, 1.2, 1])

            with c1:
                rule["enabled"] = st.checkbox(
                    "Enabled",
                    value=rule.get("enabled", True),
                    key=f"conditional_enabled_{i}",
                )

            with c2:
                rule["target_column"] = st.text_input(
                    "Target column",
                    value=rule.get("target_column", ""),
                    key=f"conditional_target_{i}",
                )

            with c3:
                rule["result_type"] = st.selectbox(
                    "Result type",
                    ["text", "number", "boolean", "date"],
                    index=["text", "number", "boolean", "date"].index(rule.get("result_type", "text")),
                    key=f"conditional_type_{i}",
                )

            rule["condition"] = st.text_area(
                "Condition",
                value=rule.get("condition", ""),
                key=f"conditional_condition_{i}",
                height=80,
                placeholder="Example: age >= 18",
            )

            v1, v2 = st.columns(2)

            with v1:
                rule["true_value"] = st.text_input(
                    "Value if true",
                    value=str(rule.get("true_value", "")),
                    key=f"conditional_true_{i}",
                )

            with v2:
                rule["false_value"] = st.text_input(
                    "Value if false",
                    value=str(rule.get("false_value", "")),
                    key=f"conditional_false_{i}",
                )

            if st.button("Remove conditional column", key=f"remove_conditional_{i}", use_container_width=True):
                conditional_rules.pop(i)
                st.rerun()


def _render_column_configuration(df_uploaded: pd.DataFrame, profiles: dict, config: dict):
    _render_section_title(
        "Column configuration",
        "Review detected types, missing value handling, replacements, transformations, and form behavior.",
    )

    visible_columns = [
        col for col in df_uploaded.columns
        if col not in config.get("_drop_columns", [])
    ]

    if not visible_columns:
        _render_alert(
            "warning",
            "All original columns are currently marked for removal. Keep at least one column before saving.",
        )
        return

    st.markdown(
        f"""
        <div class="clean-note">
            Showing <b>{len(visible_columns)}</b> configurable columns.
        </div>
        """,
        unsafe_allow_html=True,
    )

    for col in visible_columns:
        col_profile = profiles.get(col)

        if col_profile is None:
            col_profile = profile_dataset(df_uploaded[[col]]).get(col, {})

        render_column_editor(col, df_uploaded, col_profile, config)


# ============================================================
# MAIN PAGE
# ============================================================

def render_cleaning_page():
    df_uploaded, profiles, config, uploaded_name, source_label = _resolve_cleaning_context()

    if df_uploaded is None:
        st.warning("No dataset loaded.")

        if st.button("Go back", use_container_width=True):
            st.session_state.page = "Datasets"
            st.rerun()

        return

    _ensure_global_cleaning_config(config)

    _render_cleaning_header(
        dataset_name=uploaded_name,
        source_label=source_label,
        df=df_uploaded,
    )

    tabs = st.tabs([
        "Overview",
        "Dataset rules",
        "Row filters",
        "Columns",
        "New columns",
        "Preview",
        "Save",
    ])

    with tabs[0]:
        _render_section_title(
            "Cleaning overview",
            "Start with global rules, then row filters, then column configuration, then preview and save.",
        )

        _render_alert(
            "info",
            "Recommended workflow: choose the real header row if needed → apply dataset rules → remove unwanted rows → configure columns → create new columns → preview → save.",
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
        subtab_constant, subtab_formula, subtab_conditional = st.tabs([
            "Constant",
            "Formula / template",
            "Conditional",
        ])

        with subtab_constant:
            _render_constant_columns_ui(config)

        with subtab_formula:
            _render_derived_columns_ui(config)

        with subtab_conditional:
            _render_conditional_columns_ui(config)

    with tabs[5]:
        _render_section_title(
            "Preview cleaning result",
            "Generate a temporary preview before saving the cleaned dataset.",
        )

        if st.button(
            "Generate cleaned preview",
            use_container_width=True,
            key="preview_cleaned_btn",
        ):
            try:
                clean_df, form_options = _generate_preview(df_uploaded, config)
                _render_alert("success", "Cleaned dataset preview generated successfully.")
                _render_preview_panel(df_uploaded, clean_df, form_options)
            except Exception as e:
                _render_alert("danger", f"Error while applying configuration: {e}")

        elif st.session_state.get("cleaned_upload_df") is not None:
            clean_df = st.session_state.cleaned_upload_df
            form_options = st.session_state.get("generated_form_schema", {})
            _render_preview_panel(df_uploaded, clean_df, form_options)
        else:
            _render_alert(
                "info",
                "No preview generated yet. Click the button above to see how the cleaned dataset will look.",
            )

    with tabs[6]:
        _render_section_title(
            "Save cleaned dataset",
            "Upload the cleaned dataset and make it the active dataset for editing and analysis.",
        )

        _render_alert(
            "info",
            "Saving will apply the current cleaning configuration, upload the cleaned file, and open it in the editor.",
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
            except Exception as e:
                _render_alert("danger", f"Error while applying configuration: {e}")

        if save_clicked:
            try:
                _save_cleaned_dataset(df_uploaded, config, uploaded_name)
            except Exception as e:
                _render_alert("danger", f"Error while uploading dataset: {e}")