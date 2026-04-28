import streamlit as st

def render_replacements_editor(col_name: str, profile: dict, config: dict):
    st.markdown("### Value grouping")

    if "replacements" not in config[col_name]:
        config[col_name]["replacements"] = []

    detected_values = [str(v) for v in profile.get("unique_values", []) or []]

    # ===================== COMPUTE AVAILABLE VALUES =====================
    used_values = set()
    for r in config[col_name]["replacements"]:
        used_values.update(str(v) for v in r.get("old_values", []))

    available_values = sorted([v for v in detected_values if v not in used_values])

    # ===================== ADD GROUP =====================
    st.markdown("#### Create group")

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_values = st.multiselect(
            "Select values",
            options=available_values,
            key=f"{col_name}_group_select"
        )

    with col2:
        group_name = st.text_input(
            "Group name",
            key=f"{col_name}_group_name"
        )

    if st.button("Add group", key=f"{col_name}_add_group", use_container_width=True):
        if selected_values and group_name.strip():
            config[col_name]["replacements"].append({
                "old_values": selected_values,
                "new": group_name.strip()
            })


            st.session_state.upload_config = config
            st.session_state.cleaning_config = config

            st.rerun()
        else:
            st.warning("Select values and enter a group name.")

    # ===================== CURRENT GROUPS =====================
    st.markdown("#### Current groups")

    remove_indexes = []

    for idx, r in enumerate(config[col_name]["replacements"]):
        with st.container():
            st.markdown("---")
            c1, c2 = st.columns([4, 1])

            with c1:
                st.write(f"**{r['new']}**")
                st.caption(", ".join(r["old_values"]))

            with c2:
                if st.button("Remove", key=f"{col_name}_remove_{idx}"):
                    remove_indexes.append(idx)

    if remove_indexes:
        config[col_name]["replacements"] = [
            r for i, r in enumerate(config[col_name]["replacements"])
            if i not in remove_indexes
        ]
        st.rerun()

    # ===================== REMAINING VALUES =====================
    if available_values:
        with st.expander("Remaining values", expanded=False):
            st.write(", ".join(available_values))


