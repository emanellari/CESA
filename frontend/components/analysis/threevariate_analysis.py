import streamlit as st
import pandas as pd
import plotly.express as px

from services.stat_service import detect_is_numeric

from components.charts import render_three_scatter_by_group, render_bar

def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def _build_three_meta_df(
    col1, col2, col3,
    s1, s2, s3,
    t1, t2, t3,
    auto_mode, final_mode,
    total_rows, valid_rows, removed_rows, valid_pct
):

    return pd.DataFrame([
        {"Property": "Variable 1", "Value": col1},
        {"Property": "Variable 2", "Value": col2},
        {"Property": "Variable 3", "Value": col3},
        {"Property": "Variable 1 dtype", "Value": str(s1.dtype)},
        {"Property": "Variable 2 dtype", "Value": str(s2.dtype)},
        {"Property": "Variable 3 dtype", "Value": str(s3.dtype)},
        {"Property": "Variable 1 detected type", "Value": t1},
        {"Property": "Variable 2 detected type", "Value": t2},
        {"Property": "Variable 3 detected type", "Value": t3},
        {"Property": "Auto detected mode", "Value": auto_mode},
        {"Property": "Final mode", "Value": final_mode},
        {"Property": "Rows", "Value": total_rows},
        {"Property": "Valid rows", "Value": valid_rows},
        {"Property": "Removed rows", "Value": removed_rows},
        {"Property": "Validity %", "Value": f"{valid_pct}%"},
    ])
def render_three_grouped_means(df: pd.DataFrame, cat1: str, cat2: str, num_col: str):
    temp = df[[cat1, cat2, num_col]].copy()
    temp[cat1] = temp[cat1].fillna("(missing)").astype(str)
    temp[cat2] = temp[cat2].fillna("(missing)").astype(str)
    temp[num_col] = pd.to_numeric(temp[num_col], errors="coerce")

    n_before = len(temp)
    temp = temp.dropna(subset=[num_col])
    n_after = len(temp)

    st.caption(f"Valid observations used: {n_after} / {n_before}")

    if temp.empty:
        st.warning("No valid numeric observations found.")
        return

    summary = (
        temp.groupby([cat1, cat2])[num_col]
        .agg(["count", "mean", "median", "min", "max", "std"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )

    st.markdown("#### Grouped Descriptive Statistics")
    st.dataframe(summary, use_container_width=True)

    top_df = summary.head(25).copy()
    top_df["Group"] = top_df[cat1] + " | " + top_df[cat2]

    fig = px.bar(
        top_df,
        x="Group",
        y="mean",
        title=f"Mean of {num_col} by {cat1} and {cat2}"
    )
    st.plotly_chart(fig, use_container_width=True)
def render_three_bubble_chart(df: pd.DataFrame, col_x: str, col_y: str, col_z: str):
    temp = df[[col_x, col_y, col_z]].copy()
    temp[col_x] = pd.to_numeric(temp[col_x], errors="coerce")
    temp[col_y] = pd.to_numeric(temp[col_y], errors="coerce")
    temp[col_z] = pd.to_numeric(temp[col_z], errors="coerce")

    n_before = len(temp)
    temp = temp.dropna()
    n_after = len(temp)

    st.caption(f"Valid observations used: {n_after} / {n_before}")

    if temp.empty:
        st.warning("No valid observations for the three numeric variables.")
        return

    fig = px.scatter(
        temp,
        x=col_x,
        y=col_y,
        size=col_z,
        title=f"{col_x} vs {col_y} with bubble size = {col_z}"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Summary")
    st.dataframe(temp.describe().T, use_container_width=True)
def render_three_way_group_summary(temp: pd.DataFrame, num_col: str, cat1: str, cat2: str):
    temp = temp.copy()
    temp[num_col] = pd.to_numeric(temp[num_col], errors="coerce")
    temp[cat1] = temp[cat1].fillna("(missing)").astype(str)
    temp[cat2] = temp[cat2].fillna("(missing)").astype(str)

    before = len(temp)
    temp = temp.dropna(subset=[num_col])
    after = len(temp)

    st.caption(f"Valid rows used: {after} / {before}")

    if temp.empty:
        st.warning(f"No valid numeric data found in **{num_col}**.")
        return

    summary = (
        temp.groupby([cat1, cat2])[num_col]
        .agg(["count", "mean", "median", "min", "max", "std"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )

    st.markdown(f"#### {num_col} by {cat1} and {cat2}")
    st.dataframe(summary, use_container_width=True)

    top_rows = summary.head(20).copy()
    top_rows["group"] = top_rows[cat1] + " | " + top_rows[cat2]

    render_bar(
        top_rows["group"],
        top_rows["mean"],
        f"Mean of {num_col} by {cat1} and {cat2}",
        ylabel=f"Mean of {num_col}"
    )
def render_bubble_chart(temp: pd.DataFrame, col_x: str, col_y: str, col_z: str):

    fig = px.scatter(
        temp,
        x=col_x,
        y=col_y,
        size=col_z,
        title=f"{col_x} vs {col_y} with bubble size = {col_z}"
    )
    st.plotly_chart(fig, use_container_width=True)
def render_colored_scatter(temp: pd.DataFrame, col_x: str, col_y: str, col_z: str):

    fig = px.scatter(
        temp,
        x=col_x,
        y=col_y,
        color=col_z,
        title=f"{col_x} vs {col_y} grouped by {col_z}"
    )
    st.plotly_chart(fig, use_container_width=True)
def _ensure_threevar_styles():
    st.markdown("""
    <style>
    .tv-header {
        padding: 1.15rem 1.2rem 1rem 1.2rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 55%, #eef6ff 100%);
        border: 1px solid #e5e7eb;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }
    .tv-title {
        font-size: 1.55rem;
        font-weight: 750;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .tv-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .tv-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
    }
    .tv-kpi {
        min-height: 112px;
        position: relative;
        overflow: hidden;
    }
    .tv-kpi-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.75rem;
    }
    .tv-kpi-title {
        font-size: 0.84rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 0.3rem;
    }
    .tv-kpi-value {
        font-size: 1.38rem;
        line-height: 1.15;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.15rem;
    }
    .tv-kpi-subtitle {
        font-size: 0.81rem;
        color: #64748b;
    }
    .tv-panel-title {
        font-size: 1.02rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.45rem;
    }
    .tv-panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.75rem;
    }
    .tv-info {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .tv-success {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .tv-warning {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .tv-danger {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .tv-badge {
        display: inline-block;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    </style>
    """, unsafe_allow_html=True)
def _render_tv_kpi(title: str, value: str, subtitle: str = "", accent: str = "#2563eb"):
    st.markdown(
        f"""
        <div class="tv-card tv-kpi">
            <div class="tv-kpi-line" style="background:{accent};"></div>
            <div class="tv-kpi-title">{title}</div>
            <div class="tv-kpi-value">{value}</div>
            <div class="tv-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
def _type_label(is_num: bool) -> str:
    return "Numeric" if is_num else "Categorical"
def _infer_three_mode(type_map: dict[str, bool]) -> str:
    num_count = sum(type_map.values())
    if num_count == 2:
        return "Numeric + Numeric + Categorical"
    if num_count == 3:
        return "Numeric + Numeric + Numeric"
    if num_count == 1:
        return "Numeric + Categorical + Categorical"
    return "Categorical + Categorical + Categorical"
def _quality_badge_three(valid_pct: float) -> tuple[str, str]:
    if valid_pct >= 95:
        return "High readiness", "#16a34a"
    if valid_pct >= 80:
        return "Good readiness", "#2563eb"
    if valid_pct >= 60:
        return "Moderate readiness", "#f59e0b"
    return "Low readiness", "#dc2626"
def render_three_variable_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    _ensure_threevar_styles()

    st.markdown("""
    <div class="tv-header">
        <div class="tv-title">Three-variable analysis</div>
        <div class="tv-subtitle">
            Multivariable exploratory analysis for three selected variables with automatic type detection,
            readiness checks, and adaptive analysis routing based on variable structure.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df is None or df.empty:
        st.warning("No valid dataframe is available for three-variable analysis.")
        return

    if not cols_for_stats:
        st.warning("No columns are available for three-variable analysis.")
        return

    valid_cols = [c for c in cols_for_stats if c in df.columns]
    if len(valid_cols) < 3:
        st.warning("At least three valid columns are required for three-variable analysis.")
        return

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])

    with c1:
        col1 = st.selectbox("Variable 1", valid_cols, key="tri_col_1")

    with c2:
        idx2 = 1 if len(valid_cols) > 1 else 0
        col2 = st.selectbox("Variable 2", valid_cols, index=idx2, key="tri_col_2")

    with c3:
        idx3 = 2 if len(valid_cols) > 2 else 0
        col3 = st.selectbox("Variable 3", valid_cols, index=idx3, key="tri_col_3")

    with c4:
        mode = st.selectbox(
            "Analysis mode",
            [
                "Auto",
                "Numeric + Numeric + Categorical",
                "Numeric + Numeric + Numeric",
                "Numeric + Categorical + Categorical",
                "Categorical + Categorical + Categorical",
            ],
            key="tri_mode"
        )

    if len({col1, col2, col3}) < 3:
        st.info("Choose three different variables.")
        return

    s1 = df[col1]
    s2 = df[col2]
    s3 = df[col3]

    is_num_1, _ = detect_is_numeric(s1)
    is_num_2, _ = detect_is_numeric(s2)
    is_num_3, _ = detect_is_numeric(s3)

    type_map = {
        col1: is_num_1,
        col2: is_num_2,
        col3: is_num_3,
    }

    auto_mode = _infer_three_mode(type_map)
    final_mode = auto_mode if mode == "Auto" else mode
    decision_source = "Automatic detection" if mode == "Auto" else "Manual override"

    total_rows = len(df)

    if final_mode == "Numeric + Numeric + Categorical":
        numeric_cols = [c for c, is_num in type_map.items() if is_num]
        categorical_cols = [c for c, is_num in type_map.items() if not is_num]

        if len(numeric_cols) == 2 and len(categorical_cols) == 1:
            col_x, col_y = numeric_cols[0], numeric_cols[1]
            col_z = categorical_cols[0]
        else:
            col_x, col_y, col_z = col1, col2, col3

        temp = df[[col_x, col_y, col_z]].copy()
        temp[col_x] = pd.to_numeric(temp[col_x], errors="coerce")
        temp[col_y] = pd.to_numeric(temp[col_y], errors="coerce")
        valid_rows = int(temp.dropna(subset=[col_x, col_y]).shape[0])

    elif final_mode == "Numeric + Numeric + Numeric":
        temp = df[[col1, col2, col3]].copy()
        temp[col1] = pd.to_numeric(temp[col1], errors="coerce")
        temp[col2] = pd.to_numeric(temp[col2], errors="coerce")
        temp[col3] = pd.to_numeric(temp[col3], errors="coerce")
        valid_rows = int(temp.dropna(subset=[col1, col2, col3]).shape[0])
        col_x, col_y, col_z = col1, col2, col3

    elif final_mode == "Numeric + Categorical + Categorical":
        temp = df[[col1, col2, col3]].copy()
        valid_rows = int(temp.dropna().shape[0])
        col_x, col_y, col_z = col1, col2, col3

    else:
        temp = df[[col1, col2, col3]].copy()
        valid_rows = int(temp.dropna().shape[0])
        col_x, col_y, col_z = col1, col2, col3

    removed_rows = total_rows - valid_rows
    valid_pct = _safe_pct(valid_rows, total_rows)
    badge_text, badge_color = _quality_badge_three(valid_pct)

    t1 = _type_label(is_num_1)
    t2 = _type_label(is_num_2)
    t3 = _type_label(is_num_3)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        _render_tv_kpi("Variable 1", col1, t1, "#2563eb")
    with k2:
        _render_tv_kpi("Variable 2", col2, t2, "#0ea5e9")
    with k3:
        _render_tv_kpi("Variable 3", col3, t3, "#16a34a")
    with k4:
        _render_tv_kpi("Auto mode", auto_mode, decision_source, "#f59e0b")
    with k5:
        _render_tv_kpi("Valid rows", f"{valid_rows:,}", f"{valid_pct}%", badge_color)

    tabs = st.tabs([
        "Analysis",
        "Metadata",
        "Interpretation",
        "Suggested next steps"
    ])

    with tabs[0]:
        st.markdown(
            f"""
            <div class="tv-card" style="margin-bottom: 0.9rem;">
                <div class="tv-panel-title">Current configuration</div>
                <div class="tv-panel-subtitle">
                    The selected variables are being analyzed as <b>{final_mode}</b>.
                </div>
                <div class="tv-badge" style="background:{badge_color}18;color:{badge_color};border:1px solid {badge_color}40;">
                    {badge_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if valid_rows == 0:
            st.markdown(
                """
                <div class="tv-danger">
                    No valid observations remain after cleaning for the selected three-variable configuration.
                </div>
                """,
                unsafe_allow_html=True
            )
            return

        if final_mode == "Numeric + Numeric + Categorical":
            render_three_scatter_by_group(df, col_x, col_y, col_z)

        elif final_mode == "Numeric + Numeric + Numeric":
            render_three_bubble_chart(df, col1, col2, col3)

        elif final_mode == "Numeric + Categorical + Categorical":
            numeric_candidates = [c for c, is_num in type_map.items() if is_num]
            categorical_candidates = [c for c, is_num in type_map.items() if not is_num]

            if len(numeric_candidates) == 1 and len(categorical_candidates) == 2:
                render_three_grouped_means(
                    df,
                    categorical_candidates[0],
                    categorical_candidates[1],
                    numeric_candidates[0]
                )
            else:
                st.markdown(
                    """
                    <div class="tv-warning">
                        The selected manual override does not match the detected variable structure closely enough
                        to run a grouped mean summary safely.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        elif final_mode == "Categorical + Categorical + Categorical":
            st.markdown(
                """
                <div class="tv-warning">
                    A dedicated three-categorical analysis view is not connected yet.
                    Recommended extension: multi-way contingency tables, normalized stacked bars, or mosaic plots.
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            st.warning("Unsupported three-variable mode.")

    with tabs[1]:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown('<div class="tv-panel-title">Analysis metadata</div>', unsafe_allow_html=True)
            st.markdown('<div class="tv-panel-subtitle">Detected structure and row validity for the selected triple.</div>', unsafe_allow_html=True)

            meta_df = _build_three_meta_df(
                col1, col2, col3,
                s1, s2, s3,
                t1, t2, t3,
                auto_mode, final_mode,
                total_rows, valid_rows, removed_rows, valid_pct
            )
            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="tv-panel-title">Quick structural signals</div>', unsafe_allow_html=True)
            st.markdown('<div class="tv-panel-subtitle">Readiness and expected interpretability of the current multivariable configuration.</div>', unsafe_allow_html=True)

            if valid_pct >= 95:
                st.markdown(
                    """
                    <div class="tv-success">
                        Coverage is very strong, so the three-variable view is based on nearly the full dataset.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif valid_pct >= 80:
                st.markdown(
                    """
                    <div class="tv-info">
                        Coverage is good. The selected analysis should remain broadly representative.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif valid_pct >= 60:
                st.markdown(
                    """
                    <div class="tv-warning">
                        A notable share of rows is excluded, so visible patterns may reflect only a subset of the data.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class="tv-danger">
                        Coverage is low. Interpret any multivariable patterns with caution.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if final_mode == "Numeric + Numeric + Categorical":
                st.markdown(
                    """
                    <div class="tv-success">
                        This is the strongest currently supported three-variable setup for visual exploration.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif final_mode == "Numeric + Numeric + Numeric":
                st.markdown(
                    """
                    <div class="tv-info">
                        Three numeric variables are suitable for advanced multivariate exploration.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif final_mode == "Numeric + Categorical + Categorical":
                st.markdown(
                    """
                    <div class="tv-info">
                        This structure is good for grouped comparisons, especially via faceting or multi-level summaries.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class="tv-info">
                        Fully categorical triples are best interpreted through contingency structures rather than point-based charts.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    with tabs[2]:
        st.markdown('<div class="tv-panel-title">Automatic interpretation</div>', unsafe_allow_html=True)
        st.markdown('<div class="tv-panel-subtitle">System-generated reading of the selected three-variable structure.</div>', unsafe_allow_html=True)

        insights = [
            f"The selected triple is <b>{col1}</b>, <b>{col2}</b>, and <b>{col3}</b>.",
            f"Automatic type detection classified them as <b>{t1}</b>, <b>{t2}</b>, and <b>{t3}</b> respectively.",
            f"The automatically inferred structure is <b>{auto_mode}</b>, while the currently applied structure is <b>{final_mode}</b>.",
            f"The analysis retains <b>{valid_rows:,}</b> valid rows out of <b>{total_rows:,}</b>, corresponding to <b>{valid_pct}%</b> usable coverage.",
        ]

        if final_mode == "Numeric + Numeric + Categorical":
            insights.append(
                "This configuration is well suited to checking whether the relationship between two numeric variables changes across groups."
            )
            insights.append(
                "Typical questions here are whether groups occupy different regions, show different slopes, or overlap heavily."
            )
        elif final_mode == "Numeric + Numeric + Numeric":
            insights.append(
                "This configuration is naturally multivariate and can reveal joint numeric structure."
            )
        elif final_mode == "Numeric + Categorical + Categorical":
            insights.append(
                "This configuration is useful for comparing a numeric outcome across a two-level grouping structure."
            )
        else:
            insights.append(
                "This configuration is mainly about category co-occurrence patterns across three categorical dimensions."
            )

        if valid_pct < 80:
            insights.append(
                "Because usable coverage is reduced, detected patterns may describe only a filtered subset of rows."
            )

        if mode != "Auto":
            insights.append(
                "Manual override is active, so interpretation should follow the intended analytical role of each variable rather than the raw type detection alone."
            )

        for txt in insights:
            st.markdown(f'<div class="tv-info">{txt}</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="tv-panel-title">Suggested next steps</div>', unsafe_allow_html=True)
        st.markdown('<div class="tv-panel-subtitle">Recommended next analyses for the current three-variable configuration.</div>', unsafe_allow_html=True)

        if final_mode == "Numeric + Numeric + Categorical":
            steps = [
                "Inspect whether different groups occupy different regions in the scatter plot.",
                "Compute separate correlations by group to detect segment-specific relationships.",
                "Add per-group trend lines to compare directional differences.",
                "Collapse rare categories if the legend becomes too fragmented."
            ]
        elif final_mode == "Numeric + Numeric + Numeric":
            steps = [
                "Add a 3D scatter plot or use one numeric variable as point color or point size.",
                "Compute a three-variable correlation matrix and partial correlations.",
                "Explore multicollinearity or regression structure among the three numeric variables.",
                "Use dimensionality-reduction views if the numeric space becomes complex."
            ]
        elif final_mode == "Numeric + Categorical + Categorical":
            steps = [
                "Compare grouped means and medians across the two categorical variables.",
                "Use faceted boxplots or violin plots for the numeric variable.",
                "Consider two-way ANOVA when the assumptions are acceptable.",
                "Review category imbalance before making strong comparisons."
            ]
        else:
            steps = [
                "Build multi-way contingency tables.",
                "Use normalized stacked bar charts or mosaic-style visual summaries.",
                "Check sparse category combinations before interpreting rare intersections.",
                "Group rare categories to improve readability and stability."
            ]

        for step in steps:
            st.markdown(f'<div class="tv-success">{step}</div>', unsafe_allow_html=True)