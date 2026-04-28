import copy
import streamlit as st
import pandas as pd

from api.dataset_api import create_dataset_from_scratch
from utils.ui_helpers import require_login, show_http_error


def render_create_dataset_page():
    require_login()

    st.title("Create Dataset")

    # ===================== STATE INIT =====================
    defaults = {
        "undo_stack_create": [],
        "redo_stack_create": [],
        "new_vars": [],
        "new_ops": {},
        "current_var_type": "text",
        "current_var_options": "",
        "reset_form": False,
        "input_key": 0,  # clave dinámica para resetear input
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ===================== RESET FORM (ANTES DE RENDER) =====================
    if st.session_state.reset_form:
        st.session_state.input_key += 1  # fuerza recreación del input
        st.session_state.current_var_type = "text"
        st.session_state.current_var_options = ""
        st.session_state.reset_form = False

    # ===================== UNDO / REDO =====================
    def push_undo():
        st.session_state.undo_stack_create.append((
            copy.deepcopy(st.session_state.new_vars),
            copy.deepcopy(st.session_state.new_ops),
        ))
        st.session_state.redo_stack_create.clear()

    def do_undo():
        if st.session_state.undo_stack_create:
            st.session_state.redo_stack_create.append((
                st.session_state.new_vars,
                st.session_state.new_ops
            ))
            st.session_state.new_vars, st.session_state.new_ops = \
                st.session_state.undo_stack_create.pop()
            st.rerun()

    def do_redo():
        if st.session_state.redo_stack_create:
            st.session_state.undo_stack_create.append((
                st.session_state.new_vars,
                st.session_state.new_ops
            ))
            st.session_state.new_vars, st.session_state.new_ops = \
                st.session_state.redo_stack_create.pop()
            st.rerun()

    # ===================== DATASET NAME =====================
    st.subheader("Dataset")

    dataset_name = st.text_input(
        "Name",
        key="new_dataset_name",
        placeholder="Customer survey, Sales log..."
    )

    # ===================== ADD FIELD =====================
    st.subheader("Fields")

    col1, col2 = st.columns(2)

    with col1:
        var_name = st.text_input(
            "Field name",
            key=f"input_var_name_{st.session_state.input_key}"
        )

    with col2:
        var_type = st.selectbox(
            "Type",
            ["text", "number", "date", "radio", "checkbox", "select"],
            index=["text", "number", "date", "radio", "checkbox", "select"].index(
                st.session_state.current_var_type
            )
        )

    if var_type != st.session_state.current_var_type:
        st.session_state.current_var_type = var_type
        st.session_state.current_var_options = ""
        st.rerun()

    if var_type in ["radio", "select"]:
        st.session_state.current_var_options = st.text_input(
            "Options",
            value=st.session_state.current_var_options,
            placeholder="Option 1, Option 2"
        )

    # ===================== VALIDATION =====================
    name_clean = var_name.strip()
    exists = name_clean in st.session_state.new_vars
    can_add = name_clean != "" and not exists

    if exists:
        st.caption("Field already exists")

    # ===================== ACTIONS =====================
    col_add, col_undo, col_redo = st.columns([3,1,1])

    with col_add:
        if st.button("Add field", disabled=not can_add):
            push_undo()

            st.session_state.new_vars.append(name_clean)
            st.session_state.new_ops[name_clean] = {
                "type": var_type,
                "options": [
                    o.strip()
                    for o in st.session_state.current_var_options.split(",")
                    if o.strip()
                ],
            }

            # activar reset
            st.session_state.reset_form = True
            st.rerun()

    with col_undo:
        st.button("Undo", on_click=do_undo)

    with col_redo:
        st.button("Redo", on_click=do_redo)

    # ===================== FIELD LIST =====================
    if st.session_state.new_vars:
        st.subheader("Current fields")

        for v in st.session_state.new_vars:
            meta = st.session_state.new_ops[v]

            col_a, col_b = st.columns([5,1])

            with col_a:
                st.write(f"{v} — {meta['type']}")

            with col_b:
                if st.button("Remove", key=f"del_{v}"):
                    push_undo()
                    st.session_state.new_vars.remove(v)
                    st.session_state.new_ops.pop(v)
                    st.rerun()

    # ===================== PREVIEW =====================
    if st.session_state.new_vars:
        with st.expander("Preview form", expanded=False):
            for v in st.session_state.new_vars:
                meta = st.session_state.new_ops[v]
                t = meta["type"]
                opts = meta["options"]

                if t == "text":
                    st.text_input(v)
                elif t == "number":
                    st.number_input(v)
                elif t == "date":
                    st.date_input(v)
                elif t == "radio":
                    st.radio(v, opts or ["Option"])
                elif t == "select":
                    st.selectbox(v, opts or ["Option"])
                elif t == "checkbox":
                    st.checkbox(v)

    # ===================== SUBMIT =====================
    st.divider()

    can_continue = dataset_name.strip() != "" and len(st.session_state.new_vars) > 0

    if not dataset_name:
        st.caption("Enter a dataset name to continue")

    if st.button("Create dataset", disabled=not can_continue):
        with st.spinner("Creating dataset..."):
            payload = {
                "name": dataset_name,
                "options": st.session_state.new_ops,
                "columns": st.session_state.new_vars,
            }

            r = create_dataset_from_scratch(payload)

            if r.ok:
                js = r.json()

                st.session_state.dataset_id = js["dataset_id"]
                st.session_state.dataset_name = js.get("name", dataset_name)
                st.session_state.df = pd.DataFrame(
                    js.get("data", []),
                    columns=js.get("columns", st.session_state.new_vars)
                )
                st.session_state.dataset_meta = js.get("meta", {})

                st.session_state.page = "Editor + Análisis"
                st.rerun()
            else:
                show_http_error(r)