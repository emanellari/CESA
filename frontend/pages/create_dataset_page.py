import copy
import streamlit as st
import pandas as pd

from api.dataset_api import create_dataset_from_scratch
from utils.ui_helpers import require_login, show_http_error

def render_create_dataset_page():
    require_login()

    # ===================== PAGE HEADER =====================
    st.header("Create Dataset from Scratch")

    # ===================== UNDO / REDO FUNCTIONS =====================
    if "undo_stack_create" not in st.session_state:
        st.session_state.undo_stack_create = []
    if "redo_stack_create" not in st.session_state:
        st.session_state.redo_stack_create = []
    if "new_vars" not in st.session_state:
        st.session_state.new_vars = []
    if "new_ops" not in st.session_state:
        st.session_state.new_ops = {}

    def push_undo():
        snap = (
            copy.deepcopy(st.session_state.new_vars),
            copy.deepcopy(st.session_state.new_ops),
        )
        st.session_state.undo_stack_create.append(snap)
        st.session_state.redo_stack_create.clear()

    def do_undo():
        if not st.session_state.undo_stack_create:
            return
        snap_current = (
            copy.deepcopy(st.session_state.new_vars),
            copy.deepcopy(st.session_state.new_ops),
        )
        st.session_state.redo_stack_create.append(snap_current)
        prev_vars, prev_ops = st.session_state.undo_stack_create.pop()
        st.session_state.new_vars = prev_vars
        st.session_state.new_ops = prev_ops
        st.rerun()

    def do_redo():
        if not st.session_state.redo_stack_create:
            return
        snap_current = (
            copy.deepcopy(st.session_state.new_vars),
            copy.deepcopy(st.session_state.new_ops),
        )
        st.session_state.undo_stack_create.append(snap_current)
        next_vars, next_ops = st.session_state.redo_stack_create.pop()
        st.session_state.new_vars = next_vars
        st.session_state.new_ops = next_ops
        st.rerun()

    # ===================== TOP BAR =====================
    col_name, col_undo, col_redo = st.columns([4,1,1])
    with col_name:
        st.text_input("Dataset Name", key="new_dataset_name")
    with col_undo:
        st.button("Undo", on_click=do_undo)
    with col_redo:
        st.button("Redo", on_click=do_redo)

    # ===================== DYNAMIC VARIABLE FORM =====================
    if "current_var_type" not in st.session_state:
        st.session_state.current_var_type = "text"
    if "current_var_options" not in st.session_state:
        st.session_state.current_var_options = ""

    var_name = st.text_input("Variable Name", key="input_var_name")
    var_type = st.selectbox(
        "Field Type",
        ["text", "number", "date", "radio", "checkbox", "select"],
        index=["text", "number", "date", "radio", "checkbox", "select"].index(st.session_state.current_var_type)
    )

    # 🔄 Update session_state for live dynamic render
    if var_type != st.session_state.current_var_type:
        st.session_state.current_var_type = var_type
        st.session_state.current_var_options = ""  # reset options on type change
        st.rerun()

    # Show options input immediately if type supports options
    if var_type in ["radio", "select"]:
        st.session_state.current_var_options = st.text_input(
            "Options (comma-separated)",
            value=st.session_state.current_var_options,
            placeholder="Option 1, Option 2, Option 3"
        )

    # Button to add variable
    if st.button("Add Variable"):
        name = var_name.strip()
        if not name:
            st.warning("Please enter a variable name.")
        elif name in st.session_state.new_vars:
            st.warning("Variable already exists.")
        else:
            push_undo()
            st.session_state.new_vars.append(name)
            st.session_state.new_ops[name] = {
                "type": var_type,
                "options": [o.strip() for o in st.session_state.current_var_options.split(",") if o.strip()]
            }
            st.success(f"Variable added: {name}")
            st.session_state.current_var_options = ""
            st.rerun()

    # ===================== FORM PREVIEW =====================
    st.write("### Form Preview")
    for v in st.session_state.new_vars:
        meta = st.session_state.new_ops.get(v, {})
        field_type = meta.get("type", "text")
        options = meta.get("options", [])

        if field_type == "text":
            st.text_input(v)
        elif field_type == "number":
            st.number_input(v)
        elif field_type == "date":
            st.date_input(v)
        elif field_type == "radio":
            st.radio(v, options if options else ["Option 1"])
        elif field_type == "select":
            st.selectbox(v, options if options else ["Option 1"])
        elif field_type == "checkbox":
            st.checkbox(v)

    # ===================== CONTINUE BUTTON =====================
    can_continue = len(st.session_state.new_vars) > 0
    if st.button("Continue", disabled=not can_continue):
        payload = {
            "name": st.session_state.new_dataset_name,
            "options": st.session_state.new_ops,
            "columns": st.session_state.new_vars,
        }
        r = create_dataset_from_scratch(payload)

        if r.ok:
            js = r.json()
            st.session_state.dataset_id = js["dataset_id"]
            st.session_state.dataset_name = js.get("name", st.session_state.new_dataset_name)
            st.session_state.df = pd.DataFrame(js.get("data", []), columns=js.get("columns", st.session_state.new_vars))
            st.session_state.dataset_meta = js.get("meta", {})

            # ✅ SET PAGE BEFORE ANY rerun / spinner
            st.session_state.page = "Editor + Análisis"

            st.rerun()
        else:
            show_http_error(r)