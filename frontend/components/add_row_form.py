import pandas as pd
import streamlit as st
from datetime import date
from api.dataset_api import update_dataset
from utils.ui_helpers import show_http_error


def render_add_row_form():
    current_df = st.session_state.df
    meta = st.session_state.get("dataset_meta", {}) or {}
    options_map = meta.get("options", {}) or {}

    # ---------- NORMALIZE META ----------
    def normalize_field_meta(field_meta):
        if isinstance(field_meta, list) and field_meta:
            field_meta = field_meta[0]
        elif isinstance(field_meta, list):
            field_meta = {"type": "text", "options": []}
        elif not isinstance(field_meta, dict):
            field_meta = {"type": "text", "options": []}

        return {
            "type": field_meta.get("type", "text"),
            "options": field_meta.get("options", []),
        }

    # ---------- DEFAULT VALUES ----------
    def default_value_for_type(field_type, field_options):
        if field_type == "number":
            return 0.0
        if field_type == "checkbox":
            return False
        if field_type == "radio":
            return field_options[0] if field_options else "Option 1"
        if field_type == "select":
            return ""
        if field_type == "date":
            return date.today()
        return ""

    # ---------- INIT ----------
    def init_form_values():
        for c in current_df.columns:
            field_meta = normalize_field_meta(
                options_map.get(str(c).strip(), {"type": "text", "options": []})
            )
            key = f"add__{c}"

            if key not in st.session_state:
                st.session_state[key] = default_value_for_type(
                    field_meta["type"], field_meta["options"]
                )

    # ---------- RESET SAFE ----------
    def reset_form_values():
        for c in current_df.columns:
            field_meta = normalize_field_meta(
                options_map.get(str(c).strip(), {"type": "text", "options": []})
            )
            st.session_state[f"add__{c}"] = default_value_for_type(
                field_meta["type"], field_meta["options"]
            )

    if st.session_state.get("reset_add_row_form", False):
        reset_form_values()
        st.session_state.reset_add_row_form = False

    init_form_values()

    # ---------- ADD ROW ----------
    def add_row_now():
        new_row = {}

        for c in current_df.columns:
            field_meta = normalize_field_meta(
                options_map.get(str(c).strip(), {"type": "text", "options": []})
            )
            value = st.session_state.get(f"add__{c}", "")

            if field_meta["type"] == "date" and value not in ("", None):
                value = str(value)

            new_row[c] = value

        st.session_state.df = pd.concat(
            [st.session_state.df, pd.DataFrame([new_row])],
            ignore_index=True
        )

        rows = st.session_state.df.fillna("").to_dict(orient="records")
        response = update_dataset(st.session_state.dataset_id, rows)

        if not response.ok:
            show_http_error(response)
            return

        st.session_state.add_row_success = "Row added successfully."
        st.session_state.reset_add_row_form = True
        st.rerun()

    # ---------- GROUP BY TYPE ----------
    def split_columns_by_type(columns, options_map):
        groups = {
            "Text fields": [],
            "Numeric fields": [],
            "Select fields": [],
            "Radio options": [],
            "Checkbox fields": [],
            "Date fields": [],
        }

        for c in columns:
            meta = options_map.get(str(c).strip(), {"type": "text", "options": []})

            if isinstance(meta, list) and meta:
                meta = meta[0]

            field_type = meta.get("type", "text")

            if field_type == "number":
                groups["Numeric fields"].append(c)
            elif field_type == "select":
                groups["Select fields"].append(c)
            elif field_type == "radio":
                groups["Radio options"].append(c)
            elif field_type == "checkbox":
                groups["Checkbox fields"].append(c)
            elif field_type == "date":
                groups["Date fields"].append(c)
            else:
                groups["Text fields"].append(c)

        return {k: v for k, v in groups.items() if v}

    # ---------- UI ----------
    st.markdown("### Add New Record")
    st.caption("Fill the form below to insert a new row into the dataset.")

    if st.session_state.get("add_row_success"):
        st.success(st.session_state["add_row_success"])
        del st.session_state["add_row_success"]

    cols = list(current_df.columns)
    groups = split_columns_by_type(cols,options_map)

    with st.form("add_row_form", clear_on_submit=False):

        groups = split_columns_by_type(cols, options_map)

        for section, section_cols in groups.items():

            with st.expander(section, expanded=True):

                # 🧠 UX hints (lo que pediste)
                if section == "Radio options":
                    st.caption("Use keyboard arrows ← → to select options")

                if section == "Checkbox fields":
                    st.caption("Press SPACE to toggle selection")

                col1, col2 = st.columns(2, gap="large")

                for i, c in enumerate(section_cols):
                    target = col1 if i % 2 == 0 else col2

                    with target:
                        field_meta = normalize_field_meta(
                            options_map.get(str(c).strip(), {"type": "text", "options": []})
                        )

                        field_type = field_meta["type"]
                        field_options = field_meta["options"]
                        label = str(c).replace("_", " ").strip().title()

                        if field_type == "text":
                            st.text_input(label, key=f"add__{c}")

                        elif field_type == "number":
                            st.number_input(label, key=f"add__{c}", width="stretch")

                        elif field_type == "date":
                            st.date_input(label, key=f"add__{c}", width="stretch")

                        elif field_type == "radio":
                            st.radio(
                                label,
                                field_options if field_options else ["Option 1", "Option 2"],
                                key=f"add__{c}",
                                horizontal=True
                            )

                        elif field_type == "checkbox":
                            st.checkbox(label, key=f"add__{c}")

                        elif field_type == "select":
                            st.selectbox(
                                label,
                                [""] + field_options,
                                key=f"add__{c}",
                                width="stretch"
                            )

        # ---------- ACTIONS ----------
        a, b = st.columns([2, 1])

        submitted = a.form_submit_button("Add Row", width="stretch")
        reset_clicked = b.form_submit_button("Reset Form", width="stretch")

        if submitted:
            add_row_now()

        if reset_clicked:
            st.session_state.reset_add_row_form = True
            st.rerun()