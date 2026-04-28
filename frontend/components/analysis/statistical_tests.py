
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from scipy import stats
from services.stat_service import detect_is_numeric

from utils.ui_helpers import build_prediction_formula


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
