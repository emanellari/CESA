import pandas as pd
import streamlit as st
from datetime import date
from api.dataset_api import update_dataset
from utils.ui_helpers import show_http_error


def render_add_row_form():
    current_df = st.session_state.df
    meta = st.session_state.get("dataset_meta", {}) or {}
    options_map = meta.get("options", {}) or {}

    st.markdown("### Add New Rows")
    if "add_row_expanded" not in st.session_state:
        st.session_state.add_row_expanded = False

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

    def default_value_for_type(field_type, field_options):
        if field_type == "number":
            return 0.0
        elif field_type == "checkbox":
            return False
        elif field_type == "radio":
            return field_options[0] if field_options else "Option 1"
        elif field_type == "select":
            return ""
        elif field_type == "date":
            return date.today()
        else:
            return ""

    def coerce_value(field_type, value, field_options):
        if field_type == "checkbox":
            return bool(value) if isinstance(value, bool) else False

        if field_type == "number":
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        if field_type == "date":
            return value if isinstance(value, date) else date.today()

        if field_type == "radio":
            valid_options = field_options if field_options else ["Option 1", "Option 2"]
            return value if value in valid_options else valid_options[0]

        if field_type == "select":
            return value if isinstance(value, str) else ""

        return value if isinstance(value, str) else ""

    def init_field_value(col_name, field_type, field_options):
        key = f"add__{col_name}"

        if key not in st.session_state:
            st.session_state[key] = default_value_for_type(field_type, field_options)
        else:
            st.session_state[key] = coerce_value(
                field_type,
                st.session_state[key],
                field_options
            )

    def reset_form_values():
        for c in current_df.columns:
            field_meta = normalize_field_meta(options_map.get(str(c).strip(), {"type": "text", "options": []}))
            field_type = field_meta.get("type", "text")
            field_options = field_meta.get("options", [])
            st.session_state[f"add__{c}"] = default_value_for_type(field_type, field_options)

    def add_row_now():
        new_row = {}

        for c in current_df.columns:
            field_meta = normalize_field_meta(options_map.get(str(c).strip(), {"type": "text", "options": []}))
            field_type = field_meta.get("type", "text")
            value = st.session_state.get(f"add__{c}", "")

            if field_type == "date" and value not in ("", None):
                value = str(value)

            new_row[c] = value

        st.session_state.df = pd.concat(
            [st.session_state.df, pd.DataFrame([new_row])],
            ignore_index=True
        )

        rows = st.session_state.df.fillna("").to_dict(orient="records")
        r = update_dataset(st.session_state.dataset_id, rows)

        if not r.ok:
            show_http_error(r)
            st.session_state.add_row_expanded = True
            return

        reset_form_values()
        st.session_state.add_row_expanded = True
        st.rerun()

    st.markdown("➕ Añadir observación")
    st.caption("HINT: Use tab to go to the following field.")

    col_left, col_right = st.columns(2)
    columns = list(current_df.columns)

    for i, c in enumerate(columns):
        target_col = col_left if i % 2 == 0 else col_right

        with target_col:
            field_meta = normalize_field_meta(options_map.get(str(c).strip(), {"type": "text", "options": []}))
            field_type = field_meta.get("type", "text")
            field_options = field_meta.get("options", [])

            init_field_value(c, field_type, field_options)

            if field_type == "text":
                st.text_input(c, key=f"add__{c}", placeholder=f"Enter {c}")

            elif field_type == "number":
                st.number_input(
                    c,
                    key=f"add__{c}",
                    step=1.0 if "id" in str(c).lower() or "count" in str(c).lower() else 0.1
                )

            elif field_type == "date":
                st.date_input(c, key=f"add__{c}")

            elif field_type == "radio":
                st.radio(
                    c,
                    field_options if field_options else ["Option 1", "Option 2"],
                    key=f"add__{c}"
                )

            elif field_type == "checkbox":
                st.checkbox(c, key=f"add__{c}")

            elif field_type == "select":
                st.selectbox(
                    c,
                    [""] + field_options,
                    key=f"add__{c}"
                )

            else:
                st.text_input(c, key=f"add__{c}", placeholder=f"Enter {c}")

    st.divider()
    st.button(
        "Guardar nueva fila",
        key="btn_add_row",
        use_container_width=True,
        on_click=add_row_now
    )