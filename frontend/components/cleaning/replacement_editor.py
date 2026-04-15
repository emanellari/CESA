import streamlit as st
from typing import Any, Dict

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