import pandas as pd
import streamlit as st
from services.stat_service import  detect_is_numeric

import numpy as np
import plotly.express as px
from scipy import stats
import statsmodels.api as sm
def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def render_numeric_categorical(
    sa: pd.Series,
    sb: pd.Series,
    col_a: str,
    col_b: str,
    a_is_num: bool,
):
    st.write("**Relationship type:** Numeric vs Categorical")

    if a_is_num:
        num_col = col_a
        cat_col = col_b
        temp = pd.DataFrame({
            num_col: pd.to_numeric(sa, errors="coerce"),
            cat_col: sb.fillna("(missing)").astype(str)
        })
    else:
        num_col = col_b
        cat_col = col_a
        temp = pd.DataFrame({
            num_col: pd.to_numeric(sb, errors="coerce"),
            cat_col: sa.fillna("(missing)").astype(str)
        })

    n_before = len(temp)
    temp = temp.dropna(subset=[num_col])
    n_after = len(temp)

    st.caption(f"Valid observations used: {n_after} / {n_before}")

    if temp.empty or temp[cat_col].nunique() < 2:
        st.warning("Not enough valid grouped data.")
        return

    group_summary = (
        temp.groupby(cat_col)[num_col]
        .agg(["count", "mean", "median", "min", "max", "std"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )

    grouped = [g[num_col].values for _, g in temp.groupby(cat_col)]
    anova_p = np.nan
    if len(grouped) >= 2 and all(len(g) > 1 for g in grouped):
        _, anova_p = stats.f_oneway(*grouped)

    m1, m2, m3 = st.columns(3)
    m1.metric("Groups", int(temp[cat_col].nunique()))
    m2.metric("N", n_after)
    m3.metric("ANOVA p-value", f"{anova_p:.4g}" if pd.notna(anova_p) else "-")

    with st.expander("Interpretation", expanded=True):
        st.write(build_numeric_categorical_interpretation(
            group_summary=group_summary,
            num_col=num_col,
            cat_col=cat_col,
            anova_p=anova_p
        ))

    st.markdown("#### Grouped Descriptive Statistics")
    st.dataframe(group_summary, use_container_width=True)

    st.markdown("#### Mean by Category")
    fig_bar = px.bar(
        group_summary,
        x=cat_col,
        y="mean",
        title=f"Mean of {num_col} by {cat_col}"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("#### Boxplot by Category")
    fig_box = px.box(
        temp,
        x=cat_col,
        y=num_col,
        title=f"{num_col} by {cat_col}"
    )
    st.plotly_chart(fig_box, use_container_width=True)

def build_numeric_categorical_interpretation(
    group_summary: pd.DataFrame,
    num_col: str,
    cat_col: str,
    anova_p: float
) -> str:
    top_row = group_summary.iloc[0]
    bottom_row = group_summary.iloc[-1]

    base = (
        f"The highest average {num_col} appears in {top_row[cat_col]} "
        f"(mean = {top_row['mean']:.3f}), while the lowest appears in {bottom_row[cat_col]} "
        f"(mean = {bottom_row['mean']:.3f}). "
    )

    if pd.notna(anova_p):
        if anova_p < 0.05:
            base += f"ANOVA suggests statistically significant mean differences across {cat_col} groups (p = {anova_p:.4g})."
        else:
            base += f"ANOVA does not suggest statistically significant mean differences across {cat_col} groups (p = {anova_p:.4g})."

    return base

def build_numeric_numeric_interpretation(
    col_a: str,
    col_b: str,
    pearson_r: float,
    pearson_p: float,
    slope: float,
    slope_ci_low: float,
    slope_ci_high: float,
    r_squared: float,
    n: int) -> str:
    abs_r = abs(pearson_r)

    # Strength
    if abs_r < 0.2:
        strength = "very weak"
    elif abs_r < 0.4:
        strength = "weak"
    elif abs_r < 0.6:
        strength = "moderate"
    elif abs_r < 0.8:
        strength = "strong"
    else:
        strength = "very strong"

    # Direction (handle r = 0 properly)
    if pearson_r > 0:
        direction = "positive"
    elif pearson_r < 0:
        direction = "negative"
    else:
        direction = "no"

    # Significance
    significance = (
        "statistically significant"
        if pearson_p < 0.05 else
        "not statistically significant"
    )

    # Confidence interval interpretation
    ci_text = (
        "The slope confidence interval includes 0, so the linear effect should be interpreted cautiously."
        if slope_ci_low <= 0 <= slope_ci_high else
        "The slope confidence interval does not include 0, which supports a non-zero linear trend."
    )

    # Special case when no relationship
    if direction == "no":
        relation_text = f"No linear relationship was observed between {col_a} and {col_b}"
    else:
        relation_text = f"A {strength} {direction} linear relationship was observed between {col_a} and {col_b}"

    return (
        f"{relation_text} "
        f"(Pearson r = {pearson_r:.3f}, p = {pearson_p:.4g}, n = {n}). "
        f"The fitted regression suggests that a one-unit increase in {col_a} is associated with an average "
        f"change of {slope:.3f} units in {col_b}. "
        f"The model explains approximately {r_squared:.1%} of the variance in {col_b}. "
        f"The result is {significance}. {ci_text}"
    )

def render_categorical_categorical(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    st.write("**Relationship type:** Categorical vs Categorical")

    temp = pd.DataFrame({
        col_a: sa.fillna("(missing)").astype(str),
        col_b: sb.fillna("(missing)").astype(str)
    })

    if temp.empty:
        st.warning("No valid data available.")
        return

    ctab = pd.crosstab(temp[col_a], temp[col_b])

    if ctab.empty:
        st.warning("No valid contingency data.")
        return

    row_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="index") * 100
    col_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="columns") * 100

    chi2, p_value, dof, expected = stats.chi2_contingency(ctab)

    n = ctab.to_numpy().sum()
    min_dim = min(ctab.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else np.nan
    low_expected = int((expected < 5).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chi-square", f"{chi2:.3f}")
    m2.metric("p-value", f"{p_value:.4g}")
    m3.metric("Cramér's V", f"{cramers_v:.3f}" if pd.notna(cramers_v) else "-")
    m4.metric("Low expected cells", low_expected)

    with st.expander("Interpretation", expanded=True):
        if p_value < 0.05:
            st.write(
                f"There is a statistically significant association between **{col_a}** and **{col_b}** "
                f"(p = {p_value:.4g})."
            )
        else:
            st.write(
                f"No statistically significant association was detected between **{col_a}** and **{col_b}** "
                f"(p = {p_value:.4g})."
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
            st.write("Expected frequencies look acceptable for chi-square.")

    st.markdown("#### Contingency Table")
    st.dataframe(ctab, use_container_width=True)

    st.markdown("#### Row Percentages")
    st.dataframe(row_pct.round(2), use_container_width=True)

    st.markdown("#### Column Percentages")
    st.dataframe(col_pct.round(2), use_container_width=True)

    st.markdown("#### Heatmap")
    fig = px.imshow(
        ctab,
        text_auto=True,
        aspect="auto",
        title=f"{col_a} vs {col_b}"
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Expected Frequencies"):
        expected_df = pd.DataFrame(expected, index=ctab.index, columns=ctab.columns)
        st.dataframe(expected_df.round(3), use_container_width=True)

def _build_bivariate_meta_df(
    col_a: str,
    col_b: str,
    a_dtype: str,
    b_dtype: str,
    a_detected: str,
    b_detected: str,
    valid_pairs: int,
    total_rows: int,
    pair_missing: int,
    valid_pct: float,
    final_mode: str
) -> pd.DataFrame:
    return pd.DataFrame([
        {"Property": "Variable A", "Value": col_a},
        {"Property": "Variable B", "Value": col_b},
        {"Property": "A original dtype", "Value": a_dtype},
        {"Property": "B original dtype", "Value": b_dtype},
        {"Property": "A detected type", "Value": a_detected},
        {"Property": "B detected type", "Value": b_detected},
        {"Property": "Final analysis mode", "Value": final_mode},
        {"Property": "Rows", "Value": total_rows},
        {"Property": "Valid paired rows", "Value": valid_pairs},
        {"Property": "Rows excluded by missingness", "Value": pair_missing},
        {"Property": "Pair completeness %", "Value": f"{valid_pct}%"},
    ])

def render_numeric_numeric(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    st.write("**Relationship type:** Numeric vs Numeric")

    temp = pd.DataFrame({
        col_a: pd.to_numeric(sa, errors="coerce"),
        col_b: pd.to_numeric(sb, errors="coerce")
    })

    n_before = len(temp)
    temp = temp.dropna()
    n_after = len(temp)

    st.caption(f"Valid observations used: {n_after} / {n_before}")

    if len(temp) < 3:
        st.warning("Not enough valid numeric observations.")
        return

    x = temp[col_a]
    y = temp[col_b]

    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)
    cov_val = x.cov(y)

    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()

    slope = model.params[col_a]
    intercept = model.params["const"]
    r_squared = model.rsquared
    slope_p = model.pvalues[col_a]

    conf_int = model.conf_int()
    slope_ci_low = conf_int.loc[col_a, 0]
    slope_ci_high = conf_int.loc[col_a, 1]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pearson r", f"{pearson_r:.3f}")
    m2.metric("Spearman ρ", f"{spearman_r:.3f}")
    m3.metric("R²", f"{r_squared:.3f}")
    m4.metric("Covariance", f"{cov_val:.3f}")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Slope", f"{slope:.3f}")
    m6.metric("Intercept", f"{intercept:.3f}")
    m7.metric("Slope p-value", f"{slope_p:.4g}")
    m8.metric("95% CI slope", f"[{slope_ci_low:.3f}, {slope_ci_high:.3f}]")

    with st.expander("Interpretation", expanded=True):
        st.write(build_numeric_numeric_interpretation(
            col_a=col_a,
            col_b=col_b,
            pearson_r=pearson_r,
            pearson_p=pearson_p,
            slope=slope,
            slope_ci_low=slope_ci_low,
            slope_ci_high=slope_ci_high,
            r_squared=r_squared,
            n=n_after
        ))

    st.markdown("#### Scatter Plot with Regression Line")
    fig = px.scatter(
        temp,
        x=col_a,
        y=col_b,
        trendline="ols",
        title=f"{col_a} vs {col_b}"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Residual Plot")
    residual_df = pd.DataFrame({
        "Fitted": model.fittedvalues,
        "Residuals": model.resid
    })
    fig_res = px.scatter(
        residual_df,
        x="Fitted",
        y="Residuals",
        title=f"Residual Plot: {col_b} ~ {col_a}"
    )
    fig_res.add_hline(y=0)
    st.plotly_chart(fig_res, use_container_width=True)

    with st.expander("Detailed Results"):
        details_df = pd.DataFrame({
            "Metric": [
                "Sample size",
                "Pearson r",
                "Pearson p-value",
                "Spearman rho",
                "Spearman p-value",
                "Slope",
                "Intercept",
                "Slope CI low",
                "Slope CI high",
                "R-squared"
            ],
            "Value": [
                n_after,
                pearson_r,
                pearson_p,
                spearman_r,
                spearman_p,
                slope,
                intercept,
                slope_ci_low,
                slope_ci_high,
                r_squared
            ]
        })
        st.dataframe(details_df, use_container_width=True)

def _render_bi_kpi(title: str, value: str, subtitle: str = "", accent: str = "#2563eb"):
    st.markdown(
        f"""
        <div class="bi-card bi-kpi">
            <div class="bi-kpi-line" style="background:{accent};"></div>
            <div class="bi-kpi-title">{title}</div>
            <div class="bi-kpi-value">{value}</div>
            <div class="bi-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def _quality_badge_from_pair_validity(valid_pct: float) -> tuple[str, str]:
    if valid_pct >= 95:
        return "High readiness", "#16a34a"
    if valid_pct >= 80:
        return "Good readiness", "#2563eb"
    if valid_pct >= 60:
        return "Moderate readiness", "#f59e0b"
    return "Low readiness", "#dc2626"

def _ensure_bivariate_styles():
    st.markdown("""
    <style>
    .bi-header {
        padding: 1.15rem 1.2rem 1rem 1.2rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 55%, #eef6ff 100%);
        border: 1px solid #e5e7eb;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }
    .bi-title {
        font-size: 1.55rem;
        font-weight: 750;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .bi-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .bi-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
    }
    .bi-kpi {
        min-height: 112px;
        position: relative;
        overflow: hidden;
    }
    .bi-kpi-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.75rem;
    }
    .bi-kpi-title {
        font-size: 0.84rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 0.3rem;
    }
    .bi-kpi-value {
        font-size: 1.45rem;
        line-height: 1.15;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.15rem;
    }
    .bi-kpi-subtitle {
        font-size: 0.81rem;
        color: #64748b;
    }
    .bi-panel-title {
        font-size: 1.02rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.45rem;
    }
    .bi-panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.75rem;
    }
    .bi-info {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .bi-success {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .bi-warning {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .bi-danger {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .bi-badge {
        display: inline-block;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    </style>
    """, unsafe_allow_html=True)

def _detected_pair_label(a_is_num: bool, b_is_num: bool) -> str:
    if a_is_num and b_is_num:
        return "Numeric vs Numeric"
    if (not a_is_num) and (not b_is_num):
        return "Categorical vs Categorical"
    return "Numeric vs Categorical"

def _build_suggested_tests_for_pair(final_mode: str) -> pd.DataFrame:
    mapping = {
        "Numeric vs Numeric": [
            {
                "Scenario": "Linear association",
                "Suggested test / method": "Pearson correlation, scatter plot, trend line",
                "Why": "Quantify linear relationship between two continuous variables"
            },
            {
                "Scenario": "Monotonic non-linear association",
                "Suggested test / method": "Spearman correlation",
                "Why": "Useful when rank-order relation matters more than strict linearity"
            },
            {
                "Scenario": "Predictive relationship",
                "Suggested test / method": "Simple linear regression",
                "Why": "Estimate the effect of one numeric variable on the other"
            },
        ],
        "Categorical vs Categorical": [
            {
                "Scenario": "Association between categories",
                "Suggested test / method": "Contingency table, chi-square test",
                "Why": "Evaluate dependence between categorical variables"
            },
            {
                "Scenario": "Strength of association",
                "Suggested test / method": "Cramér's V",
                "Why": "Measure the effect size of categorical association"
            },
            {
                "Scenario": "Visual structure",
                "Suggested test / method": "Stacked bar chart, normalized proportions",
                "Why": "Reveal how categories distribute across groups"
            },
        ],
        "Numeric vs Categorical": [
            {
                "Scenario": "Group comparison",
                "Suggested test / method": "Boxplot, grouped summary statistics",
                "Why": "Compare the numeric distribution across categories"
            },
            {
                "Scenario": "Two groups only",
                "Suggested test / method": "t-test",
                "Why": "Test whether the group means differ significantly"
            },
            {
                "Scenario": "Three or more groups",
                "Suggested test / method": "ANOVA",
                "Why": "Assess whether at least one group mean differs from the others"
            },
        ],
    }
    return pd.DataFrame(mapping.get(final_mode, []))

def render_heatmap_table(ctab: pd.DataFrame, title: str):
    import plotly.express as px

    fig = px.imshow(
        ctab,
        text_auto=True,
        aspect="auto",
        title=f"Heatmap: {title}"
    )
    st.plotly_chart(fig, use_container_width=True)

def build_categorical_categorical_interpretation(
    col_a: str,
    col_b: str,
    p_value: float,
    cramers_v: float,
    low_expected: int
) -> str:
    if pd.isna(cramers_v):
        strength = "undefined"
    elif cramers_v < 0.1:
        strength = "very weak"
    elif cramers_v < 0.3:
        strength = "weak"
    elif cramers_v < 0.5:
        strength = "moderate"
    else:
        strength = "strong"

    significance = (
        "a statistically significant association"
        if p_value < 0.05 else
        "no statistically significant association"
    )

    expected_note = (
        f" There are {low_expected} cells with expected frequency below 5, so the chi-square approximation may be less reliable."
        if low_expected > 0 else
        " Expected frequencies look acceptable for the chi-square approximation."
    )

    return (
        f"The analysis suggests {significance} between {col_a} and {col_b} "
        f"(Chi-square test, p = {p_value:.4g}). The association strength based on Cramér's V is {strength}."
        f"{expected_note}"
    )

def build_numeric_numeric_interpretation(
    col_a: str,
    col_b: str,
    pearson_r: float,
    pearson_p: float,
    slope: float,
    slope_ci_low: float,
    slope_ci_high: float,
    r_squared: float,
    n: int
) -> str:
    abs_r = abs(pearson_r)

    if abs_r < 0.2:
        strength = "very weak"
    elif abs_r < 0.4:
        strength = "weak"
    elif abs_r < 0.6:
        strength = "moderate"
    elif abs_r < 0.8:
        strength = "strong"
    else:
        strength = "very strong"

    direction = "positive" if pearson_r > 0 else "negative"

    significance = (
        "statistically significant"
        if pearson_p < 0.05 else
        "not statistically significant"
    )

    ci_text = (
        "The slope confidence interval includes 0, so the linear effect should be interpreted cautiously."
        if slope_ci_low <= 0 <= slope_ci_high else
        "The slope confidence interval does not include 0, which supports a non-zero linear trend."
    )

    return (
        f"A {strength} {direction} linear relationship was observed between {col_a} and {col_b} "
        f"(Pearson r = {pearson_r:.3f}, p = {pearson_p:.4g}, n = {n}). "
        f"The fitted regression suggests that a one-unit increase in {col_a} is associated with an average "
        f"change of {slope:.3f} units in {col_b}. The model explains approximately {r_squared:.1%} "
        f"of the variance in {col_b}. The result is {significance}. {ci_text}"
    )

def render_boxplot_by_category(temp: pd.DataFrame, cat_name: str, num_name: str):
    import plotly.express as px

    fig = px.box(
        temp,
        x="category",
        y="value",
        title=f"{num_name} distribution by {cat_name}",
        labels={"category": cat_name, "value": num_name}
    )
    st.plotly_chart(fig, use_container_width=True)


def interpret_correlation(value):
    if pd.isna(value):
        return "undefined"
    abs_val = abs(value)
    if abs_val < 0.2:
        return "very weak"
    if abs_val < 0.4:
        return "weak"
    if abs_val < 0.6:
        return "moderate"
    if abs_val < 0.8:
        return "strong"
    return "very strong"

def render_bivariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    _ensure_bivariate_styles()

    st.markdown("""
    <div class="bi-header">
        <div class="bi-title">Bivariate analysis</div>
        <div class="bi-subtitle">
            Pairwise analysis between two selected variables with automatic type detection,
            readiness checks, structural interpretation, and method-specific diagnostics.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df is None or df.empty:
        st.warning("No valid dataframe is available for bivariate analysis.")
        return

    if not cols_for_stats:
        st.warning("No columns are available for bivariate analysis.")
        return

    valid_cols = [c for c in cols_for_stats if c in df.columns]
    if len(valid_cols) < 2:
        st.warning("At least two valid columns are required for bivariate analysis.")
        return

    c1, c2, c3 = st.columns([1, 1, 1.2])

    with c1:
        col_a = st.selectbox("Variable A", valid_cols, key="biv_col_a")

    with c2:
        default_index_b = 1 if len(valid_cols) > 1 else 0
        col_b = st.selectbox(
            "Variable B",
            valid_cols,
            index=default_index_b,
            key="biv_col_b"
        )

    with c3:
        mode = st.selectbox(
            "Analysis mode",
            [
                "Auto",
                "Numeric vs Numeric",
                "Categorical vs Categorical",
                "Numeric vs Categorical"
            ],
            key="biv_mode"
        )

    if col_a == col_b:
        st.info("Choose two different variables.")
        return

    sa = df[col_a]
    sb = df[col_b]

    a_is_num, sa_num = detect_is_numeric(sa)
    b_is_num, sb_num = detect_is_numeric(sb)

    auto_mode = _detected_pair_label(a_is_num, b_is_num)

    if mode == "Auto":
        final_mode = auto_mode
        decision_source = "Automatic detection"
    else:
        final_mode = mode
        decision_source = "Manual override"

    pair_df = pd.DataFrame({col_a: sa, col_b: sb})
    valid_pair_df = pair_df.dropna(subset=[col_a, col_b])

    total_rows = len(pair_df)
    valid_pairs = len(valid_pair_df)
    pair_missing = total_rows - valid_pairs
    valid_pct = _safe_pct(valid_pairs, total_rows)

    a_non_null = int(sa.notna().sum())
    b_non_null = int(sb.notna().sum())

    a_unique = int(sa.nunique(dropna=True))
    b_unique = int(sb.nunique(dropna=True))

    a_label = "Numeric" if a_is_num else "Categorical"
    b_label = "Numeric" if b_is_num else "Categorical"

    badge_text, badge_color = _quality_badge_from_pair_validity(valid_pct)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        _render_bi_kpi("Variable A", col_a, a_label, "#2563eb")
    with k2:
        _render_bi_kpi("Variable B", col_b, b_label, "#0ea5e9")
    with k3:
        _render_bi_kpi("Detected pair", auto_mode, decision_source, "#16a34a")
    with k4:
        _render_bi_kpi("Valid pairs", f"{valid_pairs:,}", f"{valid_pct}%", "#f59e0b")
    with k5:
        _render_bi_kpi("Final mode", final_mode, badge_text, badge_color)

    tabs = st.tabs([
        "Analysis",
        "Metadata",
        "Interpretation",
        "Suggested tests"
    ])

    with tabs[0]:
        st.markdown(
            f"""
            <div class="bi-card" style="margin-bottom: 0.9rem;">
                <div class="bi-panel-title">Current configuration</div>
                <div class="bi-panel-subtitle">
                    <b>{col_a}</b> and <b>{col_b}</b> are being analyzed as <b>{final_mode}</b>.
                </div>
                <div class="bi-badge" style="background:{badge_color}18;color:{badge_color};border:1px solid {badge_color}40;">
                    {badge_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if valid_pairs == 0:
            st.markdown(
                """
                <div class="bi-danger">
                    There are no valid paired observations after removing rows with missing values in either variable.
                    Bivariate analysis cannot be computed.
                </div>
                """,
                unsafe_allow_html=True
            )
            return

        if final_mode == "Numeric vs Numeric":
            render_numeric_numeric(sa, sb, col_a, col_b)
        elif final_mode == "Categorical vs Categorical":
            render_categorical_categorical(sa, sb, col_a, col_b)
        elif final_mode == "Numeric vs Categorical":
            render_numeric_categorical(sa, sb, col_a, col_b, a_is_num)
        else:
            st.warning("Unsupported analysis mode.")

    with tabs[1]:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown('<div class="bi-panel-title">Pair metadata</div>', unsafe_allow_html=True)
            st.markdown('<div class="bi-panel-subtitle">Structural description of the selected variable pair.</div>', unsafe_allow_html=True)

            meta_df = _build_bivariate_meta_df(
                col_a=col_a,
                col_b=col_b,
                a_dtype=str(sa.dtype),
                b_dtype=str(sb.dtype),
                a_detected=a_label,
                b_detected=b_label,
                valid_pairs=valid_pairs,
                total_rows=total_rows,
                pair_missing=pair_missing,
                valid_pct=valid_pct,
                final_mode=final_mode
            )
            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="bi-panel-title">Quick structural signals</div>', unsafe_allow_html=True)
            st.markdown('<div class="bi-panel-subtitle">Readiness and potential issues before interpreting results.</div>', unsafe_allow_html=True)

            if valid_pct >= 95:
                st.markdown(
                    """
                    <div class="bi-success">
                        Pair completeness is very high, so the relationship can be analyzed with minimal missing-data concern.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif valid_pct >= 80:
                st.markdown(
                    """
                    <div class="bi-info">
                        Pair completeness is good. The analysis should remain broadly reliable.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif valid_pct >= 60:
                st.markdown(
                    """
                    <div class="bi-warning">
                        A notable share of rows is excluded by missingness, so results may be less stable or less representative.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class="bi-danger">
                        Pair completeness is low. Relationship analysis should be interpreted with caution.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if final_mode == "Numeric vs Numeric":
                st.markdown(
                    """
                    <div class="bi-success">
                        This setup is appropriate for scatter plots, correlation, and trend estimation.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif final_mode == "Categorical vs Categorical":
                if a_unique > 20 or b_unique > 20:
                    st.markdown(
                        """
                        <div class="bi-warning">
                            At least one categorical variable has high cardinality, which may produce sparse contingency tables and crowded charts.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
                        <div class="bi-success">
                            Category counts appear manageable for contingency analysis and stacked visualizations.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            elif final_mode == "Numeric vs Categorical":
                cat_unique = b_unique if a_is_num else a_unique if final_mode == auto_mode else min(a_unique, b_unique)
                if cat_unique > 20:
                    st.markdown(
                        """
                        <div class="bi-warning">
                            The categorical side may have too many levels for clean group comparison. Consider grouping rare categories.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
                        <div class="bi-success">
                            This setup is suitable for comparing numeric distributions across groups.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown(
                f"""
                <div class="bi-card" style="margin-top:0.6rem;">
                    <div class="bi-panel-title">Variable profile</div>
                    <div class="bi-panel-subtitle">
                        <b>{col_a}</b>: {a_non_null:,} non-null, {a_unique:,} unique<br>
                        <b>{col_b}</b>: {b_non_null:,} non-null, {b_unique:,} unique
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with tabs[2]:
        st.markdown('<div class="bi-panel-title">Automatic interpretation</div>', unsafe_allow_html=True)
        st.markdown('<div class="bi-panel-subtitle">System-generated narrative based on pair structure and analysis mode.</div>', unsafe_allow_html=True)

        insights = []

        insights.append(
            f"The selected pair is <b>{col_a}</b> and <b>{col_b}</b>, with <b>{valid_pairs:,}</b> valid paired observations out of <b>{total_rows:,}</b> total rows."
        )

        if final_mode == "Numeric vs Numeric":
            insights.append(
                "Both variables are being treated as numeric, so the main focus is linear or monotonic association, dispersion, and possible predictive trend."
            )
            if valid_pct < 80:
                insights.append(
                    "Because pair completeness is reduced, the observed relationship may reflect a filtered subset rather than the full dataset."
                )
            if a_unique <= 5 or b_unique <= 5:
                insights.append(
                    "At least one variable has very low numeric diversity, so it may behave more like an ordinal scale than a continuous measure."
                )

        elif final_mode == "Categorical vs Categorical":
            insights.append(
                "Both variables are being treated as categorical, so the main focus is whether category membership in one variable is associated with the other."
            )
            if a_unique > 20 or b_unique > 20:
                insights.append(
                    "High category cardinality may create sparse cells and make contingency-based interpretation less stable or less readable."
                )
            else:
                insights.append(
                    "The category structure appears usable for contingency tables, normalized comparisons, and association testing."
                )

        elif final_mode == "Numeric vs Categorical":
            insights.append(
                "This pair is being treated as numeric versus categorical, so the central question is whether the numeric distribution changes meaningfully across groups."
            )
            if valid_pct < 80:
                insights.append(
                    "Because some rows are excluded by missingness, group comparisons may be based on an incomplete subset."
                )
            if a_unique > 20 and b_unique > 20:
                insights.append(
                    "One side may have many levels, so group summaries may be clearer after category consolidation."
                )

        insights.append(
            f"The final analysis mode comes from {'automatic detection' if mode == 'Auto' else 'manual override'}, so interpretation should reflect the intended analytical role of each variable."
        )

        for txt in insights:
            st.markdown(f'<div class="bi-info">{txt}</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="bi-panel-title">Suggested next analyses</div>', unsafe_allow_html=True)
        st.markdown('<div class="bi-panel-subtitle">Recommended tests and visuals for the selected variable pair.</div>', unsafe_allow_html=True)

        tests_df = _build_suggested_tests_for_pair(final_mode)

        if tests_df.empty:
            st.info("No suggestions are available for the current pair configuration.")
        else:
            st.dataframe(tests_df, use_container_width=True, hide_index=True)

        workflow_steps = []

        if final_mode == "Numeric vs Numeric":
            workflow_steps = [
                "Inspect the scatter plot for linearity, clusters, curvature, and extreme points.",
                "Quantify the relationship with Pearson or Spearman correlation.",
                "Add a trend line and consider simple regression if prediction matters.",
                "Review outliers because a few extreme values can distort correlation."
            ]
        elif final_mode == "Categorical vs Categorical":
            workflow_steps = [
                "Start with a contingency table of counts.",
                "Then inspect normalized proportions to compare category composition.",
                "Use chi-square to test dependence between the variables.",
                "If association is significant, add an effect-size measure such as Cramér's V."
            ]
        elif final_mode == "Numeric vs Categorical":
            workflow_steps = [
                "Inspect grouped distributions with boxplots or violin plots.",
                "Compare means or medians across categories.",
                "Use a t-test for two groups or ANOVA for three or more groups.",
                "If there are many rare categories, consolidate them before inference."
            ]

        for step in workflow_steps:
            st.markdown(f'<div class="bi-success">{step}</div>', unsafe_allow_html=True)