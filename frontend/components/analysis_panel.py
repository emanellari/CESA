import streamlit as st
import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as sm
import matplotlib.pyplot as plt
import plotly.express as px
import io
import plotly.graph_objects as go
from analysis import render_u
from services.stat_service import (
    detect_is_numeric,
    describe_numeric,
    describe_categorical,
)
from utils.formatters import fmt_metric
from components.charts import (
    render_histogram,
    render_boxplot,
    render_bar,
    render_pie,
    render_scatter,
)


def render_correlation_interpretation(corr: pd.DataFrame):
    st.markdown("#### Correlation Interpretation")

    if corr.empty or len(corr.columns) < 2:
        st.info("Not enough numeric variables to interpret correlations.")
        return

    pairs = []
    cols = corr.columns.tolist()

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.loc[cols[i], cols[j]]
            if pd.notna(value):
                pairs.append({
                    "Variable 1": cols[i],
                    "Variable 2": cols[j],
                    "Correlation": value,
                    "Absolute": abs(value)
                })

    if not pairs:
        st.info("No valid correlations were found.")
        return

    pairs_df = pd.DataFrame(pairs).sort_values("Absolute", ascending=False)
    top = pairs_df.iloc[0]

    if top["Absolute"] < 0.2:
        st.info("No clearly relevant linear correlations were detected among the selected numeric variables.")
        return

    direction = "positive" if top["Correlation"] > 0 else "negative"

    st.write(
        f"The strongest observed linear relationship is between **{top['Variable 1']}** and "
        f"**{top['Variable 2']}**, with a **{direction}** correlation of **{top['Correlation']:.3f}**."
    )

    with st.expander("Correlation Ranking"):
        show_df = pairs_df.copy()
        show_df["Correlation"] = show_df["Correlation"].round(3)
        show_df["Absolute"] = show_df["Absolute"].round(3)
        st.dataframe(show_df, use_container_width=True)

def render_chi_square_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    categorical_cols = [c for c in cols_for_stats if not detect_is_numeric(df[c])[0]]

    if len(categorical_cols) < 2:
        st.warning("At least two categorical variables are required.")
        return

    c1, c2 = st.columns(2)
    with c1:
        col_a = st.selectbox("Categorical Variable A", categorical_cols, key="chi_a")
    with c2:
        col_b = st.selectbox(
            "Categorical Variable B",
            categorical_cols,
            index=1 if len(categorical_cols) > 1 else 0,
            key="chi_b"
        )

    if col_a == col_b:
        st.info("Choose two different categorical variables.")
        return

    temp = pd.DataFrame({
        col_a: df[col_a].fillna("(missing)").astype(str),
        col_b: df[col_b].fillna("(missing)").astype(str)
    })

    ctab = pd.crosstab(temp[col_a], temp[col_b])

    if ctab.empty:
        st.warning("No valid contingency data.")
        return

    chi2, p_value, dof, expected = stats.chi2_contingency(ctab)

    n = ctab.to_numpy().sum()
    min_dim = min(ctab.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else np.nan
    low_expected = int((expected < 5).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chi-square", f"{chi2:.3f}")
    m2.metric("p-value", f"{p_value:.4g}")
    m3.metric("Degrees of freedom", int(dof))
    m4.metric("Cramér's V", f"{cramers_v:.3f}" if pd.notna(cramers_v) else "-")

    st.markdown("#### Contingency Table")
    st.dataframe(ctab, use_container_width=True)

    st.markdown("#### Expected Frequencies")
    expected_df = pd.DataFrame(expected, index=ctab.index, columns=ctab.columns)
    st.dataframe(expected_df.round(3), use_container_width=True)

    with st.expander("Interpretation", expanded=True):
        if p_value < 0.05:
            st.write(
                f"There is a statistically significant association between **{col_a}** and **{col_b}** "
                f"(Chi-square = {chi2:.3f}, p = {p_value:.4g})."
            )
        else:
            st.write(
                f"No statistically significant association was detected between **{col_a}** and **{col_b}** "
                f"(Chi-square = {chi2:.3f}, p = {p_value:.4g})."
            )

        if pd.notna(cramers_v):
            if cramers_v < 0.1:
                strength = "very weak"
            elif cramers_v < 0.3:
                strength = "weak"
            elif cramers_v < 0.5:
                strength = "moderate"
            else:
                strength = "strong"

            st.write(f"Association strength based on Cramér's V: **{strength}**.")

        if low_expected > 0:
            st.write(
                f"There are **{low_expected}** cells with expected frequency below 5, "
                "so the chi-square approximation may be less reliable."
            )
        else:
            st.write("Expected frequencies look acceptable for the chi-square approximation.")

def render_group_mean_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    numeric_cols = [c for c in cols_for_stats if detect_is_numeric(df[c])[0]]
    categorical_cols = [c for c in cols_for_stats if not detect_is_numeric(df[c])[0]]

    if not numeric_cols:
        st.warning("At least one numeric variable is required.")
        return

    if not categorical_cols:
        st.warning("At least one categorical variable is required.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        num_col = st.selectbox("Numeric Variable", numeric_cols, key="group_num")
    with c2:
        cat_col = st.selectbox("Grouping Variable", categorical_cols, key="group_cat")
    with c3:
        test_type = st.selectbox("Test", ["Auto", "t-test", "ANOVA"], key="group_test_type")

    temp = pd.DataFrame({
        num_col: pd.to_numeric(df[num_col], errors="coerce"),
        cat_col: df[cat_col].fillna("(missing)").astype(str)
    }).dropna(subset=[num_col])

    if temp.empty:
        st.warning("No valid observations found.")
        return

    n_groups = temp[cat_col].nunique()

    st.caption(f"Valid observations used: {len(temp)} | Groups detected: {n_groups}")

    group_summary = (
        temp.groupby(cat_col)[num_col]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )

    st.markdown("#### Grouped Descriptive Statistics")
    st.dataframe(group_summary, use_container_width=True)

    fig = px.box(
        temp,
        x=cat_col,
        y=num_col,
        title=f"{num_col} by {cat_col}"
    )
    st.plotly_chart(fig, use_container_width=True)

    grouped_values = [g[num_col].values for _, g in temp.groupby(cat_col)]

    # Auto mode
    if test_type == "Auto":
        if n_groups == 2:
            test_type = "t-test"
        elif n_groups > 2:
            test_type = "ANOVA"
        else:
            st.info("At least two groups are required.")
            return

    if test_type == "t-test":
        if n_groups != 2:
            st.warning("t-test requires exactly 2 groups.")
            return

        group_names = list(temp[cat_col].unique())
        g1 = temp[temp[cat_col] == group_names[0]][num_col]
        g2 = temp[temp[cat_col] == group_names[1]][num_col]

        if len(g1) < 2 or len(g2) < 2:
            st.warning("Each group must contain at least 2 valid values for t-test.")
            return

        t_stat, p_value = stats.ttest_ind(g1, g2, equal_var=False)

        m1, m2, m3 = st.columns(3)
        m1.metric("Test", "Welch t-test")
        m2.metric("t statistic", f"{t_stat:.3f}")
        m3.metric("p-value", f"{p_value:.4g}")

        with st.expander("Interpretation", expanded=True):
            st.write(
                f"The comparison of **{num_col}** across the two **{cat_col}** groups "
                f"returned t = {t_stat:.3f}, p = {p_value:.4g}."
            )
            if p_value < 0.05:
                st.write("The difference in group means is statistically significant.")
            else:
                st.write("No statistically significant difference in group means was detected.")

    elif test_type == "ANOVA":
        if n_groups < 2:
            st.warning("ANOVA requires at least 2 groups.")
            return

        if not all(len(g) > 1 for g in grouped_values):
            st.warning("Each group should contain at least 2 valid values for ANOVA.")
            return

        f_stat, p_value = stats.f_oneway(*grouped_values)

        m1, m2, m3 = st.columns(3)
        m1.metric("Test", "One-way ANOVA")
        m2.metric("F statistic", f"{f_stat:.3f}")
        m3.metric("p-value", f"{p_value:.4g}")

        with st.expander("Interpretation", expanded=True):
            st.write(
                f"The comparison of **{num_col}** across **{cat_col}** groups "
                f"returned F = {f_stat:.3f}, p = {p_value:.4g}."
            )
            if p_value < 0.05:
                st.write("There is evidence that at least one group mean differs from the others.")
            else:
                st.write("No statistically significant group mean differences were detected.")

def render_statistical_tests(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown("### Statistical Tests")

    test_type = st.selectbox(
        "Test family",
        [
            "Correlation Test",
            "Chi-square Test",
            "Group Mean Comparison"
        ],
        key="test_family"
    )

    if test_type == "Correlation Test":
        render_correlation_test_ui(df, cols_for_stats)
    elif test_type == "Chi-square Test":
        render_chi_square_test_ui(df, cols_for_stats)
    elif test_type == "Group Mean Comparison":
        render_group_mean_test_ui(df, cols_for_stats)

def render_correlation_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    numeric_cols = [c for c in cols_for_stats if detect_is_numeric(df[c])[0]]

    if len(numeric_cols) < 2:
        st.warning("At least two numeric variables are required.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        col_a = st.selectbox("Variable A", numeric_cols, key="test_corr_a")
    with c2:
        col_b = st.selectbox("Variable B", numeric_cols, key="test_corr_b")
    with c3:
        method = st.selectbox("Method", ["Pearson", "Spearman"], key="test_corr_method")

    if col_a == col_b:
        st.info("Choose two different numeric variables.")
        return

    temp = pd.DataFrame({
        col_a: pd.to_numeric(df[col_a], errors="coerce"),
        col_b: pd.to_numeric(df[col_b], errors="coerce")
    }).dropna()

    if len(temp) < 3:
        st.warning("Not enough valid observations.")
        return

    if method == "Pearson":
        stat, pval = stats.pearsonr(temp[col_a], temp[col_b])
    else:
        stat, pval = stats.spearmanr(temp[col_a], temp[col_b])

    result_df = pd.DataFrame({
        "Statistic": [stat],
        "p-value": [pval],
        "N": [len(temp)]
    })
    st.dataframe(result_df, use_container_width=True)

    conclusion = (
        "There is evidence of association."
        if pval < 0.05 else
        "No statistically significant association was detected."
    )
    st.write(conclusion)

def render_correlation_interpretation(corr: pd.DataFrame):
    st.markdown("#### Correlation Interpretation")

    if corr.empty or len(corr.columns) < 2:
        st.info("Not enough numeric variables to interpret correlations.")
        return

    pairs = []
    cols = corr.columns.tolist()

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.loc[cols[i], cols[j]]
            if pd.notna(value):
                pairs.append({
                    "Variable 1": cols[i],
                    "Variable 2": cols[j],
                    "Correlation": value,
                    "Absolute": abs(value)
                })

    if not pairs:
        st.info("No valid correlations were found.")
        return

    pairs_df = pd.DataFrame(pairs).sort_values("Absolute", ascending=False)
    top = pairs_df.iloc[0]

    if top["Absolute"] < 0.2:
        st.info("No clearly relevant linear correlations were detected among the selected numeric variables.")
        return

    direction = "positive" if top["Correlation"] > 0 else "negative"

    st.write(
        f"The strongest observed linear relationship is between **{top['Variable 1']}** and "
        f"**{top['Variable 2']}**, with a **{direction}** correlation of **{top['Correlation']:.3f}**."
    )

    with st.expander("Correlation Ranking"):
        show_df = pairs_df.copy()
        show_df["Correlation"] = show_df["Correlation"].round(3)
        show_df["Absolute"] = show_df["Absolute"].round(3)
        st.dataframe(show_df, use_container_width=True)

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

def render_colored_scatter(temp: pd.DataFrame, col_x: str, col_y: str, col_z: str):

    fig = px.scatter(
        temp,
        x=col_x,
        y=col_y,
        color=col_z,
        title=f"{col_x} vs {col_y} grouped by {col_z}"
    )
    st.plotly_chart(fig, use_container_width=True)

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

def _build_three_meta_df(
    col1: str, col2: str, col3: str,
    s1: pd.Series, s2: pd.Series, s3: pd.Series,
    t1: str, t2: str, t3: str,
    auto_mode: str, final_mode: str,
    total_rows: int, valid_rows: int, removed_rows: int, valid_pct: float
) -> pd.DataFrame:
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
            # fallback for manual override when auto types do not match requested mode
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
            st.markdown(
                f"""
                <div class="tv-warning">
                    A dedicated three-numeric analysis view is not connected yet.  
                    Current selection: <b>{col1}</b>, <b>{col2}</b>, <b>{col3}</b>.  
                    Recommended extension: 3D scatter, pairwise colored scatter, correlation matrix, or regression-based view.
                </div>
                """,
                unsafe_allow_html=True
            )

        elif final_mode == "Numeric + Categorical + Categorical":
            st.markdown(
                f"""
                <div class="tv-warning">
                    A dedicated numeric-by-two-categorical analysis view is not connected yet.  
                    Recommended extension: grouped boxplots, faceted histograms, grouped means, or two-way ANOVA style summaries.
                </div>
                """,
                unsafe_allow_html=True
            )

        elif final_mode == "Categorical + Categorical + Categorical":
            st.markdown(
                f"""
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
                        Three numeric variables are suitable for advanced multivariate exploration, but need a dedicated visualization layer.
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
                "This configuration is naturally multivariate and can reveal joint numeric structure, but requires a dedicated 3-variable numeric visualization."
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

        steps = []

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

def render_top_correlation_pairs(corr: pd.DataFrame):
    pairs = []
    cols = corr.columns.tolist()

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.loc[cols[i], cols[j]]
            if pd.notna(value):
                pairs.append({
                    "Variable 1": cols[i],
                    "Variable 2": cols[j],
                    "Correlation": round(value, 3),
                    "Absolute correlation": round(abs(value), 3)
                })

    if not pairs:
        st.info("No valid pairwise correlations found.")
        return

    pairs_df = pd.DataFrame(pairs).sort_values("Absolute correlation", ascending=False)
    st.dataframe(pairs_df, use_container_width=True)

def build_multivariate_interpretation(target: str, predictors: list[str], model) -> str:
    significant = []
    for var, pval in model.pvalues.items():
        if var == "const":
            continue
        if pval < 0.05:
            significant.append(var)

    if significant:
        sig_text = ", ".join(significant)
        sig_sentence = f"The predictors showing statistically significant associations with {target} are: {sig_text}."
    else:
        sig_sentence = f"No predictor reached conventional statistical significance for {target}."

    return (
        f"A multiple linear regression model was fitted with {target} as the outcome and "
        f"{', '.join(predictors)} as predictors. The model explains approximately "
        f"{model.rsquared:.1%} of the variance in {target} (adjusted R² = {model.rsquared_adj:.1%}). "
        f"{sig_sentence}"
    )

def render_multivariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown("### Multivariate Analysis")

    numeric_cols = []
    for c in cols_for_stats:
        is_num, _ = detect_is_numeric(df[c])
        if is_num:
            numeric_cols.append(c)

    if len(numeric_cols) < 2:
        st.warning("At least two numeric variables are required.")
        return

    c1, c2 = st.columns([1, 2])

    with c1:
        target = st.selectbox("Target variable", numeric_cols, key="multi_target")

    with c2:
        predictors = st.multiselect(
            "Predictor variables",
            [c for c in numeric_cols if c != target],
            default=[c for c in numeric_cols if c != target][:3],
            key="multi_predictors"
        )

    if not predictors:
        st.info("Choose at least one predictor.")
        return

    temp = df[[target] + predictors].copy()
    for c in [target] + predictors:
        temp[c] = pd.to_numeric(temp[c], errors="coerce")

    n_before = len(temp)
    temp = temp.dropna()
    n_after = len(temp)

    st.caption(f"Valid observations used: {n_after} / {n_before}")

    if len(temp) < 5:
        st.warning("Not enough valid rows for multivariate analysis.")
        return

    st.markdown("#### Correlation Matrix")
    corr = temp.corr(numeric_only=True)
    st.dataframe(corr, use_container_width=True)
    render_correlation_interpretation(corr)

    X = sm.add_constant(temp[predictors])
    y = temp[target]
    model = sm.OLS(y, X).fit()

    st.markdown("#### Model Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("R²", f"{model.rsquared:.3f}")
    m2.metric("Adjusted R²", f"{model.rsquared_adj:.3f}")
    m3.metric("Model p-value", f"{model.f_pvalue:.4g}" if pd.notna(model.f_pvalue) else "-")

    coef_df = pd.DataFrame({
        "Variable": model.params.index,
        "Coefficient": model.params.values,
        "p-value": model.pvalues.values,
        "CI Low": model.conf_int()[0].values,
        "CI High": model.conf_int()[1].values
    })

    st.markdown("#### Coefficients")
    st.dataframe(coef_df, use_container_width=True)

    with st.expander("Interpretation", expanded=True):
        st.write(build_multivariate_interpretation(target, predictors, model))

    residual_df = pd.DataFrame({
        "Fitted": model.fittedvalues,
        "Residuals": model.resid
    })

    st.markdown("#### Residual Plot")
    fig = px.scatter(
        residual_df,
        x="Fitted",
        y="Residuals",
        title=f"Residual Plot for {target}"
    )
    fig.add_hline(y=0)
    st.plotly_chart(fig, use_container_width=True)

def render_histogram(series, title, col_name, bins=10):
    fig, ax = plt.subplots()
    ax.hist(series, bins=bins)
    ax.set_title(title)
    st.pyplot(fig)

def render_analysis_panel():
    st.markdown("## Analysis")

    current_df = st.session_state.df
    if current_df is None or current_df.empty:
        st.warning("The dataset is empty.")
        return

    cols_for_stats = [c for c in current_df.columns if c != COMMENT_COL]
    if not cols_for_stats:
        st.warning("There are no analyzable columns.")
        return

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview",
        "Univariate Analysis",
        "Bivariate Analysis",
        "Three-Variable Analysis",
        "Multivariate Analysis",
        "Statistical Tests"
    ])

    with tab1:
        render_global_summary(current_df, cols_for_stats)

    with tab2:
        render_univariate_analysis(current_df, cols_for_stats)

    with tab3:
        render_bivariate_analysis(current_df, cols_for_stats)

    with tab4:
        render_three_variable_analysis(current_df, cols_for_stats)

    with tab5:
        render_multivariate_analysis(current_df, cols_for_stats)

    with tab6:
        render_statistical_tests(current_df, cols_for_stats)

def render_correlation_interpretation(corr: pd.DataFrame):
    st.markdown("##### Interpretación de correlaciones")

    if corr.empty or len(corr.columns) < 2:
        st.info("No hay suficientes variables numéricas para interpretar correlaciones.")
        return

    corr_pairs = []

    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a = cols[i]
            b = cols[j]
            val = corr.loc[a, b]

            if pd.notna(val):
                corr_pairs.append({
                    "var_1": a,
                    "var_2": b,
                    "corr": val,
                    "abs_corr": abs(val)
                })

    if not corr_pairs:
        st.info("No se pudieron calcular correlaciones válidas.")
        return

    pairs_df = pd.DataFrame(corr_pairs).sort_values("abs_corr", ascending=False)

    top_pair = pairs_df.iloc[0]
    top_val = top_pair["corr"]
    top_abs = top_pair["abs_corr"]

    def corr_strength(v: float) -> str:
        v = abs(v)
        if v >= 0.8:
            return "muy fuerte"
        elif v >= 0.6:
            return "fuerte"
        elif v >= 0.4:
            return "moderada"
        elif v >= 0.2:
            return "débil"
        return "muy débil"

    def corr_direction(v: float) -> str:
        return "positiva" if v > 0 else "negativa"

    strong_pairs = pairs_df[pairs_df["abs_corr"] >= 0.6]
    moderate_pairs = pairs_df[(pairs_df["abs_corr"] >= 0.4) & (pairs_df["abs_corr"] < 0.6)]

    if top_abs < 0.2:
        st.info("No hay variables claramente correlacionadas. Todas las correlaciones son muy débiles.")
        return

    st.write(
        f"**Las variables más correlacionadas son** "
        f"`{top_pair['var_1']}` y `{top_pair['var_2']}` "
        f"con una correlación **{corr_direction(top_val)} {corr_strength(top_val)}** "
        f"de **{top_val:.3f}**."
    )

    if not strong_pairs.empty:
        st.write(f"Se detectaron **{len(strong_pairs)}** relaciones fuertes o muy fuertes.")
    elif not moderate_pairs.empty:
        st.write(f"No hay relaciones fuertes, pero sí **{len(moderate_pairs)}** relaciones moderadas.")
    else:
        st.write("No se detectaron relaciones moderadas o fuertes; en general las correlaciones son bajas.")

    with st.expander("Ver ranking de correlaciones"):
        ranking_df = pairs_df.copy()
        ranking_df["strength"] = ranking_df["corr"].apply(corr_strength)
        ranking_df["direction"] = ranking_df["corr"].apply(corr_direction)
        ranking_df["corr"] = ranking_df["corr"].round(3)

        ranking_df = ranking_df.rename(columns={
            "var_1": "Variable 1",
            "var_2": "Variable 2",
            "corr": "Correlation",
            "abs_corr": "Absolute correlation",
            "strength": "Strength",
            "direction": "Direction"
        })

        st.dataframe(ranking_df, use_container_width=True)

def render_scatter_with_line(x, y, x_label: str, y_label: str):


    plot_df = pd.DataFrame({"x": x, "y": y})
    fig = px.scatter(
        plot_df,
        x="x",
        y="y",
        trendline="ols",
        labels={"x": x_label, "y": y_label},
        title=f"{x_label} vs {y_label}"
    )
    st.plotly_chart(fig, use_container_width=True)

def _quality_label(score: int) -> tuple[str, str]:
    if score >= 85:
        return "Excellent", "#16a34a"
    if score >= 70:
        return "Good", "#2563eb"
    if score >= 50:
        return "Moderate", "#f59e0b"
    return "Needs attention", "#dc2626"

def _compute_quality_score(summary_df: pd.DataFrame) -> int:
    if summary_df.empty:
        return 0

    avg_missing = summary_df["Missing %"].mean()
    max_missing = summary_df["Missing %"].max()

    cat_df = summary_df[summary_df["Detected type"] == "Categorical"]
    high_card = int((cat_df["Unique"] > 20).sum())

    penalty = 0
    penalty += min(avg_missing * 1.2, 35)
    penalty += min(max_missing * 0.25, 20)
    penalty += min(high_card * 4, 20)

    score = int(round(100 - penalty))
    return max(0, min(100, score))

def _correlation_strength_label(v: float) -> str:
    a = abs(v)
    if a >= 0.80:
        return "Very strong"
    if a >= 0.60:
        return "Strong"
    if a >= 0.40:
        return "Moderate"
    if a >= 0.20:
        return "Weak"
    return "Very weak"

def _extract_top_correlations(corr: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if corr.empty or corr.shape[0] < 2:
        return pd.DataFrame(columns=[
            "Variable A", "Variable B", "Correlation", "Direction", "Strength"
        ])

    rows = []
    cols = corr.columns.tolist()

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.notna(v):
                rows.append({
                    "Variable A": cols[i],
                    "Variable B": cols[j],
                    "Correlation": round(float(v), 3),
                    "Direction": "Positive" if v > 0 else "Negative",
                    "Strength": _correlation_strength_label(float(v)),
                    "_abs": abs(float(v)),
                })

    if not rows:
        return pd.DataFrame(columns=[
            "Variable A", "Variable B", "Correlation", "Direction", "Strength"
        ])

    out = (
        pd.DataFrame(rows)
        .sort_values("_abs", ascending=False)
        .head(top_n)
        .drop(columns="_abs")
        .reset_index(drop=True)
    )
    return out

def _build_suggested_tests(summary_df: pd.DataFrame) -> pd.DataFrame:
    numeric_count = int((summary_df["Detected type"] == "Numeric").sum())
    categorical_count = int((summary_df["Detected type"] == "Categorical").sum())

    suggestions = []

    if numeric_count >= 1:
        suggestions.append({
            "Scenario": "Single numeric variable",
            "Suggested test / method": "Descriptive statistics, histogram, boxplot, normality assessment",
            "Why": "Understand distribution, spread, skewness, and outliers"
        })

    if numeric_count >= 2:
        suggestions.append({
            "Scenario": "Two numeric variables",
            "Suggested test / method": "Pearson / Spearman correlation, scatter plot, linear trend line",
            "Why": "Measure linear or monotonic association"
        })

    if numeric_count >= 1 and categorical_count >= 1:
        suggestions.append({
            "Scenario": "Numeric vs categorical",
            "Suggested test / method": "Group comparison, t-test, ANOVA, boxplot by category",
            "Why": "Check whether group membership affects the numeric outcome"
        })

    if categorical_count >= 2:
        suggestions.append({
            "Scenario": "Categorical vs categorical",
            "Suggested test / method": "Contingency table, chi-square test, stacked bar chart",
            "Why": "Evaluate dependency between categories"
        })

    if numeric_count >= 3:
        suggestions.append({
            "Scenario": "Multiple numeric variables",
            "Suggested test / method": "Multicollinearity check, PCA, clustering, regression",
            "Why": "Explore higher-dimensional structure and redundancy"
        })

    return pd.DataFrame(suggestions)

def _to_csv_download_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def _render_kpi_card(title: str, value: str, subtitle: str = "", accent: str = "#2563eb"):
    st.markdown(
        f"""
        <div class="gs-card kpi-card">
            <div class="kpi-top-line" style="background:{accent};"></div>
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_global_summary(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown("""
    <style>
    .gs-header {
        padding: 1.2rem 1.25rem 1rem 1.25rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 55%, #eef6ff 100%);
        border: 1px solid #e5e7eb;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }
    .gs-title {
        font-size: 1.7rem;
        font-weight: 750;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .gs-subtitle {
        color: #64748b;
        font-size: 0.96rem;
        line-height: 1.5;
    }
    .gs-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
    }
    .kpi-card {
        min-height: 120px;
        position: relative;
        overflow: hidden;
    }
    .kpi-top-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.8rem;
    }
    .kpi-title {
        font-size: 0.86rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 0.35rem;
    }
    .kpi-value {
        font-size: 1.7rem;
        line-height: 1.15;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }
    .kpi-subtitle {
        font-size: 0.82rem;
        color: #64748b;
    }
    .panel-title {
        font-size: 1.02rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.5rem;
    }
    .panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.8rem;
    }
    .insight-box {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.6rem;
        color: #0f172a;
        font-size: 0.94rem;
    }
    .success-box {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.6rem;
        color: #0f172a;
        font-size: 0.94rem;
    }
    .warning-box {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.6rem;
        color: #0f172a;
        font-size: 0.94rem;
    }
    .danger-box {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.6rem;
        color: #0f172a;
        font-size: 0.94rem;
    }
    .badge {
        display: inline-block;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="gs-header">
        <div class="gs-title">Dataset overview</div>
        <div class="gs-subtitle">
            Executive summary of structure, completeness, variable types, missingness risk,
            and quantitative relationships across the selected dataset columns.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df is None or df.empty or not cols_for_stats:
        st.warning("No valid data is available to compute the global summary.")
        return

    valid_cols = [c for c in cols_for_stats if c in df.columns]
    if not valid_cols:
        st.warning("None of the selected columns exist in the dataframe.")
        return

    subset_df = df[valid_cols].copy()

    total_rows = len(subset_df)
    total_cols = len(valid_cols)
    total_cells = total_rows * total_cols
    total_missing = int(subset_df.isna().sum().sum())
    completeness = round(100 - _safe_pct(total_missing, total_cells), 2)

    summary_rows = []
    numeric_cols_detected = []

    for c in valid_cols:
        s = subset_df[c]
        is_num, s_num = detect_is_numeric(s)

        if is_num:
            numeric_cols_detected.append(c)

        missing = int(s_num.isna().sum()) if is_num else int(s.isna().sum())
        non_null = int(s.notna().sum())
        unique = int(s.nunique(dropna=True))
        missing_pct = _safe_pct(missing, len(subset_df))

        summary_rows.append({
            "Column": c,
            "Detected type": "Numeric" if is_num else "Categorical",
            "Non-null": non_null,
            "Missing": missing,
            "Missing %": missing_pct,
            "Unique": unique,
        })

    summary_df = pd.DataFrame(summary_rows)
    numeric_count = int((summary_df["Detected type"] == "Numeric").sum())
    categorical_count = int((summary_df["Detected type"] == "Categorical").sum())

    quality_score = _compute_quality_score(summary_df)
    quality_text, quality_color = _quality_label(quality_score)

    high_missing = summary_df[summary_df["Missing %"] >= 30].copy()
    moderate_missing = summary_df[(summary_df["Missing %"] >= 10) & (summary_df["Missing %"] < 30)].copy()
    high_cardinality = summary_df[
        (summary_df["Detected type"] == "Categorical") & (summary_df["Unique"] > 20)
    ].copy()

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_kpi_card("Rows", f"{total_rows:,}", "Observations", "#2563eb")
    with k2:
        _render_kpi_card("Columns", f"{total_cols:,}", "Selected variables", "#0ea5e9")
    with k3:
        _render_kpi_card("Missing cells", f"{total_missing:,}", "Null / empty values", "#f59e0b")
    with k4:
        _render_kpi_card("Completeness", f"{completeness}%", "Coverage across cells", "#16a34a")
    with k5:
        _render_kpi_card("Quality score", f"{quality_score}/100", quality_text, quality_color)

    st.markdown("")

    tabs = st.tabs([
        "Overview",
        "Missingness",
        "Correlations",
        "Insights",
        "Suggested tests"
    ])

    # =====================================================
    # TAB 1 - OVERVIEW
    # =====================================================
    with tabs[0]:
        left, right = st.columns([1.8, 1])

        with left:
            st.markdown('<div class="panel-title">Column summary</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-subtitle">Detected variable type, completeness, and cardinality.</div>', unsafe_allow_html=True)

            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Column": st.column_config.TextColumn("Column", width="medium"),
                    "Detected type": st.column_config.TextColumn("Detected type", width="small"),
                    "Non-null": st.column_config.NumberColumn("Non-null", format="%d"),
                    "Missing": st.column_config.NumberColumn("Missing", format="%d"),
                    "Missing %": st.column_config.ProgressColumn(
                        "Missing %",
                        min_value=0.0,
                        max_value=100.0,
                        format="%.2f%%"
                    ),
                    "Unique": st.column_config.NumberColumn("Unique", format="%d"),
                }
            )

            st.download_button(
                "Download summary CSV",
                data=_to_csv_download_bytes(summary_df),
                file_name="dataset_summary.csv",
                mime="text/csv",
                use_container_width=False
            )

        with right:
            st.markdown('<div class="panel-title">Schema balance</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-subtitle">Detected variable-type distribution.</div>', unsafe_allow_html=True)

            schema_df = pd.DataFrame({
                "Type": ["Numeric", "Categorical"],
                "Count": [numeric_count, categorical_count]
            })

            fig_schema = px.pie(
                schema_df,
                names="Type",
                values="Count",
                hole=0.6
            )
            fig_schema.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_schema, use_container_width=True)

            avg_missing = round(summary_df["Missing %"].mean(), 2)
            max_missing = round(summary_df["Missing %"].max(), 2)
            avg_unique = round(summary_df["Unique"].mean(), 2)

            st.markdown(
                f"""
                <div class="gs-card">
                    <div class="panel-title">Quick profile</div>
                    <div class="panel-subtitle">
                        Average missing per column: <b>{avg_missing}%</b><br>
                        Maximum missing in one column: <b>{max_missing}%</b><br>
                        Average unique values: <b>{avg_unique}</b><br>
                        Numeric columns: <b>{numeric_count}</b><br>
                        Categorical columns: <b>{categorical_count}</b>
                    </div>
                    <div class="badge" style="background:{quality_color}18;color:{quality_color};border:1px solid {quality_color}40;">
                        {quality_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # =====================================================
    # TAB 2 - MISSINGNESS
    # =====================================================
    with tabs[1]:
        left, right = st.columns([1.6, 1])

        with left:
            st.markdown('<div class="panel-title">Missingness by column</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-subtitle">Ranking of variables by missing-value percentage.</div>', unsafe_allow_html=True)

            miss_plot_df = summary_df.sort_values("Missing %", ascending=False)

            fig_missing = px.bar(
                miss_plot_df,
                x="Missing %",
                y="Column",
                orientation="h",
                text="Missing %"
            )
            fig_missing.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            fig_missing.update_layout(
                height=max(320, 42 * len(miss_plot_df)),
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Missing percentage",
                yaxis_title=""
            )
            st.plotly_chart(fig_missing, use_container_width=True)

        with right:
            st.markdown('<div class="panel-title">Data quality risks</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-subtitle">Potential structural issues worth checking before analysis.</div>', unsafe_allow_html=True)

            if high_missing.empty and moderate_missing.empty and high_cardinality.empty:
                st.markdown(
                    """
                    <div class="success-box">
                        No major structural risks were detected from missingness or cardinality.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                if not high_missing.empty:
                    st.markdown(
                        f"""
                        <div class="danger-box">
                            <b>High missingness (≥ 30%)</b><br>
                            {", ".join(high_missing["Column"].tolist())}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                if not moderate_missing.empty:
                    st.markdown(
                        f"""
                        <div class="warning-box">
                            <b>Moderate missingness (10%–29.99%)</b><br>
                            {", ".join(moderate_missing["Column"].tolist())}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                if not high_cardinality.empty:
                    st.markdown(
                        f"""
                        <div class="insight-box">
                            <b>High-cardinality categorical variables</b><br>
                            {", ".join(high_cardinality["Column"].tolist())}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown('<div class="panel-title">Uniqueness profile</div>', unsafe_allow_html=True)

            uniq_plot_df = summary_df.sort_values("Unique", ascending=False).head(12)

            fig_unique = px.bar(
                uniq_plot_df,
                x="Column",
                y="Unique",
                text="Unique"
            )
            fig_unique.update_traces(textposition="outside")
            fig_unique.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="",
                yaxis_title="Distinct values"
            )
            st.plotly_chart(fig_unique, use_container_width=True)

    # =====================================================
    # TAB 3 - CORRELATIONS
    # =====================================================
    with tabs[2]:
        if len(numeric_cols_detected) >= 2:
            numeric_df = subset_df[numeric_cols_detected].apply(pd.to_numeric, errors="coerce")
            corr = numeric_df.corr(numeric_only=True)

            st.markdown('<div class="panel-title">Correlation matrix</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-subtitle">Linear relationships among detected numeric variables.</div>', unsafe_allow_html=True)

            fig_corr = go.Figure(
                data=go.Heatmap(
                    z=corr.values,
                    x=corr.columns,
                    y=corr.index,
                    zmin=-1,
                    zmax=1,
                    text=np.round(corr.values, 2),
                    texttemplate="%{text}",
                    hovertemplate="X: %{x}<br>Y: %{y}<br>Correlation: %{z:.3f}<extra></extra>"
                )
            )
            fig_corr.update_layout(
                height=560,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="",
                yaxis_title=""
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            c1, c2 = st.columns([1.2, 1])

            with c1:
                st.markdown('<div class="panel-title">Top correlations</div>', unsafe_allow_html=True)
                top_corr_df = _extract_top_correlations(corr, top_n=10)

                if top_corr_df.empty:
                    st.info("No valid pairwise correlations were detected.")
                else:
                    st.dataframe(top_corr_df, use_container_width=True, hide_index=True)

            with c2:
                st.markdown('<div class="panel-title">Interpretation</div>', unsafe_allow_html=True)

                top_corr_df = _extract_top_correlations(corr, top_n=10)

                if top_corr_df.empty:
                    st.markdown(
                        """
                        <div class="warning-box">
                            Correlations could not be interpreted because there are not enough valid numeric pairs.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    strongest = top_corr_df.iloc[0]
                    corr_val = strongest["Correlation"]
                    strength = strongest["Strength"]
                    direction = strongest["Direction"].lower()

                    st.markdown(
                        f"""
                        <div class="insight-box">
                            <b>Strongest detected relationship</b><br>
                            {strongest["Variable A"]} ↔ {strongest["Variable B"]}<br>
                            Correlation = <b>{corr_val}</b> ({strength.lower()}, {direction})
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if abs(corr_val) >= 0.80:
                        st.markdown(
                            """
                            <div class="danger-box">
                                Very strong correlation detected. If these variables are used together in predictive models,
                                consider checking redundancy or multicollinearity.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    elif abs(corr_val) >= 0.40:
                        st.markdown(
                            """
                            <div class="warning-box">
                                Moderate-to-strong relationships exist. These variables are good candidates for deeper feature analysis.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            """
                            <div class="success-box">
                                No strong linear dependency dominates the numeric space. Relationships may be weak or non-linear.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

            if "render_correlation_interpretation" in globals():
                render_correlation_interpretation(corr)

        else:
            st.info("At least two numeric columns are required to compute correlations.")

    # =====================================================
    # TAB 4 - INSIGHTS
    # =====================================================
    with tabs[3]:
        st.markdown('<div class="panel-title">Automatic interpretation</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-subtitle">System-generated summary of dataset quality and analysis readiness.</div>', unsafe_allow_html=True)

        insights = []

        if completeness >= 95:
            insights.append("The dataset is highly complete and appears well-prepared for downstream analysis.")
        elif completeness >= 85:
            insights.append("The dataset is reasonably complete, though selected columns may need preprocessing.")
        else:
            insights.append("The dataset has notable incompleteness, so missing-value treatment will strongly affect results.")

        if numeric_count == 0:
            insights.append("No numeric variables were detected, so correlation-based statistical analysis is not available.")
        elif numeric_count == 1:
            insights.append("Only one numeric variable was detected, which limits pairwise quantitative analysis.")
        else:
            insights.append(f"{numeric_count} numeric variables were detected, enabling correlation and multi-variable exploration.")

        if categorical_count > 0:
            insights.append(f"{categorical_count} categorical variables were detected, making segmentation and group comparison possible.")

        if not high_missing.empty:
            insights.append(
                "Columns with high missingness may require imputation, exclusion, or rule-based handling: "
                + ", ".join(high_missing["Column"].tolist()) + "."
            )

        if not high_cardinality.empty:
            insights.append(
                "Some categorical variables have high cardinality, which may complicate encoding, plotting, and aggregation: "
                + ", ".join(high_cardinality["Column"].tolist()) + "."
            )

        if len(numeric_cols_detected) >= 2:
            numeric_df = subset_df[numeric_cols_detected].apply(pd.to_numeric, errors="coerce")
            corr = numeric_df.corr(numeric_only=True)
            top_corr_df = _extract_top_correlations(corr, top_n=5)

            if not top_corr_df.empty:
                strongest = top_corr_df.iloc[0]
                v = strongest["Correlation"]

                if abs(v) >= 0.70:
                    insights.append(
                        f"The strongest linear relationship is between {strongest['Variable A']} and {strongest['Variable B']} ({v}). This may reflect redundancy, dependency, or a meaningful predictive signal."
                    )
                elif abs(v) >= 0.40:
                    insights.append(
                        f"A moderate relationship was detected between {strongest['Variable A']} and {strongest['Variable B']} ({v}), which may be useful for feature analysis."
                    )
                else:
                    insights.append(
                        "No strong linear correlations were detected, suggesting either relative independence or more complex non-linear relationships."
                    )

        label, color = _quality_label(quality_score)
        st.markdown(
            f"""
            <div class="gs-card" style="margin-bottom:0.8rem;">
                <div class="panel-title">Overall assessment</div>
                <div class="panel-subtitle">
                    Quality score: <b>{quality_score}/100</b>
                </div>
                <div class="badge" style="background:{color}18;color:{color};border:1px solid {color}40;">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        for txt in insights:
            st.markdown(f"""
            <div class="insight-box">{txt}</div>
            """, unsafe_allow_html=True)

    # =====================================================
    # TAB 5 - SUGGESTED TESTS
    # =====================================================
    with tabs[4]:
        st.markdown('<div class="panel-title">Suggested next analyses</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-subtitle">Recommended statistical directions based on the detected dataset structure.</div>', unsafe_allow_html=True)

        tests_df = _build_suggested_tests(summary_df)

        if tests_df.empty:
            st.info("No suggestions are available for the current dataset structure.")
        else:
            st.dataframe(tests_df, use_container_width=True, hide_index=True)

        st.markdown('<div class="panel-title">Recommended workflow</div>', unsafe_allow_html=True)

        workflow = []

        if not high_missing.empty:
            workflow.append("1. Address high-missingness columns before modeling or statistical testing.")
        else:
            workflow.append("1. Missingness risk is low, so you can proceed directly to exploratory analysis.")

        if not high_cardinality.empty:
            workflow.append("2. Consider grouping, encoding, or simplifying high-cardinality categorical variables.")
        else:
            workflow.append("2. Categorical cardinality appears manageable for standard visualization and grouping.")

        if len(numeric_cols_detected) >= 2:
            workflow.append("3. Review top numeric correlations and investigate whether they are meaningful or redundant.")
        else:
            workflow.append("3. Add or verify numeric fields if correlation analysis is expected.")

        if categorical_count >= 1 and numeric_count >= 1:
            workflow.append("4. Follow with group comparison analysis between categorical and numeric variables.")
        elif categorical_count >= 2:
            workflow.append("4. Follow with categorical association testing such as chi-square.")
        elif numeric_count >= 2:
            workflow.append("4. Follow with pairwise trends, regression, or dimensionality reduction.")

        for step in workflow:
            st.markdown(f"""
            <div class="success-box">{step}</div>
            """, unsafe_allow_html=True)











