import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from datetime import date
from api.dataset_api import update_dataset
from utils.ui_helpers import show_http_error


# ===================== FIELD HELPERS =====================
def normalize_field_meta(field_meta):
    if isinstance(field_meta, list) and field_meta:
        field_meta = field_meta[0]
    elif isinstance(field_meta, list):
        field_meta = {"type": "text", "options": []}
    elif not isinstance(field_meta, dict):
        field_meta = {"type": "text", "options": []}

    return {
        "type": field_meta.get("type", "text"),
        "options": field_meta.get("options", []) or [],
    }


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


def format_field_label(column_name):
    return str(column_name).replace("_", " ").strip().title()


def split_columns_by_type(columns, options_map):
    groups = {
        "Numeric Fields": [],
        "Text Fields": [],
        "Select Fields": [],
        "Radio Options": [],
        "Checkbox Fields": [],
        "Date Fields": [],
    }

    for column in columns:
        field_meta = normalize_field_meta(
            options_map.get(str(column).strip(), {"type": "text", "options": []})
        )
        field_type = field_meta["type"]

        if field_type == "number":
            groups["Numeric Fields"].append(column)
        elif field_type == "select":
            groups["Select Fields"].append(column)
        elif field_type == "radio":
            groups["Radio Options"].append(column)
        elif field_type == "checkbox":
            groups["Checkbox Fields"].append(column)
        elif field_type == "date":
            groups["Date Fields"].append(column)
        else:
            groups["Text Fields"].append(column)

    return {
        group_name: group_columns
        for group_name, group_columns in groups.items()
        if group_columns
    }


def get_columns_count_for_section(section):
    if section == "Numeric Fields":
        return 3

    if section == "Date Fields":
        return 3

    if section == "Checkbox Fields":
        return 3

    if section == "Radio Options":
        return 2

    return 2


def render_field_input(column, field_meta):
    field_type = field_meta["type"]
    field_options = field_meta["options"]
    label = format_field_label(column)
    key = f"add__{column}"

    if field_type == "number":
        st.number_input(
            label,
            key=key,
            step=1.0,
            format="%.2f",
        )

    elif field_type == "date":
        st.date_input(
            label,
            key=key,
        )

    elif field_type == "radio":
        st.radio(
            label,
            field_options if field_options else ["Option 1", "Option 2"],
            key=key,
            horizontal=True,
        )

    elif field_type == "checkbox":
        st.checkbox(
            label,
            key=key,
        )

    elif field_type == "select":
        st.selectbox(
            label,
            [""] + field_options,
            key=key,
        )

    else:
        st.text_input(
            label,
            key=key,
        )


# ===================== FORM STATE HELPERS =====================
def init_form_values(current_df, options_map):
    for column in current_df.columns:
        field_meta = normalize_field_meta(
            options_map.get(str(column).strip(), {"type": "text", "options": []})
        )
        key = f"add__{column}"

        if key not in st.session_state:
            st.session_state[key] = default_value_for_type(
                field_meta["type"],
                field_meta["options"],
            )


def reset_form_values(current_df, options_map):
    for column in current_df.columns:
        field_meta = normalize_field_meta(
            options_map.get(str(column).strip(), {"type": "text", "options": []})
        )

        st.session_state[f"add__{column}"] = default_value_for_type(
            field_meta["type"],
            field_meta["options"],
        )


def build_new_row(current_df, options_map):
    new_row = {}

    for column in current_df.columns:
        field_meta = normalize_field_meta(
            options_map.get(str(column).strip(), {"type": "text", "options": []})
        )

        value = st.session_state.get(f"add__{column}", "")

        if field_meta["type"] == "date" and value not in ("", None):
            value = str(value)

        new_row[column] = value

    return new_row


def render_section_fields(section, section_columns, options_map):
    columns_count = get_columns_count_for_section(section)
    layout_columns = st.columns(columns_count, gap="medium")

    for index, column in enumerate(section_columns):
        target_column = layout_columns[index % columns_count]

        with target_column:
            field_meta = normalize_field_meta(
                options_map.get(
                    str(column).strip(),
                    {"type": "text", "options": []},
                )
            )
            render_field_input(column, field_meta)


# ===================== FOCUS HELPER =====================
def focus_first_add_row_field():
    components.html(
        """
        <script>
        setTimeout(() => {
            const doc = window.parent.document;

            const selectors = [
                'input[type="text"]',
                'input[type="number"]',
                'input[type="date"]',
                'textarea',
                '[role="combobox"] input'
            ];

            const inputs = Array.from(
                doc.querySelectorAll(selectors.join(","))
            );

            const visibleInputs = inputs.filter((el) => {
                const rect = el.getBoundingClientRect();
                const style = window.parent.getComputedStyle(el);

                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.visibility !== "hidden" &&
                    style.display !== "none" &&
                    !el.disabled &&
                    !el.readOnly
                );
            });

            if (visibleInputs.length > 0) {
                const firstInput = visibleInputs[0];

                firstInput.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                setTimeout(() => {
                    firstInput.focus();
                    firstInput.select?.();
                }, 250);
            }
        }, 650);
        </script>
        """,
        height=0,
    )


# ===================== MAIN COMPONENT =====================
def render_add_row_form():
    # ===================== SAFETY CHECK =====================
    if "df" not in st.session_state or st.session_state.df is None:
        st.info("No dataset is currently loaded.")
        return

    current_df = st.session_state.df

    if current_df.empty and len(current_df.columns) == 0:
        st.info("The current dataset has no columns available.")
        return

    dataset_id = st.session_state.get("dataset_id")

    if not dataset_id:
        st.warning("No dataset ID found. Please open a dataset before adding rows.")
        return

    meta = st.session_state.get("dataset_meta", {}) or {}
    options_map = meta.get("options", {}) or {}

    # ===================== LOCAL CSS =====================
    st.markdown(
        """
        <style>
        .add-record-summary {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }

        .add-record-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.38rem 0.65rem;
            border-radius: 999px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            color: #475569;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .form-quick-note {
            margin-bottom: 0.9rem;
            padding: 0.75rem 0.9rem;
            border-radius: 14px;
            background: linear-gradient(90deg, #eff6ff 0%, #f8fafc 100%);
            border: 1px solid #dbeafe;
            color: #334155;
            font-size: 0.9rem;
            line-height: 1.5;
        }

        div[data-testid="stExpander"] {
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            background: #ffffff;
            margin-bottom: 0.7rem;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.025);
        }

        div[data-testid="stExpander"] details {
            border: none !important;
            box-shadow: none !important;
            margin-bottom: 0 !important;
        }

        div[data-testid="stExpander"] summary {
            font-size: 0.92rem;
            font-weight: 700;
            color: #1e293b;
        }

        div[data-testid="stNumberInput"],
        div[data-testid="stTextInput"],
        div[data-testid="stDateInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stRadio"],
        div[data-testid="stCheckbox"] {
            margin-bottom: 0.45rem;
        }

        .add-row-actions-note {
            color: #64748b;
            font-size: 0.85rem;
            line-height: 1.45;
            margin-top: 0.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ===================== RESET / INIT =====================
    if st.session_state.get("reset_add_row_form", False):
        reset_form_values(current_df, options_map)
        st.session_state.reset_add_row_form = False

    init_form_values(current_df, options_map)

    # Focus first field after successful add + rerun
    if st.session_state.get("focus_add_row_first_field", False):
        focus_first_add_row_field()
        st.session_state.focus_add_row_first_field = False

    columns = list(current_df.columns)
    groups = split_columns_by_type(columns, options_map)

    total_fields = len(columns)
    total_sections = len(groups)

    # ===================== HEADER =====================
    st.markdown(
        """
        <div class="form-section-title">Add New Record</div>
        <div class="form-section-subtitle">
            Complete the fields below to insert a new row into the active dataset.
            Sections stay open so you can enter many values quickly.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="add-record-summary">
            <div class="add-record-pill">Fields: {total_fields}</div>
            <div class="add-record-pill">Sections: {total_sections}</div>
            <div class="add-record-pill">Mode: Fast entry</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("add_row_success"):
        st.success(st.session_state["add_row_success"])
        del st.session_state["add_row_success"]

    st.markdown(
        """
        <div class="form-quick-note">
            Fill the visible sections from top to bottom. Numeric and date fields are arranged
            in compact columns to reduce scrolling while keeping the form readable.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===================== FORM =====================
    with st.form("add_row_form", clear_on_submit=False):
        for section, section_columns in groups.items():
            section_label = f"{section} · {len(section_columns)}"

            with st.expander(section_label, expanded=True):
                if section == "Radio Options":
                    st.caption("Keyboard tip: use ← → to move between options.")

                if section == "Checkbox Fields":
                    st.caption("Keyboard tip: press SPACE to toggle selection.")

                render_section_fields(section, section_columns, options_map)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        action_left, action_right = st.columns([2.2, 1], gap="medium")

        submitted = action_left.form_submit_button(
            "Add Row",
            use_container_width=True,
            type="primary",
        )

        reset_clicked = action_right.form_submit_button(
            "Reset Form",
            use_container_width=True,
        )

        st.markdown(
            """
            <div class="add-row-actions-note">
                Saving adds the row to the dataset and updates the backend immediately.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ===================== ACTION LOGIC =====================
    if reset_clicked:
        st.session_state.reset_add_row_form = True
        st.session_state.focus_add_row_first_field = True
        st.rerun()

    if submitted:
        new_row = build_new_row(current_df, options_map)

        updated_df = pd.concat(
            [st.session_state.df, pd.DataFrame([new_row])],
            ignore_index=True,
        )

        rows = updated_df.fillna("").to_dict(orient="records")
        response = update_dataset(dataset_id, rows)

        if response.ok:
            st.session_state.df = updated_df.copy()
            st.session_state.add_row_success = "Row added successfully."
            st.session_state.reset_add_row_form = True
            st.session_state.focus_add_row_first_field = True
            st.rerun()
        else:
            show_http_error(response)