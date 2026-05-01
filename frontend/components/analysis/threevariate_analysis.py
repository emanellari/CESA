import pandas as pd
import streamlit as st
import plotly.express as px

from services.stat_service import detect_is_numeric


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def _format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _format_number(value, decimals: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    return f"{value:,.{decimals}f}"


def _truncate_text(value, max_len: int = 24) -> str:
    text = str(value)
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


def _normalize_missing(s: pd.Series) -> pd.Series:
    s_clean = s.astype(str).str.strip()

    missing_like = {
        "",
        "na",
        "n/a",
        "n.a",
        "nan",
        "null",
        "none",
        "missing",
        "-",
        "--",
    }

    return s_clean.mask(s_clean.str.lower().isin(missing_like), pd.NA)


def _plot_layout(fig, height: int = 430, x_title: str = "", y_title: str = ""):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=25, b=10),
        xaxis_title=x_title,
        yaxis_title=y_title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        legend_title_text="",
    )
    return fig


def _chart_height(rows: int, minimum: int = 380, maximum: int = 620) -> int:
    return min(maximum, max(minimum, 280 + min(rows, 18) * 18))


# ============================================================
# UI HELPERS
# ============================================================

def _render_tv_kpi(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="tv-card tv-kpi">
            <div class="tv-kpi-title">{title}</div>
            <div class="tv-kpi-value">{value}</div>
            <div class="tv-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str):
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="tv-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="tv-panel-title">{title}</div>
        <div class="tv-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_current_config(final_mode: str, decision_source: str, badge_text: str):
    st.markdown(
        f"""
        <div class="tv-card">
            <div class="tv-panel-title">Current configuration</div>
            <div class="tv-panel-subtitle">
                The selected variables are being analyzed as <b>{final_mode}</b>.
                Detection mode: <b>{decision_source}</b>.
            </div>
            <div class="tv-badge">{badge_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TYPE / MODE HELPERS
# ============================================================

def _type_label(is_num: bool) -> str:
    return "Numeric" if is_num else "Categorical"


def _infer_three_mode(type_map: dict[str, bool]) -> str:
    numeric_count = sum(type_map.values())

    if numeric_count == 3:
        return "Numeric + Numeric + Numeric"

    if numeric_count == 2:
        return "Numeric + Numeric + Categorical"

    if numeric_count == 1:
        return "Numeric + Categorical + Categorical"

    return "Categorical + Categorical + Categorical"


def _quality_badge_three(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "High readiness"
    if valid_pct >= 80:
        return "Good readiness"
    if valid_pct >= 60:
        return "Moderate readiness"
    return "Low readiness"


def _alert_type_from_validity(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "success"
    if valid_pct >= 80:
        return "info"
    if valid_pct >= 60:
        return "warning"
    return "danger"


def _get_validity_message(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "Coverage is very strong, so the three-variable view is based on nearly the full dataset."

    if valid_pct >= 80:
        return "Coverage is good. The selected analysis should remain broadly representative."

    if valid_pct >= 60:
        return "A notable share of rows is excluded, so visible patterns may reflect only a subset of the data."

    return "Coverage is low. Interpret any multivariable patterns with caution."


# ============================================================
# STRUCTURE HELPERS
# ============================================================

def _get_valid_columns(df: pd.DataFrame, cols_for_stats: list[str]) -> list[str]:
    if not cols_for_stats:
        return list(df.columns)

    return [col for col in cols_for_stats if col in df.columns]


def _build_three_meta_df(
    col1: str,
    col2: str,
    col3: str,
    s1: pd.Series,
    s2: pd.Series,
    s3: pd.Series,
    t1: str,
    t2: str,
    t3: str,
    auto_mode: str,
    final_mode: str,
    total_rows: int,
    valid_rows: int,
    removed_rows: int,
    valid_pct: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
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
        ]
    )


def _prepare_three_context(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    col3: str,
    final_mode: str,
    type_map: dict[str, bool],
):
    selected_cols = [col1, col2, col3]
    numeric_cols = [col for col in selected_cols if type_map[col]]
    categorical_cols = [col for col in selected_cols if not type_map[col]]

    if final_mode == "Numeric + Numeric + Categorical":
        if len(numeric_cols) == 2 and len(categorical_cols) == 1:
            x_col, y_col = numeric_cols
            group_col = categorical_cols[0]
        else:
            x_col, y_col, group_col = col1, col2, col3

        temp = df[[x_col, y_col, group_col]].copy()
        temp[x_col] = pd.to_numeric(temp[x_col], errors="coerce")
        temp[y_col] = pd.to_numeric(temp[y_col], errors="coerce")
        temp[group_col] = _normalize_missing(temp[group_col]).fillna("(missing)").astype(str)
        valid_temp = temp.dropna(subset=[x_col, y_col])

        return {
            "temp": valid_temp,
            "numeric_cols": [x_col, y_col],
            "categorical_cols": [group_col],
            "role_cols": {"x": x_col, "y": y_col, "group": group_col},
        }

    if final_mode == "Numeric + Numeric + Numeric":
        temp = df[selected_cols].copy()

        for col in selected_cols:
            temp[col] = pd.to_numeric(temp[col], errors="coerce")

        valid_temp = temp.dropna(subset=selected_cols)

        return {
            "temp": valid_temp,
            "numeric_cols": selected_cols,
            "categorical_cols": [],
            "role_cols": {"x": col1, "y": col2, "size": col3},
        }

    if final_mode == "Numeric + Categorical + Categorical":
        if len(numeric_cols) == 1 and len(categorical_cols) == 2:
            num_col = numeric_cols[0]
            cat1, cat2 = categorical_cols
        else:
            num_col, cat1, cat2 = col1, col2, col3

        temp = df[[num_col, cat1, cat2]].copy()
        temp[num_col] = pd.to_numeric(temp[num_col], errors="coerce")
        temp[cat1] = _normalize_missing(temp[cat1]).fillna("(missing)").astype(str)
        temp[cat2] = _normalize_missing(temp[cat2]).fillna("(missing)").astype(str)
        valid_temp = temp.dropna(subset=[num_col])

        return {
            "temp": valid_temp,
            "numeric_cols": [num_col],
            "categorical_cols": [cat1, cat2],
            "role_cols": {"value": num_col, "cat1": cat1, "cat2": cat2},
        }

    temp = df[selected_cols].copy()

    for col in selected_cols:
        temp[col] = _normalize_missing(temp[col]).fillna("(missing)").astype(str)

    valid_temp = temp.dropna(subset=selected_cols)

    return {
        "temp": valid_temp,
        "numeric_cols": [],
        "categorical_cols": selected_cols,
        "role_cols": {"cat1": col1, "cat2": col2, "cat3": col3},
    }


# ============================================================
# ANALYSIS RENDERERS
# ============================================================

def render_three_numeric_numeric_categorical(temp: pd.DataFrame, x_col: str, y_col: str, group_col: str):
    _render_section_title(
        "Two numeric variables grouped by category",
        "Use this view to see whether the relationship between two numeric variables changes across groups.",
    )

    if temp.empty:
        _render_alert("warning", "No valid rows are available for this grouped scatter plot.")
        return

    m1, m2, m3 = st.columns(3)

    with m1:
        _render_tv_kpi("Valid rows", _format_int(len(temp)), "Used in chart")

    with m2:
        _render_tv_kpi("Groups", _format_int(temp[group_col].nunique()), group_col)

    with m3:
        _render_tv_kpi("Numeric pair", f"{_truncate_text(x_col, 14)} × {_truncate_text(y_col, 14)}", "Scatter view")

    tabs = st.tabs(["Scatter", "Group summary"])

    with tabs[0]:
        fig = px.scatter(
            temp,
            x=x_col,
            y=y_col,
            color=group_col,
            trendline="ols",
            labels={x_col: x_col, y_col: y_col, group_col: group_col},
        )
        fig = _plot_layout(fig, 470, x_col, y_col)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        summary = (
            temp.groupby(group_col)
            .agg(
                rows=(x_col, "count"),
                x_mean=(x_col, "mean"),
                y_mean=(y_col, "mean"),
                x_median=(x_col, "median"),
                y_median=(y_col, "median"),
            )
            .reset_index()
            .sort_values("rows", ascending=False)
        )

        st.dataframe(summary, use_container_width=True, hide_index=True)


def render_three_numeric_numeric_numeric(temp: pd.DataFrame, x_col: str, y_col: str, size_col: str):
    _render_section_title(
        "Three numeric variables",
        "Bubble size represents the third numeric variable while the x/y axes show the first two.",
    )

    if temp.empty:
        _render_alert("warning", "No valid rows are available for the three numeric variables.")
        return

    m1, m2, m3 = st.columns(3)

    with m1:
        _render_tv_kpi("Valid rows", _format_int(len(temp)), "Complete numeric triples")

    with m2:
        _render_tv_kpi("X/Y pair", f"{_truncate_text(x_col, 14)} × {_truncate_text(y_col, 14)}", "Position")

    with m3:
        _render_tv_kpi("Bubble size", _truncate_text(size_col, 18), "Third variable")

    tabs = st.tabs(["Bubble chart", "Correlation matrix", "Summary"])

    with tabs[0]:
        size_series = temp[size_col]

        if size_series.nunique() <= 1 or size_series.max() <= 0:
            _render_alert(
                "warning",
                "The size variable has no usable variation for bubble sizing. A regular scatter plot is shown instead.",
            )

            fig = px.scatter(
                temp,
                x=x_col,
                y=y_col,
                labels={x_col: x_col, y_col: y_col},
            )
        else:
            fig = px.scatter(
                temp,
                x=x_col,
                y=y_col,
                size=size_col,
                labels={x_col: x_col, y_col: y_col, size_col: size_col},
            )

        fig = _plot_layout(fig, 470, x_col, y_col)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        corr_df = temp[[x_col, y_col, size_col]].corr(numeric_only=True)

        fig_corr = px.imshow(
            corr_df,
            text_auto=True,
            aspect="auto",
            labels=dict(color="Correlation"),
        )
        fig_corr = _plot_layout(fig_corr, 420, "", "")
        st.plotly_chart(fig_corr, use_container_width=True)

    with tabs[2]:
        st.dataframe(temp[[x_col, y_col, size_col]].describe().T, use_container_width=True)


def render_three_numeric_categorical_categorical(temp: pd.DataFrame, num_col: str, cat1: str, cat2: str):
    _render_section_title(
        "Numeric outcome by two categorical variables",
        "Use this view to compare a numeric value across combinations of two categorical fields.",
    )

    if temp.empty:
        _render_alert("warning", f"No valid numeric data found in {num_col}.")
        return

    summary = (
        temp.groupby([cat1, cat2])[num_col]
        .agg(["count", "mean", "median", "min", "max", "std"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )

    top_rows = summary.head(25).copy()
    top_rows["Group"] = top_rows[cat1] + " | " + top_rows[cat2]

    m1, m2, m3 = st.columns(3)

    with m1:
        _render_tv_kpi("Valid rows", _format_int(len(temp)), "Used in summary")

    with m2:
        _render_tv_kpi("Group combinations", _format_int(len(summary)), "cat1 × cat2")

    with m3:
        _render_tv_kpi("Numeric outcome", _truncate_text(num_col, 20), "Compared by groups")

    tabs = st.tabs(["Grouped table", "Mean chart", "Heatmap"])

    with tabs[0]:
        st.dataframe(summary, use_container_width=True, hide_index=True)

    with tabs[1]:
        fig = px.bar(
            top_rows.sort_values("mean", ascending=True),
            x="mean",
            y="Group",
            orientation="h",
            text="mean",
            labels={"mean": f"Mean of {num_col}", "Group": "Group"},
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig = _plot_layout(fig, _chart_height(len(top_rows)), f"Mean of {num_col}", "Group")
        st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        pivot = summary.pivot_table(
            index=cat1,
            columns=cat2,
            values="mean",
            aggfunc="mean",
        )

        fig_heatmap = px.imshow(
            pivot,
            text_auto=True,
            aspect="auto",
            labels=dict(color=f"Mean {num_col}"),
        )
        fig_heatmap = _plot_layout(fig_heatmap, 460, cat2, cat1)
        st.plotly_chart(fig_heatmap, use_container_width=True)


def render_three_categorical_categorical_categorical(temp: pd.DataFrame, cat1: str, cat2: str, cat3: str):
    _render_section_title(
        "Three categorical variables",
        "This view summarizes category combinations and highlights the most common intersections.",
    )

    if temp.empty:
        _render_alert("warning", "No valid categorical triples are available.")
        return

    combo_summary = (
        temp.groupby([cat1, cat2, cat3])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    top_rows = combo_summary.head(30).copy()
    top_rows["Combination"] = top_rows[cat1] + " | " + top_rows[cat2] + " | " + top_rows[cat3]

    m1, m2, m3 = st.columns(3)

    with m1:
        _render_tv_kpi("Valid rows", _format_int(len(temp)), "Complete triples")

    with m2:
        _render_tv_kpi("Combinations", _format_int(len(combo_summary)), "Unique intersections")

    with m3:
        _render_tv_kpi("Top count", _format_int(top_rows["count"].max()), "Most frequent combo")

    tabs = st.tabs(["Combination table", "Top combinations"])

    with tabs[0]:
        st.dataframe(combo_summary, use_container_width=True, hide_index=True)

    with tabs[1]:
        fig = px.bar(
            top_rows.sort_values("count", ascending=True),
            x="count",
            y="Combination",
            orientation="h",
            text="count",
            labels={"count": "Count", "Combination": "Combination"},
        )
        fig.update_traces(textposition="outside")
        fig = _plot_layout(fig, _chart_height(len(top_rows)), "Count", "Combination")
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# INTERPRETATION / NEXT STEPS
# ============================================================

def _build_three_interpretation(
    col1: str,
    col2: str,
    col3: str,
    t1: str,
    t2: str,
    t3: str,
    auto_mode: str,
    final_mode: str,
    mode: str,
    valid_rows: int,
    total_rows: int,
    valid_pct: float,
) -> list[str]:
    insights = [
        f"The selected triple is <b>{col1}</b>, <b>{col2}</b>, and <b>{col3}</b>.",
        f"Automatic type detection classified them as <b>{t1}</b>, <b>{t2}</b>, and <b>{t3}</b> respectively.",
        f"The automatically inferred structure is <b>{auto_mode}</b>, while the currently applied structure is <b>{final_mode}</b>.",
        f"The analysis retains <b>{valid_rows:,}</b> valid rows out of <b>{total_rows:,}</b>, corresponding to <b>{valid_pct}%</b> usable coverage.",
    ]

    if final_mode == "Numeric + Numeric + Categorical":
        insights.append(
            "This configuration is useful for checking whether the relationship between two numeric variables changes across groups."
        )
        insights.append(
            "Look for group separation, different slopes, clusters, or overlapping patterns."
        )

    elif final_mode == "Numeric + Numeric + Numeric":
        insights.append(
            "This configuration helps explore joint numeric structure across three continuous or score-like variables."
        )
        insights.append(
            "The bubble chart is useful for visual exploration, while the correlation matrix gives a compact relationship summary."
        )

    elif final_mode == "Numeric + Categorical + Categorical":
        insights.append(
            "This configuration is useful for comparing a numeric outcome across a two-level grouping structure."
        )
        insights.append(
            "The most useful outputs are grouped means, medians, and heatmaps of average values."
        )

    else:
        insights.append(
            "This configuration focuses on category co-occurrence patterns across three categorical dimensions."
        )
        insights.append(
            "The main goal is to find frequent combinations, sparse intersections, and possible grouping needs."
        )

    if valid_pct < 80:
        insights.append(
            "Because usable coverage is reduced, detected patterns may describe only a filtered subset of rows."
        )

    if mode != "Auto":
        insights.append(
            "Manual override is active, so interpretation should follow the intended analytical role of each variable rather than type detection alone."
        )

    return insights


def _build_three_next_steps(final_mode: str, valid_pct: float) -> list[str]:
    if final_mode == "Numeric + Numeric + Categorical":
        steps = [
            "Inspect whether different groups occupy different regions in the scatter plot.",
            "Compare correlations separately by group to detect segment-specific relationships.",
            "Look for groups with unusually high or low dispersion.",
            "Collapse rare categories if the legend becomes too fragmented.",
        ]

    elif final_mode == "Numeric + Numeric + Numeric":
        steps = [
            "Use the bubble chart to inspect whether the third numeric variable changes the visible pattern.",
            "Review the correlation matrix to identify the strongest pairwise relationships.",
            "Consider regression or multicollinearity checks if the three variables will be used in modeling.",
            "Use dimensionality-reduction views if the numeric structure becomes complex.",
        ]

    elif final_mode == "Numeric + Categorical + Categorical":
        steps = [
            "Compare grouped means and medians across the two categorical variables.",
            "Use the heatmap to find combinations with unusually high or low averages.",
            "Check group counts before interpreting mean differences strongly.",
            "Consider two-way ANOVA when assumptions are acceptable.",
        ]

    else:
        steps = [
            "Review the most common category combinations.",
            "Check whether many combinations are rare or sparse.",
            "Group rare categories to improve readability and stability.",
            "Use normalized stacked bars or mosaic-style summaries for deeper categorical exploration.",
        ]

    if valid_pct < 80:
        steps.append(
            "Review missingness because reduced coverage can make the three-variable pattern less representative."
        )

    return steps


# ============================================================
# MAIN COMPONENT
# ============================================================

def render_three_variable_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown(
        """
        <div class="tv-header">
            <div class="tv-title">Three-variable analysis</div>
            <div class="tv-subtitle">
                Explore relationships across three selected variables with automatic type detection,
                adaptive visualizations, interpretation, and suggested next steps.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.warning("No valid dataframe is available for three-variable analysis.")
        return

    valid_cols = _get_valid_columns(df, cols_for_stats)

    if len(valid_cols) < 3:
        st.warning("At least three valid columns are required for three-variable analysis.")
        return

    st.markdown('<div class="tv-toolbar">', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])

    with c1:
        col1 = st.selectbox(
            "Variable 1",
            valid_cols,
            key="tri_col_1",
            help="First variable in the three-variable analysis.",
        )

    with c2:
        idx2 = 1 if len(valid_cols) > 1 else 0
        col2 = st.selectbox(
            "Variable 2",
            valid_cols,
            index=idx2,
            key="tri_col_2",
            help="Second variable in the three-variable analysis.",
        )

    with c3:
        idx3 = 2 if len(valid_cols) > 2 else 0
        col3 = st.selectbox(
            "Variable 3",
            valid_cols,
            index=idx3,
            key="tri_col_3",
            help="Third variable in the three-variable analysis.",
        )

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
            key="tri_mode",
            help="Use Auto unless the detected structure does not match your analytical intent.",
        )

    st.markdown(
        """
        <div class="tv-small-muted">
            Auto mode routes the analysis based on detected column types. Manual override is useful when the stored type differs from the analytical meaning.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if len({col1, col2, col3}) < 3:
        _render_alert("info", "Choose three different variables to run this analysis.")
        return

    s1 = df[col1]
    s2 = df[col2]
    s3 = df[col3]

    is_num_1, _ = detect_is_numeric(_normalize_missing(s1))
    is_num_2, _ = detect_is_numeric(_normalize_missing(s2))
    is_num_3, _ = detect_is_numeric(_normalize_missing(s3))

    type_map = {
        col1: is_num_1,
        col2: is_num_2,
        col3: is_num_3,
    }

    auto_mode = _infer_three_mode(type_map)
    final_mode = auto_mode if mode == "Auto" else mode
    decision_source = "Automatic detection" if mode == "Auto" else "Manual override"

    context = _prepare_three_context(
        df=df,
        col1=col1,
        col2=col2,
        col3=col3,
        final_mode=final_mode,
        type_map=type_map,
    )

    temp = context["temp"]

    total_rows = len(df)
    valid_rows = len(temp)
    removed_rows = total_rows - valid_rows
    valid_pct = _safe_pct(valid_rows, total_rows)
    badge_text = _quality_badge_three(valid_pct)

    t1 = _type_label(is_num_1)
    t2 = _type_label(is_num_2)
    t3 = _type_label(is_num_3)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_tv_kpi("Variable 1", _truncate_text(col1), t1)

    with k2:
        _render_tv_kpi("Variable 2", _truncate_text(col2), t2)

    with k3:
        _render_tv_kpi("Variable 3", _truncate_text(col3), t3)

    with k4:
        _render_tv_kpi("Auto mode", auto_mode, decision_source)

    with k5:
        _render_tv_kpi("Valid rows", _format_int(valid_rows), f"{valid_pct}% · {badge_text}")

    tabs = st.tabs(
        [
            "Analysis",
            "Interpretation",
            "Next steps",
            "Metadata",
        ]
    )

    with tabs[0]:
        _render_current_config(
            final_mode=final_mode,
            decision_source=decision_source,
            badge_text=badge_text,
        )

        if valid_rows == 0:
            _render_alert(
                "danger",
                "No valid observations remain after cleaning for the selected three-variable configuration.",
            )
            return

        role_cols = context["role_cols"]

        if final_mode == "Numeric + Numeric + Categorical":
            render_three_numeric_numeric_categorical(
                temp=temp,
                x_col=role_cols["x"],
                y_col=role_cols["y"],
                group_col=role_cols["group"],
            )

        elif final_mode == "Numeric + Numeric + Numeric":
            render_three_numeric_numeric_numeric(
                temp=temp,
                x_col=role_cols["x"],
                y_col=role_cols["y"],
                size_col=role_cols["size"],
            )

        elif final_mode == "Numeric + Categorical + Categorical":
            render_three_numeric_categorical_categorical(
                temp=temp,
                num_col=role_cols["value"],
                cat1=role_cols["cat1"],
                cat2=role_cols["cat2"],
            )

        elif final_mode == "Categorical + Categorical + Categorical":
            render_three_categorical_categorical_categorical(
                temp=temp,
                cat1=role_cols["cat1"],
                cat2=role_cols["cat2"],
                cat3=role_cols["cat3"],
            )

        else:
            st.warning("Unsupported three-variable mode.")

    with tabs[1]:
        _render_section_title(
            "Automatic interpretation",
            "Plain-language reading of the selected three-variable structure.",
        )

        insights = _build_three_interpretation(
            col1=col1,
            col2=col2,
            col3=col3,
            t1=t1,
            t2=t2,
            t3=t3,
            auto_mode=auto_mode,
            final_mode=final_mode,
            mode=mode,
            valid_rows=valid_rows,
            total_rows=total_rows,
            valid_pct=valid_pct,
        )

        for insight in insights:
            _render_alert("info", insight)

    with tabs[2]:
        _render_section_title(
            "Suggested next steps",
            "Recommended workflow for this three-variable configuration.",
        )

        steps = _build_three_next_steps(final_mode, valid_pct)

        for step in steps:
            _render_alert("success", step)

    with tabs[3]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title(
                "Analysis metadata",
                "Detected structure and row validity for the selected triple.",
            )

            meta_df = _build_three_meta_df(
                col1=col1,
                col2=col2,
                col3=col3,
                s1=s1,
                s2=s2,
                s3=s3,
                t1=t1,
                t2=t2,
                t3=t3,
                auto_mode=auto_mode,
                final_mode=final_mode,
                total_rows=total_rows,
                valid_rows=valid_rows,
                removed_rows=removed_rows,
                valid_pct=valid_pct,
            )

            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title(
                "Quick structural signals",
                "Readiness and expected interpretability of the current multivariable configuration.",
            )

            validity_kind = _alert_type_from_validity(valid_pct)
            validity_message = _get_validity_message(valid_pct)
            _render_alert(validity_kind, validity_message)

            if final_mode == "Numeric + Numeric + Categorical":
                _render_alert(
                    "success",
                    "This is one of the strongest three-variable setups for visual exploration.",
                )

            elif final_mode == "Numeric + Numeric + Numeric":
                _render_alert(
                    "info",
                    "Three numeric variables are suitable for bubble charts, correlation matrices, and multivariate exploration.",
                )

            elif final_mode == "Numeric + Categorical + Categorical":
                _render_alert(
                    "info",
                    "This structure is good for grouped comparisons and multi-level summaries.",
                )

            else:
                _render_alert(
                    "info",
                    "Fully categorical triples are best interpreted through combination tables and normalized category views.",
                )

