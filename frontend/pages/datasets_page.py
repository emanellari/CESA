import streamlit as st
import pandas as pd
import io
import numpy as np
from api.dataset_api import delete_dataset, upload_dataset
from services.dataset_service import refresh_dataset_list, load_dataset_into_session
from utils.ui_helpers import require_login, show_http_error
from utils.session import go

# ===================== HELPERS =====================

def get_mode_value(series: pd.Series):
    s = series.dropna()
    if s.empty:
        return ""
    mode = s.mode()
    return mode.iloc[0] if not mode.empty else ""

def render_replacements_editor(col_name: str, profile: dict, config: dict):
    st.markdown("### Value replacements")

    if "replacements" not in config[col_name] or not isinstance(config[col_name]["replacements"], list):
        config[col_name]["replacements"] = []

    if "replacements_text" not in config[col_name]:
        config[col_name]["replacements_text"] = ""

    detected_values = profile.get("unique_values", []) or []
    detected_values_str = [str(v) for v in detected_values]

    top_left, top_right = st.columns([3, 1])

    with top_left:
        st.caption("Use the visual mode or write replacements manually.")

    with top_right:
        if st.button("➕ Add rule", key=f"add_replacement_{col_name}", use_container_width=True):
            config[col_name]["replacements"].append({
                "old_values": [],
                "new": ""
            })
            st.rerun()

    # -------- VISUAL MODE --------
    st.markdown("#### Visual mode")

    if not config[col_name]["replacements"]:
        st.info("No visual rules yet.")

    remove_indexes = []

    for idx, item in enumerate(config[col_name]["replacements"]):
        current_old_values = item.get("old_values", [])
        current_old_values = [str(v) for v in current_old_values] if isinstance(current_old_values, list) else []
        current_new = "" if item.get("new") is None else str(item.get("new"))

        already_used = set()
        for j, other in enumerate(config[col_name]["replacements"]):
            if j != idx:
                other_vals = other.get("old_values", [])
                if isinstance(other_vals, list):
                    already_used.update(str(v) for v in other_vals)

        options = [v for v in detected_values_str if v not in already_used]
        for v in current_old_values:
            if v not in options:
                options.append(v)

        with st.container():
            st.markdown("---")
            c1, c2, c3 = st.columns([2.2, 2, 0.8])

            with c1:
                selected_old_values = st.multiselect(
                    "Replace these values",
                    options=options,
                    default=current_old_values,
                    key=f"{col_name}_{idx}_old_values"
                )

            with c2:
                mode = st.radio(
                    "New value",
                    ["Type manually", "Choose existing"],
                    index=0 if current_new not in detected_values_str else 1,
                    key=f"{col_name}_{idx}_mode",
                    horizontal=True
                )

                if mode == "Choose existing":
                    new_options = [""] + detected_values_str
                    typed_new = st.selectbox(
                        "Replace with",
                        new_options,
                        index=new_options.index(current_new) if current_new in new_options else 0,
                        key=f"{col_name}_{idx}_new_select"
                    )
                else:
                    typed_new = st.text_input(
                        "Replace with",
                        value=current_new,
                        key=f"{col_name}_{idx}_new_input"
                    )

            with c3:
                st.write("")
                st.write("")
                if st.button("🗑️", key=f"{col_name}_{idx}_remove", use_container_width=True):
                    remove_indexes.append(idx)

            config[col_name]["replacements"][idx] = {
                "old_values": selected_old_values,
                "new": typed_new
            }

            if selected_old_values and typed_new:
                st.caption(f"{', '.join(selected_old_values)} → {typed_new}")

    if remove_indexes:
        config[col_name]["replacements"] = [
            item for i, item in enumerate(config[col_name]["replacements"])
            if i not in remove_indexes
        ]
        st.rerun()

    # -------- MANUAL MODE --------
    st.markdown("#### Manual mode")
    config[col_name]["replacements_text"] = st.text_area(
        "Write replacements manually (one per line: old=new)",
        value=config[col_name].get("replacements_text", ""),
        key=f"{col_name}_replacements_text",
        height=120,
        placeholder="yes=true\nno=false\nunknown="
    )
def get_mean_value(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 0
    return float(s.mean())

def get_median_value(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 0
    return float(s.median())
def normalize_string_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()
def safe_strip_value(value):
    return value.strip() if isinstance(value, str) else value

def detect_boolean_defaults(unique_values: list) -> tuple[str, str]:
    """
    Detecta automáticamente qué valor representa True y cuál False.
    Devuelve (true_value, false_value).
    """
    if not unique_values or len(unique_values) < 2:
        return "", ""

    normalized_map = {}
    for v in unique_values:
        normalized_map[str(v).strip().lower()] = v

    known_pairs = [
        # English
        ("true", "false"),
        ("yes", "no"),
        ("y", "n"),
        ("1", "0"),
        ("t", "f"),

        # Albanian
        ("po", "jo"),

        # Spanish
        ("si", "no"),
        ("sí", "no"),
        ("verdadero", "falso"),

        # Italian
        ("si", "no"),
        ("vero", "falso"),

        # French
        ("oui", "non"),
        ("vrai", "faux"),

        # German
        ("ja", "nein"),
        ("wahr", "falsch"),

        # Portuguese
        ("sim", "nao"),
        ("não", "sim"),
        ("verdadeiro", "falso"),

        # Turkish
        ("evet", "hayir"),
        ("hayır", "evet"),

        # Dutch
        ("ja", "nee"),
        ("waar", "onwaar"),

        # Swedish
        ("ja", "nej"),
        ("sant", "falskt"),

        # Danish
        ("ja", "nej"),
        ("sand", "falsk"),

        # Norwegian
        ("ja", "nei"),
        ("sann", "usann"),

        # Finnish
        ("kylla", "ei"),
        ("kyllä", "ei"),
        ("tosi", "epatosi"),
        ("tosi", "epätosi"),

        # Polish
        ("tak", "nie"),
        ("prawda", "falsz"),
        ("prawda", "fałsz"),

        # Czech / Slovak
        ("ano", "ne"),
        ("pravda", "nepravda"),

        # Romanian
        ("da", "nu"),
        ("adevarat", "fals"),
        ("adevărat", "fals"),

        # Hungarian
        ("igen", "nem"),
        ("igaz", "hamis"),

        # Russian
        ("da", "net"),
        ("pravda", "lozh"),
        ("правда", "ложь"),
        ("да", "нет"),

        # Greek
        ("nai", "oxi"),
        ("ναι", "όχι"),
        ("alithes", "psema"),
        ("αληθες", "ψευδές"),

        # Arabic
        ("naam", "la"),
        ("نعم", "لا"),
        ("sahih", "khata"),
        ("صحيح", "خطأ"),

        # Hindi
        ("haan", "nahin"),
        ("सही", "गलत"),

        # Chinese
        ("shi", "fou"),
        ("是", "否"),
        ("dui", "cuo"),
        ("对", "错"),

        # Japanese
        ("hai", "iie"),
        ("はい", "いいえ"),
        ("tadashii", "machigai"),
        ("正しい", "間違い"),

        # Korean
        ("ne", "aniyo"),
        ("네", "아니요"),
        ("majda", "teullida"),
        ("맞다", "틀리다"),
    ]

    for true_norm, false_norm in known_pairs:
        if true_norm in normalized_map and false_norm in normalized_map:
            return str(normalized_map[true_norm]), str(normalized_map[false_norm])

    # fallback: conserva orden si no reconoce el par
    return str(unique_values[0]), str(unique_values[1])
def get_preserved_unique_values(series: pd.Series) -> list:
    """
    Devuelve valores únicos preservando tipos originales.
    Solo limpia espacios en strings.
    """
    cleaned = [safe_strip_value(v) for v in series.dropna().tolist()]

    uniques = []
    for v in cleaned:
        if v not in uniques:
            uniques.append(v)

    try:
        return sorted(uniques)
    except Exception:
        return uniques


def infer_column_type(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "text"

    s_str = s.astype(str).str.strip().str.lower()
    s_str = s_str[s_str != ""]

    if s_str.empty:
        return "text"

    boolean_pairs = [
        # English
        ("true", "false"),
        ("yes", "no"),
        ("y", "n"),
        ("1", "0"),
        ("t", "f"),

        # Albanian
        ("po", "jo"),

        # Spanish
        ("si", "no"),
        ("sí", "no"),
        ("verdadero", "falso"),

        # Italian
        ("si", "no"),
        ("vero", "falso"),

        # French
        ("oui", "non"),
        ("vrai", "faux"),

        # German
        ("ja", "nein"),
        ("wahr", "falsch"),

        # Portuguese
        ("sim", "nao"),
        ("não", "sim"),
        ("verdadeiro", "falso"),

        # Turkish
        ("evet", "hayir"),
        ("hayır", "evet"),

        # Dutch
        ("ja", "nee"),
        ("waar", "onwaar"),

        # Swedish
        ("ja", "nej"),
        ("sant", "falskt"),

        # Danish
        ("ja", "nej"),
        ("sand", "falsk"),

        # Norwegian
        ("ja", "nei"),
        ("sann", "usann"),

        # Finnish
        ("kylla", "ei"),
        ("kyllä", "ei"),
        ("tosi", "epatosi"),
        ("tosi", "epätosi"),

        # Polish
        ("tak", "nie"),
        ("prawda", "falsz"),
        ("prawda", "fałsz"),

        # Czech / Slovak
        ("ano", "ne"),
        ("pravda", "nepravda"),

        # Romanian
        ("da", "nu"),
        ("adevarat", "fals"),
        ("adevărat", "fals"),

        # Hungarian
        ("igen", "nem"),
        ("igaz", "hamis"),

        # Russian
        ("da", "net"),
        ("pravda", "lozh"),
        ("правда", "ложь"),
        ("да", "нет"),

        # Greek
        ("nai", "oxi"),
        ("ναι", "όχι"),
        ("alithes", "psema"),
        ("αληθες", "ψευδές"),

        # Arabic
        ("naam", "la"),
        ("نعم", "لا"),
        ("sahih", "khata"),
        ("صحيح", "خطأ"),

        # Hindi
        ("haan", "nahin"),
        ("सही", "गलत"),

        # Chinese
        ("shi", "fou"),
        ("是", "否"),
        ("dui", "cuo"),
        ("对", "错"),

        # Japanese
        ("hai", "iie"),
        ("はい", "いいえ"),
        ("tadashii", "machigai"),
        ("正しい", "間違い"),

        # Korean
        ("ne", "aniyo"),
        ("네", "아니요"),
        ("majda", "teullida"),
        ("맞다", "틀리다"),
    ]

    unique_vals = set(s_str.unique())

    # Boolean confirmado
    if len(unique_vals) in (1, 2):
        for pair in boolean_pairs:
            if unique_vals.issubset(pair):
                return "boolean"

    # Boolean candidato: 80% dentro de un mismo par
    for pair in boolean_pairs:
        pair_ratio = s_str.isin(pair).mean()
        if pair_ratio >= 0.80:
            return "boolean_candidate"

    numeric_conv = pd.to_numeric(s_str, errors="coerce")
    if numeric_conv.notna().mean() >= 0.9:
        return "number"

    date_conv = pd.to_datetime(s_str, errors="coerce")
    if date_conv.notna().mean() >= 0.9:
        return "date_candidate"

    unique_count = s.nunique(dropna=True)
    unique_ratio = unique_count / len(s) if len(s) else 1

    if unique_ratio < 0.50:
        return "categorical"

    return "text"

def get_column_profile(series: pd.Series) -> dict:
    s_non_null = series.dropna()
    inferred = infer_column_type(series)
    unique_count = s_non_null.nunique(dropna=True)
    non_null_count = len(s_non_null)
    unique_ratio = unique_count / non_null_count if non_null_count else 0

    unique_values = []
    max_preview_uniques = 300

    try:
        cleaned_unique_values = [
            v.strip() if isinstance(v, str) else v
            for v in s_non_null.unique().tolist()
        ]

        if inferred in ["categorical", "boolean_candidate"]:
            unique_values = cleaned_unique_values[:max_preview_uniques]

        elif inferred == "text":
            # también mostrar opciones reemplazables para texto,
            # pero solo si no son demasiadas
            if unique_count <= max_preview_uniques:
                unique_values = cleaned_unique_values[:max_preview_uniques]
            else:
                unique_values = cleaned_unique_values[:max_preview_uniques]

        try:
            unique_values = sorted(unique_values)
        except Exception:
            pass

    except Exception:
        unique_values = []

    return {
        "inferred_type": inferred,
        "null_count": int(series.isna().sum()),
        "non_null_count": int(non_null_count),
        "unique_count": int(unique_count),
        "unique_ratio": float(unique_ratio),
        "unique_values": unique_values,
        "sample_values": [
            v.strip() if isinstance(v, str) else v
            for v in series.dropna().head(5).tolist()
        ],
    }
def profile_dataset(df: pd.DataFrame) -> dict:
    return {col: get_column_profile(df[col]) for col in df.columns}

def build_default_config(df: pd.DataFrame, profiles: dict) -> dict:
    config = {}

    for col in df.columns:
        p = profiles[col]
        inferred = p["inferred_type"]
        unique_values = p.get("unique_values", [])

        # defaults
        final_type = "text"
        form_type = "text"

        if inferred == "boolean_candidate":
            # ahora NO lo ponemos como boolean por defecto
            final_type = "categorical"
            form_type = "radio"

        if inferred == "boolean":
            # ahora NO lo ponemos como boolean por defecto
            final_type = "boolean"
            form_type = "checkbox"

        elif inferred == "date_candidate":
            final_type = "date"
            form_type = "date"

        elif inferred == "number":
            final_type = "number"
            form_type = "number"

        elif inferred == "categorical" and len(unique_values)>4:
            final_type = "categorical"
            form_type = "select"

        elif inferred == "categorical" and len(unique_values)<=4:
            final_type = "categorical"
            form_type = "radio"

        else:
            final_type = "text"
            form_type = "text"

        true_default, false_default = detect_boolean_defaults(unique_values)

        config[col] = {
            "final_type": final_type,
            "form_type": form_type,
            "use_auto_choices": True,
            "null_strategy": "keep",
            "null_fill_value": "",
            "replacements": [],
            "replacements_text": "",
            "convert_to_date": inferred == "date_candidate",
            "convert_to_boolean": False,  # ya no forzado por defecto
            "true_value": true_default,
            "false_value": false_default,
            "other_values_strategy": "null",
            "manual_choices_text": "\n".join(str(v) for v in unique_values) if unique_values else "",
            "force_checkbox": False,
        }

    return config
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


def _safe_eval_expression(expr: str, row: dict):
    safe_locals = {}
    for k, v in row.items():
        if pd.isna(v):
            safe_locals[k] = ""
        else:
            safe_locals[k] = v
    return eval(expr, {"__builtins__": {}}, safe_locals)

import re
def _render_text_template(template: str, row: dict) -> str:
    def replacer(match):
        expr = match.group(1).strip()
        try:
            value = _safe_eval_expression(expr, row)
            return "" if pd.isna(value) else str(value)
        except Exception as e:
            return f"[ERROR: {e}]"

    return re.sub(r"\{(.*?)\}", replacer, template)

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

        rendered = re.sub(r"\{(.*?)\}", replacer, expr)

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

        rendered = re.sub(r"\{(.*?)\}", replacer, expr)

        try:
            return bool(eval(rendered, {"__builtins__": {}}, {}))
        except Exception:
            return np.nan

    df.loc[mask, column_name] = df.loc[mask].apply(compute, axis=1)
    return df


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

def generate_form_options_from_config(df: pd.DataFrame, config: dict) -> dict:
    options = {}

    for col, cfg in config.items():
        final_type = cfg.get("final_type")

        if final_type == "number":
            options[col] = {"type": "number", "options": []}

        elif final_type == "date":
            options[col] = {"type": "date", "options": []}

        elif final_type == "boolean":
            options[col] = {"type": "checkbox", "options": []}

        elif final_type == "categorical":
            if cfg.get("use_auto_choices", True):
                vals = get_preserved_unique_values(df[col])
            else:
                vals = [
                    x.strip()
                    for x in cfg.get("manual_choices_text", "").splitlines()
                    if x.strip()
                ]

            form_type = cfg.get("form_type", "select")
            if form_type not in ["select", "radio"]:
                form_type = "select"

            options[col] = {"type": form_type, "options": vals}

        else:
            options[col] = {"type": "text", "options": []}

    return options

def render_column_editor(col_name: str, profile: dict, config: dict):
    inferred = profile["inferred_type"]
    current_type = config[col_name]["final_type"]

    if current_type == "date_candidate":
        current_type = "date"
    if current_type == "boolean_candidate":
        current_type = "boolean"

    emoji_map = {
        "text": "🆃",
        "number": "⓵",
        "categorical": "☰️",
        "boolean": "✔",
        "date": "🗓",
        "boolean_candidate": "✔",
        "date_candidate": "🗓",
    }

    pretty_type_map = {
        "text": "Text",
        "number": "Number",
        "categorical": "Category",
        "boolean": "Boolean",
        "date": "Date",
        "boolean_candidate": "Looks like boolean",
        "date_candidate": "Looks like date",
    }

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(145deg, #2563eb, #0f172a);
                border:1px solid #f3d9e8;
                border-radius:16px;
                padding:16px;
                margin-bottom:14px;
            ">
                <div style="font-size:1.05rem; font-weight:700; color:#7a284b;">
                    {emoji_map.get(inferred, "✨")} {col_name}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        c1, c2 = st.columns([1.2, 1])

        with c1:
            st.caption(f"Detected type: {pretty_type_map.get(inferred, inferred)}")
            st.caption(f"Null values: {profile['null_count']}")
            st.caption(f"Unique values: {profile['unique_count']}")

            if profile["sample_values"]:
                st.write("Examples:")
                st.code(", ".join(str(x) for x in profile["sample_values"][:5]))

        with c2:
            type_options = ["text", "number", "categorical", "boolean", "date"]
            selected_type = st.selectbox(
                f"Choose type for {col_name}",
                type_options,
                index=type_options.index(current_type),
                key=f"type_{col_name}",
                label_visibility="visible"
            )
            config[col_name]["final_type"] = selected_type

        if profile["unique_values"]:
            st.write("Detected values:")
            st.code(", ".join(str(x) for x in profile["unique_values"]))

        all_other_cols = [c for c in config.keys() if c != col_name]
        numeric_other_cols = [
            c for c in config.keys()
            if c != col_name and config[c].get("final_type") == "number"
        ]

        # -------- NULL HANDLING FRIENDLY --------
        if selected_type == "categorical":
            null_label_to_value = {
                "Keep empty values": "keep",
                "Fill with most common value": "fill_mode",
                "Fill with my own value": "fill",
                "Fill using other columns + text": "fill_formula_text",
                "Delete rows with empty values": "drop",
            }

            current_null_strategy = config[col_name].get("null_strategy", "keep")
            reverse_null_map = {v: k for k, v in null_label_to_value.items()}
            current_null_label = reverse_null_map.get(current_null_strategy, "Keep empty values")

            if profile["null_count"] != 0:
                chosen_null_label = st.radio(
                    f"What should happen with empty values in {col_name}?",
                    list(null_label_to_value.keys()),
                    key=f"null_radio_{col_name}",
                    index=list(null_label_to_value.keys()).index(current_null_label)
                )
                config[col_name]["null_strategy"] = null_label_to_value[chosen_null_label]

            config[col_name]["use_auto_choices"] = st.checkbox(
                f"Use detected choices automatically for {col_name}",
                value=config[col_name].get("use_auto_choices", True),
                key=f"auto_choices_{col_name}"
            )

            form_ui = st.radio(
                f"How should this appear in the form?",
                ["Dropdown", "Radio buttons"],
                key=f"form_ui_{col_name}",
                index=0 if config[col_name].get("form_type", "select") == "select" else 1,
                horizontal=True
            )
            config[col_name]["form_type"] = "select" if form_ui == "Dropdown" else "radio"

            if config[col_name]["null_strategy"] == "fill":
                config[col_name]["null_fill_value"] = st.text_input(
                    f"Value to use for empty cells in {col_name}",
                    value=config[col_name].get("null_fill_value", ""),
                    key=f"fill_{col_name}"
                )

            elif config[col_name]["null_strategy"] == "fill_formula_text":
                st.markdown("#### Build value from other columns")
                config[col_name]["null_formula_cols"] = st.multiselect(
                    f"Columns to use for {col_name}",
                    all_other_cols,
                    default=config[col_name].get("null_formula_cols", []),
                    key=f"formula_cols_{col_name}"
                )
                config[col_name]["null_formula_text"] = st.text_input(
                    f"Template for empty cells in {col_name}",
                    value=config[col_name].get("null_formula_text", ""),
                    key=f"formula_text_{col_name}",
                    placeholder='{full_name.lower().replace(" ","")}@aol.com'
                )
                st.caption('Use expressions inside braces, for example: {full_name.lower().replace(" ","")}@aol.com')

            if not config[col_name]["use_auto_choices"]:
                config[col_name]["manual_choices_text"] = st.text_area(
                    f"Write your own choices for {col_name} (one per line)",
                    value=config[col_name].get("manual_choices_text", ""),
                    key=f"manual_choices_{col_name}",
                    height=100
                )

        elif selected_type == "number":
            null_label_to_value = {
                "Keep empty values": "keep",
                "Fill with mean": "fill_mean",
                "Fill with median": "fill_median",
                "Fill with my own value": "fill",
                "Fill using numeric formula": "fill_formula_numeric",
                "Delete rows with empty values": "drop",
            }

            current_null_strategy = config[col_name].get("null_strategy", "keep")
            reverse_null_map = {v: k for k, v in null_label_to_value.items()}
            current_null_label = reverse_null_map.get(current_null_strategy, "Keep empty values")

            if profile["null_count"] != 0:
                chosen_null_label = st.radio(
                    f"What should happen with empty values in {col_name}?",
                    list(null_label_to_value.keys()),
                    key=f"null_radio_{col_name}",
                    index=list(null_label_to_value.keys()).index(current_null_label)
                )
                config[col_name]["null_strategy"] = null_label_to_value[chosen_null_label]

            config[col_name]["form_type"] = "number"

            if config[col_name]["null_strategy"] == "fill":
                config[col_name]["null_fill_value"] = st.number_input(
                    f"Value to use for empty cells in {col_name}",
                    value=float(config[col_name].get("null_fill_value", 0) or 0),
                    key=f"fill_{col_name}"
                )

            elif config[col_name]["null_strategy"] == "fill_formula_numeric":
                st.markdown("#### Build value from numeric columns")
                config[col_name]["null_formula_cols"] = st.multiselect(
                    f"Numeric columns to use for {col_name}",
                    numeric_other_cols,
                    default=config[col_name].get("null_formula_cols", []),
                    key=f"formula_cols_{col_name}"
                )
                config[col_name]["null_formula_numeric"] = st.text_input(
                    f"Formula for empty cells in {col_name}",
                    value=config[col_name].get("null_formula_numeric", ""),
                    key=f"formula_numeric_{col_name}",
                    placeholder="({salary} + {bonus}) / 2"
                )
                st.caption("Use expressions with numeric columns inside braces, operators, and parentheses.")

        elif selected_type == "boolean":
            config[col_name]["form_type"] = "checkbox"

            null_label_to_value = {
                "Keep empty values": "keep",
                "Fill with TRUE": "fill_true",
                "Fill with FALSE": "fill_false",
                "Fill using logical rule": "fill_formula_boolean",
                "Delete rows with empty values": "drop",
            }

            current_null_strategy = config[col_name].get("null_strategy", "keep")
            reverse_null_map = {v: k for k, v in null_label_to_value.items()}
            current_null_label = reverse_null_map.get(current_null_strategy, "Keep empty values")

            if profile["null_count"] != 0:
                chosen_null_label = st.radio(
                    f"What should happen with empty values in {col_name}?",
                    list(null_label_to_value.keys()),
                    key=f"null_radio_{col_name}",
                    index=list(null_label_to_value.keys()).index(current_null_label)
                )
                config[col_name]["null_strategy"] = null_label_to_value[chosen_null_label]

            current_uniques = profile.get("unique_values", [])
            if current_uniques:
                suggested_true, suggested_false = detect_boolean_defaults(current_uniques)

                if not config[col_name].get("true_value"):
                    config[col_name]["true_value"] = suggested_true
                if not config[col_name].get("false_value"):
                    config[col_name]["false_value"] = suggested_false

                st.info(
                    f"I found these values and I suggest:\n\n"
                    f"- TRUE → {config[col_name]['true_value']}\n"
                    f"- FALSE → {config[col_name]['false_value']}"
                )

            config[col_name]["true_value"] = st.text_input(
                f"Which value means TRUE in {col_name}?",
                value=config[col_name].get("true_value", ""),
                key=f"true_{col_name}"
            )

            config[col_name]["false_value"] = st.text_input(
                f"Which value means FALSE in {col_name}?",
                value=config[col_name].get("false_value", ""),
                key=f"false_{col_name}"
            )

            if config[col_name]["null_strategy"] == "fill_formula_boolean":
                st.markdown("#### Build boolean from other columns")
                config[col_name]["null_formula_cols"] = st.multiselect(
                    f"Columns to use for rule in {col_name}",
                    all_other_cols,
                    default=config[col_name].get("null_formula_cols", []),
                    key=f"formula_cols_{col_name}"
                )
                config[col_name]["null_formula_boolean"] = st.text_input(
                    f"Logical rule for empty cells in {col_name}",
                    value=config[col_name].get("null_formula_boolean", ""),
                    key=f"formula_boolean_{col_name}",
                    placeholder="{age} >= 18 and {active} == True"
                )
                st.caption("Use boolean expressions with other columns inside braces.")

            config[col_name]["other_values_strategy"] = st.radio(
                f"If other values appear in {col_name}:",
                ["Turn into empty", "Turn into TRUE", "Turn into FALSE", "Delete those rows"],
                key=f"other_vals_ui_{col_name}",
                index={
                    "null": 0,
                    "true": 1,
                    "false": 2,
                    "drop": 3
                }.get(config[col_name].get("other_values_strategy", "null"), 0)
            )

            ui_to_internal = {
                "Turn into empty": "null",
                "Turn into TRUE": "true",
                "Turn into FALSE": "false",
                "Delete those rows": "drop",
            }
            config[col_name]["other_values_strategy"] = ui_to_internal[
                st.session_state[f"other_vals_ui_{col_name}"]
            ]

        elif selected_type == "date":
            config[col_name]["form_type"] = "date"

            null_label_to_value = {
                "Keep empty values": "keep",
                "Fill with my own value": "fill",
                "Delete rows with empty values": "drop",
            }

            current_null_strategy = config[col_name].get("null_strategy", "keep")
            reverse_null_map = {v: k for k, v in null_label_to_value.items()}
            current_null_label = reverse_null_map.get(current_null_strategy, "Keep empty values")

            if profile["null_count"] != 0:
                chosen_null_label = st.radio(
                    f"What should happen with empty values in {col_name}?",
                    list(null_label_to_value.keys()),
                    key=f"null_radio_{col_name}",
                    index=list(null_label_to_value.keys()).index(current_null_label)
                )
                config[col_name]["null_strategy"] = null_label_to_value[chosen_null_label]

            if config[col_name]["null_strategy"] == "fill":
                config[col_name]["null_fill_value"] = st.text_input(
                    f"Date to use for empty cells in {col_name}",
                    value=config[col_name].get("null_fill_value", ""),
                    key=f"fill_{col_name}",
                    placeholder="2026-04-08"
                )

        else:
            config[col_name]["form_type"] = "text"

            null_label_to_value = {
                "Keep empty values": "keep",
                "Fill with my own value": "fill",
                "Fill using other columns + text": "fill_formula_text",
                "Delete rows with empty values": "drop",
            }

            current_null_strategy = config[col_name].get("null_strategy", "keep")
            reverse_null_map = {v: k for k, v in null_label_to_value.items()}
            current_null_label = reverse_null_map.get(current_null_strategy, "Keep empty values")

            if profile["null_count"] != 0:
                chosen_null_label = st.radio(
                    f"What should happen with empty values in {col_name}?",
                    list(null_label_to_value.keys()),
                    key=f"null_radio_{col_name}",
                    index=list(null_label_to_value.keys()).index(current_null_label)
                )
                config[col_name]["null_strategy"] = null_label_to_value[chosen_null_label]

            if config[col_name]["null_strategy"] == "fill":
                config[col_name]["null_fill_value"] = st.text_input(
                    f"Value to use for empty cells in {col_name}",
                    value=config[col_name].get("null_fill_value", ""),
                    key=f"fill_{col_name}"
                )

            elif config[col_name]["null_strategy"] == "fill_formula_text":
                st.markdown("#### Build value from other columns")
                config[col_name]["null_formula_cols"] = st.multiselect(
                    f"Columns to use for {col_name}",
                    all_other_cols,
                    default=config[col_name].get("null_formula_cols", []),
                    key=f"formula_cols_{col_name}"
                )
                config[col_name]["null_formula_text"] = st.text_input(
                    f"Template for empty cells in {col_name}",
                    value=config[col_name].get("null_formula_text", ""),
                    key=f"formula_text_{col_name}",
                    placeholder='{full_name.lower().replace(" ","")}@aol.com'
                )
                st.caption('Use expressions inside braces, for example: {full_name.lower().replace(" ","")}@aol.com')

        with st.expander(f"Advanced options for {col_name}"):
            render_replacements_editor(col_name, profile, config)
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

# ===================== MAIN PAGE =====================
def read_uploaded_dataset(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return pd.read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if filename.endswith(".tsv"):
        return pd.read_csv(uploaded_file, sep="\t")

    raise ValueError("Unsupported file format")
def render_datasets_page():
    require_login()

    st.markdown("""
        <div class="page-hero">
            <div class="page-hero-title">Datasets</div>
            <div class="page-hero-subtitle">
                Manage existing datasets, upload raw files, clean them automatically,
                and transform them into structured analysis workflows.
            </div>
        </div>
    """, unsafe_allow_html=True)

    top_left, top_right = st.columns([4, 1])

    with top_right:
        if st.button("Refresh", use_container_width=True):
            refresh_dataset_list()

    if not st.session_state.get("datasets"):
        refresh_dataset_list()

    datasets = st.session_state.get("datasets", [])

    st.markdown("""
        <div class="soft-info-card">
            <strong>Workspace capabilities</strong><br>
            Upload raw datasets, standardize them, generate form-ready structures,
            and continue directly into editing and analysis.
        </div>
    """, unsafe_allow_html=True)

    st.markdown("## Existing datasets")
    st.caption("Open a saved dataset to continue working on it.")

    if datasets:
        dataset_options = {
            f"{d['name']} (ID: {d['dataset_id']})": d["dataset_id"]
            for d in datasets
        }

        selected_label = st.selectbox(
            "Select a dataset",
            list(dataset_options.keys()),
            key="dataset_selector"
        )
        selected_id = dataset_options[selected_label]

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Open workspace", use_container_width=True, key="open_dataset_btn"):
                with st.spinner("Loading dataset..."):
                    response = load_dataset_into_session(selected_id)

                if response.ok:
                    st.session_state.page ="Editor + Analysis"
                    st.rerun()
                else:
                    show_http_error(response)

        with c2:
            if st.button("Delete dataset", use_container_width=True, key="delete_dataset_btn"):
                with st.spinner("Deleting dataset..."):
                    response = delete_dataset(selected_id)

                if response.ok:
                    st.success("Dataset deleted successfully.")
                    refresh_dataset_list()
                    st.rerun()
                else:
                    show_http_error(response)



    else:
        st.markdown("""
            <div class="empty-state-card">
                <div class="empty-state-title">No datasets available yet</div>
                <div class="empty-state-text">
                    Upload a raw file or create a dataset from scratch to get started.
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.markdown("## Create or upload a new dataset")
    st.caption("Start from scratch or upload a file and prepare it automatically for analysis.")

    c1, c2 = st.columns([1.2, 2])

    with c1:
        if st.button("Create dataset from scratch", use_container_width=True, key="create_bottom_btn"):
            st.session_state.page = PAGE_CREATE_DATASET
            st.rerun()

    with c2:
        st.markdown("""
            <div class="upload-hint-card">
                Uploaded datasets can be reviewed, cleaned, standardized, and converted
                into form-ready structures before being saved.
            </div>
        """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload a dataset file",
        type=["xlsx", "xls", "csv", "tsv"],
        key="dataset_uploader",
        help="Supported formats: XLSX, XLS, CSV, TSV"
    )

    if uploaded is not None:
        try:
            df_uploaded = read_uploaded_dataset(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return

        df_uploaded = handle_duplicate_columns(df_uploaded)

        st.success("File loaded successfully. Review and configure it before uploading.")
        st.dataframe(df_uploaded.head(20), use_container_width=True)

        st.session_state.upload_preview_df = df_uploaded.copy()

        if (
            "upload_profiles" not in st.session_state
            or st.session_state.get("last_uploaded_name") != uploaded.name
        ):
            profiles = profile_dataset(df_uploaded)
            st.session_state.upload_profiles = profiles
            st.session_state.upload_config = build_default_config(df_uploaded, profiles)
            st.session_state.last_uploaded_name = uploaded.name

        profiles = st.session_state.upload_profiles
        config = st.session_state.upload_config

        st.markdown("## Column configuration")
        st.caption("Review detected types, missing value handling, replacements, and form behavior.")

        for col in df_uploaded.columns:
            render_column_editor(col, profiles[col], config)

        preview_col, upload_col = st.columns(2)

        with preview_col:
            if st.button("Preview cleaned dataset", use_container_width=True, key="preview_cleaned_btn"):
                try:
                    clean_df = apply_user_config(df_uploaded, config)
                    st.session_state.cleaned_upload_df = clean_df
                    st.success("Cleaned dataset preview generated successfully.")
                    st.dataframe(clean_df.head(20), use_container_width=True)

                    form_options = generate_form_options_from_config(clean_df, config)
                    st.markdown("### Generated form schema preview")
                    st.json(form_options)

                except Exception as e:
                    st.error(f"Error while applying configuration: {e}")

        with upload_col:
            if st.button("Upload cleaned dataset", use_container_width=True, key="upload_cleaned_btn"):
                try:
                    clean_df = apply_user_config(df_uploaded, config)
                    form_options = generate_form_options_from_config(clean_df, config)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        clean_df.to_excel(writer, index=False, sheet_name="Sheet1")
                    output.seek(0)
                    output.name = uploaded.name

                    with st.spinner("Uploading cleaned dataset..."):
                        response = upload_dataset(
                            output,
                            options=form_options,
                            columns=clean_df.columns.tolist()
                        )

                    if response.ok:
                        payload = response.json()

                        st.session_state.dataset_id = payload.get("dataset_id")
                        st.session_state.dataset_name = payload.get("dataset_name", uploaded.name)
                        st.session_state.df = clean_df.copy()

                        meta = payload.get("meta", {})
                        meta["options"] = form_options
                        meta["columns"] = clean_df.columns.tolist()

                        st.session_state.dataset_meta = meta
                        st.session_state.generated_form_schema = form_options

                        st.success("Dataset uploaded successfully.")
                        st.session_state.page = "Editor + Analysis"
                        st.rerun()

                    else:
                        show_http_error(response)

                except Exception as e:
                    st.error(f"Error while uploading dataset: {e}")