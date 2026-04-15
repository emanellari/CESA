import streamlit as st
import pandas as pd

from components.cleaning.replacement_editor import render_replacements_editor
from services.cleaning.profiles import detect_boolean_defaults
from services.cleaning.transforms import get_numeric_outlier_info


def render_column_editor(col_name: str, df: pd.DataFrame, profile: dict, config: dict):
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

            outlier_info = get_numeric_outlier_info(df[col_name])

            if outlier_info["count"] > 0:
                st.warning(
                    f"Detected {outlier_info['count']} potential outliers "
                    f"(outside {outlier_info['lower_bound']:.2f} to {outlier_info['upper_bound']:.2f})."
                )

                if outlier_info["examples"]:
                    st.caption("Examples of extreme values:")
                    st.code(", ".join(str(x) for x in outlier_info["examples"]))

                st.markdown("#### Outlier handling")

                outlier_ui_to_value = {
                    "Do nothing": "none",
                    "Cap using IQR": "cap_iqr",
                    "Remove rows using IQR": "drop_iqr",
                    "Cap using Z-score": "cap_zscore",
                    "Remove rows using Z-score": "drop_zscore",
                }

                current_outlier_strategy = config[col_name].get("outlier_strategy", "none")
                reverse_outlier_map = {v: k for k, v in outlier_ui_to_value.items()}
                current_outlier_label = reverse_outlier_map.get(current_outlier_strategy, "Do nothing")

                chosen_outlier_label = st.radio(
                    f"What should happen with outliers in {col_name}?",
                    list(outlier_ui_to_value.keys()),
                    key=f"outlier_radio_{col_name}",
                    index=list(outlier_ui_to_value.keys()).index(current_outlier_label)
                )
                config[col_name]["outlier_strategy"] = outlier_ui_to_value[chosen_outlier_label]

                if config[col_name]["outlier_strategy"] in ["cap_iqr", "drop_iqr"]:
                    config[col_name]["outlier_iqr_multiplier"] = st.number_input(
                        f"IQR multiplier for {col_name}",
                        min_value=0.5,
                        value=float(config[col_name].get("outlier_iqr_multiplier", 1.5)),
                        step=0.5,
                        key=f"outlier_iqr_multiplier_{col_name}"
                    )

                elif config[col_name]["outlier_strategy"] in ["cap_zscore", "drop_zscore"]:
                    config[col_name]["outlier_zscore_threshold"] = st.number_input(
                        f"Z-score threshold for {col_name}",
                        min_value=1.0,
                        value=float(config[col_name].get("outlier_zscore_threshold", 3.0)),
                        step=0.5,
                        key=f"outlier_zscore_threshold_{col_name}"
                    )
            else:
                st.success("No obvious outliers detected with the current IQR rule.")
                config[col_name]["outlier_strategy"] = "none"

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