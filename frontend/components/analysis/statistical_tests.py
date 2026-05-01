import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import statsmodels.api as sm
from scipy import stats

from services.stat_service import detect_is_numeric


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def _format_number(value, decimals: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    return f"{value:,.{decimals}f}"


def _format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _safe_key(*parts) -> str:
    return "_".join(
        str(part)
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("[", "")
        .replace("]", "")
        .replace("{", "")
        .replace("}", "")
        .replace(",", "_")
        .replace("×", "x")
        for part in parts
    )


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


def _get_valid_columns(df: pd.DataFrame, cols_for_stats: list[str]) -> list[str]:
    if not cols_for_stats:
        return list(df.columns)

    return [col for col in cols_for_stats if col in df.columns]


def _get_numeric_columns(df: pd.DataFrame, valid_cols: list[str]) -> list[str]:
    numeric_cols = []

    for col in valid_cols:
        s = _normalize_missing(df[col])
        is_numeric, _ = detect_is_numeric(s)

        if is_numeric:
            numeric_cols.append(col)

    return numeric_cols


def _get_categorical_columns(df: pd.DataFrame, valid_cols: list[str]) -> list[str]:
    categorical_cols = []

    for col in valid_cols:
        s = _normalize_missing(df[col])
        is_numeric, _ = detect_is_numeric(s)

        if not is_numeric:
            categorical_cols.append(col)

    return categorical_cols


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


def _association_strength(value: float) -> str:
    if pd.isna(value):
        return "undefined"

    abs_value = abs(value)

    if abs_value < 0.2:
        return "very weak"
    if abs_value < 0.4:
        return "weak"
    if abs_value < 0.6:
        return "moderate"
    if abs_value < 0.8:
        return "strong"

    return "very strong"


def _cramers_v_strength(value: float) -> str:
    if pd.isna(value):
        return "undefined"

    if value < 0.1:
        return "very weak"
    if value < 0.3:
        return "weak"
    if value < 0.5:
        return "moderate"

    return "strong"


def _p_value_label(p_value: float) -> str:
    if pd.isna(p_value):
        return "Unavailable"

    return "Significant" if p_value < 0.05 else "Not significant"


def _validity_badge(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "High readiness"
    if valid_pct >= 80:
        return "Good readiness"
    if valid_pct >= 60:
        return "Moderate readiness"
    return "Low readiness"


# ============================================================
# UI HELPERS
# ============================================================

def _render_test_kpi(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="sttest-card sttest-kpi">
            <div class="sttest-kpi-title">{title}</div>
            <div class="sttest-kpi-value">{value}</div>
            <div class="sttest-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str):
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="sttest-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="sttest-panel-title">{title}</div>
        <div class="sttest-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_current_config(title: str, subtitle: str, badge: str):
    st.markdown(
        f"""
        <div class="sttest-card">
            <div class="sttest-panel-title">{title}</div>
            <div class="sttest-panel-subtitle">{subtitle}</div>
            <div class="sttest-badge">{badge}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PREDICTION FORMULA HELPERS
# ============================================================

def _fit_simple_prediction_model(
    temp: pd.DataFrame,
    predictor_col: str,
    target_col: str,
):
    x = temp[predictor_col]
    y = temp[target_col]

    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()

    intercept = float(model.params["const"])
    slope = float(model.params[predictor_col])

    return model, intercept, slope


def _build_simple_prediction_formula(
    target_col: str,
    predictor_col: str,
    intercept: float,
    slope: float,
) -> str:
    sign = "+" if slope >= 0 else "-"

    return (
        f"{target_col} = "
        f"{intercept:.6f} {sign} {abs(slope):.6f} × {predictor_col}"
    )


def _render_prediction_formula(
    prediction_model,
    target_col: str,
    predictor_col: str,
    intercept: float,
    slope: float,
):
    prediction_formula = _build_simple_prediction_formula(
        target_col=target_col,
        predictor_col=predictor_col,
        intercept=intercept,
        slope=slope,
    )

    _render_section_title(
        "Prediction formula",
        "Estimated dependency formula fitted from the selected variables.",
    )

    st.code(prediction_formula)

    _render_alert(
        "info",
        f"This formula estimates <b>{target_col}</b> from <b>{predictor_col}</b>. "
        f"The coefficient means that each one-unit increase in <b>{predictor_col}</b> is associated with an average "
        f"change of <b>{slope:.6f}</b> units in <b>{target_col}</b>.",
    )

    formula_details_df = pd.DataFrame(
        [
            {"Term": "Target / dependent variable", "Value": target_col},
            {"Term": "Predictor / independent variable", "Value": predictor_col},
            {"Term": "Intercept", "Value": intercept},
            {"Term": "Coefficient / slope", "Value": slope},
            {"Term": "R-squared", "Value": prediction_model.rsquared},
            {"Term": "Adjusted R-squared", "Value": prediction_model.rsquared_adj},
            {"Term": "Model p-value", "Value": prediction_model.f_pvalue},
        ]
    )

    st.dataframe(formula_details_df, use_container_width=True, hide_index=True)


def _render_chi_square_dependency_summary(result: dict, col_a: str, col_b: str):
    _render_section_title(
        "Dependency summary",
        "For categorical variables, dependency is expressed through observed vs expected frequencies, not a numeric prediction equation.",
    )

    _render_alert(
        "info",
        f"The dependency between <b>{col_a}</b> and <b>{col_b}</b> is summarized by the chi-square statistic "
        f"and Cramér's V. Unlike numeric regression, this test does not produce a formula like "
        f"<b>Y = a + bX</b>."
    )

    dependency_df = pd.DataFrame(
        [
            {"Measure": "Chi-square", "Value": result["chi2"]},
            {"Measure": "p-value", "Value": result["p_value"]},
            {"Measure": "Degrees of freedom", "Value": result["dof"]},
            {"Measure": "Cramér's V", "Value": result["cramers_v"]},
            {"Measure": "Association strength", "Value": _cramers_v_strength(result["cramers_v"])},
            {"Measure": "Low expected cells", "Value": result["low_expected"]},
        ]
    )

    st.dataframe(dependency_df, use_container_width=True, hide_index=True)


def _render_group_dependency_summary(
    group_summary: pd.DataFrame,
    num_col: str,
    cat_col: str,
):
    _render_section_title(
        "Group prediction rule",
        "For group comparisons, the practical prediction is the average value for each category.",
    )

    _render_alert(
        "info",
        f"A simple dependency rule for this setup is: predict <b>{num_col}</b> using the mean of its "
        f"<b>{cat_col}</b> group. This is not a continuous regression equation, but it is useful for practical estimation.",
    )

    prediction_df = group_summary[[cat_col, "count", "mean", "median", "std"]].copy()
    prediction_df = prediction_df.rename(
        columns={
            cat_col: "Group",
            "count": "N",
            "mean": f"Predicted {num_col} by group mean",
            "median": "Group median",
            "std": "Group std",
        }
    )

    st.dataframe(prediction_df, use_container_width=True, hide_index=True)


# ============================================================
# CORRELATION TEST
# ============================================================

def _prepare_numeric_pair(df: pd.DataFrame, col_a: str, col_b: str) -> tuple[pd.DataFrame, int, int, float]:
    temp = pd.DataFrame(
        {
            col_a: pd.to_numeric(_normalize_missing(df[col_a]), errors="coerce"),
            col_b: pd.to_numeric(_normalize_missing(df[col_b]), errors="coerce"),
        }
    )

    total_rows = len(temp)
    temp = temp.dropna()
    valid_rows = len(temp)
    valid_pct = _safe_pct(valid_rows, total_rows)

    return temp, total_rows, valid_rows, valid_pct


def _build_correlation_interpretation(
    col_a: str,
    col_b: str,
    method: str,
    statistic: float,
    p_value: float,
    n: int,
) -> str:
    strength = _association_strength(statistic)

    if statistic > 0:
        direction = "positive"
    elif statistic < 0:
        direction = "negative"
    else:
        direction = "no clear"

    significance = (
        "statistically significant"
        if p_value < 0.05
        else "not statistically significant"
    )

    if method == "Pearson":
        method_note = "Pearson correlation focuses on linear association."
    else:
        method_note = "Spearman correlation focuses on rank-based or monotonic association."

    return (
        f"The <b>{method}</b> test shows a <b>{strength}</b> {direction} association between "
        f"<b>{col_a}</b> and <b>{col_b}</b> "
        f"(statistic = <b>{statistic:.3f}</b>, p = <b>{p_value:.4g}</b>, n = <b>{n:,}</b>). "
        f"The result is <b>{significance}</b>. {method_note}"
    )


def render_correlation_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    valid_cols = _get_valid_columns(df, cols_for_stats)
    numeric_cols = _get_numeric_columns(df, valid_cols)

    if len(numeric_cols) < 2:
        _render_alert("warning", "At least two numeric variables are required for a correlation test.")
        return

    st.markdown('<div class="sttest-toolbar">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1.2, 1])

    with c1:
        col_a = st.selectbox(
            "Variable A",
            numeric_cols,
            key="test_corr_a",
            help="Predictor / independent variable.",
        )

    with c2:
        default_b = 1 if len(numeric_cols) > 1 else 0
        col_b = st.selectbox(
            "Variable B",
            numeric_cols,
            index=default_b,
            key="test_corr_b",
            help="Target / dependent variable.",
        )

    with c3:
        method = st.selectbox(
            "Method",
            ["Pearson", "Spearman"],
            key="test_corr_method",
            help="Pearson for linear association. Spearman for monotonic/rank association.",
        )

    st.markdown(
        """
        <div class="sttest-small-muted">
            Variable A is treated as the predictor and Variable B as the target for the prediction formula.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if col_a == col_b:
        _render_alert("info", "Choose two different numeric variables.")
        return

    temp, total_rows, valid_rows, valid_pct = _prepare_numeric_pair(df, col_a, col_b)

    if valid_rows < 3:
        _render_alert("warning", "Not enough valid observations. At least 3 paired numeric rows are required.")
        return

    if method == "Pearson":
        statistic, p_value = stats.pearsonr(temp[col_a], temp[col_b])
    else:
        statistic, p_value = stats.spearmanr(temp[col_a], temp[col_b])

    prediction_model, intercept, slope = _fit_simple_prediction_model(
        temp=temp,
        predictor_col=col_a,
        target_col=col_b,
    )

    readiness = _validity_badge(valid_pct)

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        _render_test_kpi("Statistic", _format_number(statistic), method)

    with k2:
        _render_test_kpi("p-value", _format_number(p_value, 4), _p_value_label(p_value))

    with k3:
        _render_test_kpi("Valid rows", _format_int(valid_rows), f"{valid_pct}% · {readiness}")

    with k4:
        _render_test_kpi("R²", _format_number(prediction_model.rsquared), "Formula fit")

    tabs = st.tabs(["Result", "Visualization", "Prediction formula", "Details"])

    with tabs[0]:
        _render_current_config(
            title="Correlation test result",
            subtitle=f"<b>{col_a}</b> predicts <b>{col_b}</b> through a simple fitted dependency formula.",
            badge=_p_value_label(p_value),
        )

        interpretation = _build_correlation_interpretation(
            col_a=col_a,
            col_b=col_b,
            method=method,
            statistic=statistic,
            p_value=p_value,
            n=valid_rows,
        )

        _render_alert("info", interpretation)

        if valid_pct < 80:
            _render_alert(
                "warning",
                "Pair completeness is below 80%, so the association may reflect a filtered subset.",
            )

    with tabs[1]:
        _render_section_title(
            "Scatter plot with fitted line",
            "Use the chart to check direction, shape, clusters, and possible outliers.",
        )

        fig = px.scatter(
            temp,
            x=col_a,
            y=col_b,
            trendline="ols",
            labels={col_a: col_a, col_b: col_b},
        )
        fig = _plot_layout(fig, 440, col_a, col_b)

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=_safe_key("sttest_corr_scatter", col_a, col_b, method),
        )

    with tabs[2]:
        _render_prediction_formula(
            prediction_model=prediction_model,
            target_col=col_b,
            predictor_col=col_a,
            intercept=intercept,
            slope=slope,
        )

    with tabs[3]:
        result_df = pd.DataFrame(
            [
                {"Metric": "Method", "Value": method},
                {"Metric": "Predictor / independent variable", "Value": col_a},
                {"Metric": "Target / dependent variable", "Value": col_b},
                {"Metric": "Total rows", "Value": total_rows},
                {"Metric": "Valid paired rows", "Value": valid_rows},
                {"Metric": "Validity %", "Value": f"{valid_pct}%"},
                {"Metric": "Correlation statistic", "Value": statistic},
                {"Metric": "Correlation p-value", "Value": p_value},
                {"Metric": "Association strength", "Value": _association_strength(statistic)},
                {"Metric": "Prediction intercept", "Value": intercept},
                {"Metric": "Prediction coefficient / slope", "Value": slope},
                {"Metric": "Prediction R-squared", "Value": prediction_model.rsquared},
                {"Metric": "Prediction model p-value", "Value": prediction_model.f_pvalue},
            ]
        )

        st.dataframe(result_df, use_container_width=True, hide_index=True)


# ============================================================
# CHI-SQUARE TEST
# ============================================================

def _prepare_categorical_pair(df: pd.DataFrame, col_a: str, col_b: str) -> tuple[pd.DataFrame, int, int, float]:
    temp = pd.DataFrame(
        {
            col_a: _normalize_missing(df[col_a]).fillna("(missing)").astype(str),
            col_b: _normalize_missing(df[col_b]).fillna("(missing)").astype(str),
        }
    )

    total_rows = len(temp)
    valid_rows = len(temp.dropna())
    valid_pct = _safe_pct(valid_rows, total_rows)

    return temp, total_rows, valid_rows, valid_pct


def _compute_chi_square(temp: pd.DataFrame, col_a: str, col_b: str):
    ctab = pd.crosstab(temp[col_a], temp[col_b])

    if ctab.empty:
        return None

    chi2, p_value, dof, expected = stats.chi2_contingency(ctab)

    n = ctab.to_numpy().sum()
    min_dim = min(ctab.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else np.nan
    low_expected = int((expected < 5).sum())

    expected_df = pd.DataFrame(expected, index=ctab.index, columns=ctab.columns)
    row_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="index") * 100
    col_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="columns") * 100

    return {
        "ctab": ctab,
        "row_pct": row_pct,
        "col_pct": col_pct,
        "expected": expected_df,
        "chi2": chi2,
        "p_value": p_value,
        "dof": dof,
        "cramers_v": cramers_v,
        "low_expected": low_expected,
    }


def _build_chi_square_interpretation(
    col_a: str,
    col_b: str,
    chi2: float,
    p_value: float,
    cramers_v: float,
    low_expected: int,
) -> str:
    if p_value < 0.05:
        significance = "a statistically significant association"
    else:
        significance = "no statistically significant association"

    strength = _cramers_v_strength(cramers_v)

    expected_note = (
        f"There are <b>{low_expected}</b> cells with expected frequency below 5, so the chi-square approximation may be less reliable."
        if low_expected > 0
        else "Expected frequencies look acceptable for the chi-square approximation."
    )

    return (
        f"The chi-square test suggests <b>{significance}</b> between <b>{col_a}</b> and <b>{col_b}</b> "
        f"(χ² = <b>{chi2:.3f}</b>, p = <b>{p_value:.4g}</b>). "
        f"The association strength based on Cramér's V is <b>{strength}</b>. {expected_note}"
    )


def render_chi_square_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    valid_cols = _get_valid_columns(df, cols_for_stats)
    categorical_cols = _get_categorical_columns(df, valid_cols)

    if len(categorical_cols) < 2:
        _render_alert("warning", "At least two categorical variables are required for a chi-square test.")
        return

    st.markdown('<div class="sttest-toolbar">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        col_a = st.selectbox(
            "Categorical Variable A",
            categorical_cols,
            key="chi_a",
            help="First categorical variable.",
        )

    with c2:
        default_b = 1 if len(categorical_cols) > 1 else 0
        col_b = st.selectbox(
            "Categorical Variable B",
            categorical_cols,
            index=default_b,
            key="chi_b",
            help="Second categorical variable.",
        )

    st.markdown(
        """
        <div class="sttest-small-muted">
            Chi-square tests whether two categorical variables appear associated. For categorical data, dependency is summarized through frequencies, not a numeric equation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if col_a == col_b:
        _render_alert("info", "Choose two different categorical variables.")
        return

    temp, total_rows, valid_rows, valid_pct = _prepare_categorical_pair(df, col_a, col_b)
    result = _compute_chi_square(temp, col_a, col_b)

    if result is None:
        _render_alert("warning", "No valid contingency data is available.")
        return

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        _render_test_kpi("Chi-square", _format_number(result["chi2"]), "Test statistic")

    with k2:
        _render_test_kpi("p-value", _format_number(result["p_value"], 4), _p_value_label(result["p_value"]))

    with k3:
        _render_test_kpi("Cramér's V", _format_number(result["cramers_v"]), _cramers_v_strength(result["cramers_v"]))

    with k4:
        _render_test_kpi("Low expected", _format_int(result["low_expected"]), "Cells < 5")

    tabs = st.tabs(["Result", "Tables", "Heatmap", "Dependency summary", "Expected"])

    with tabs[0]:
        _render_current_config(
            title="Chi-square test result",
            subtitle=f"<b>{col_a}</b> and <b>{col_b}</b> were tested for categorical association.",
            badge=_p_value_label(result["p_value"]),
        )

        interpretation = _build_chi_square_interpretation(
            col_a=col_a,
            col_b=col_b,
            chi2=result["chi2"],
            p_value=result["p_value"],
            cramers_v=result["cramers_v"],
            low_expected=result["low_expected"],
        )

        _render_alert("info", interpretation)

        if result["low_expected"] > 0:
            _render_alert(
                "warning",
                "Some expected frequencies are below 5. Consider combining rare categories or using an exact test for small tables.",
            )

    with tabs[1]:
        subtab_counts, subtab_row, subtab_col = st.tabs(["Counts", "Row %", "Column %"])

        with subtab_counts:
            st.dataframe(result["ctab"], use_container_width=True)

        with subtab_row:
            st.dataframe(result["row_pct"].round(2), use_container_width=True)

        with subtab_col:
            st.dataframe(result["col_pct"].round(2), use_container_width=True)

    with tabs[2]:
        _render_section_title("Contingency heatmap")

        fig = px.imshow(
            result["ctab"],
            text_auto=True,
            aspect="auto",
            labels=dict(color="Count"),
        )
        fig = _plot_layout(fig, 460, col_b, col_a)

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=_safe_key("sttest_chi_heatmap", col_a, col_b),
        )

    with tabs[3]:
        _render_chi_square_dependency_summary(result, col_a, col_b)

    with tabs[4]:
        _render_section_title(
            "Expected frequencies",
            "Expected counts are used by the chi-square test. Low expected counts can reduce reliability.",
        )

        st.dataframe(result["expected"].round(3), use_container_width=True)


# ============================================================
# GROUP MEAN TEST
# ============================================================

def _prepare_group_mean_data(df: pd.DataFrame, num_col: str, cat_col: str):
    temp = pd.DataFrame(
        {
            num_col: pd.to_numeric(_normalize_missing(df[num_col]), errors="coerce"),
            cat_col: _normalize_missing(df[cat_col]).fillna("(missing)").astype(str),
        }
    )

    total_rows = len(temp)
    temp = temp.dropna(subset=[num_col])
    valid_rows = len(temp)
    valid_pct = _safe_pct(valid_rows, total_rows)

    return temp, total_rows, valid_rows, valid_pct


def _cohens_d(g1: pd.Series, g2: pd.Series) -> float:
    n1 = len(g1)
    n2 = len(g2)

    if n1 < 2 or n2 < 2:
        return np.nan

    pooled_sd = np.sqrt(
        ((n1 - 1) * g1.var(ddof=1) + (n2 - 1) * g2.var(ddof=1)) / (n1 + n2 - 2)
    )

    if pooled_sd == 0:
        return np.nan

    return (g1.mean() - g2.mean()) / pooled_sd


def _eta_squared_anova(groups: list[pd.Series]) -> float:
    values = pd.concat([pd.Series(g) for g in groups], ignore_index=True)

    if values.empty:
        return np.nan

    grand_mean = values.mean()
    ss_between = sum(len(g) * (pd.Series(g).mean() - grand_mean) ** 2 for g in groups)
    ss_total = sum((values - grand_mean) ** 2)

    if ss_total == 0:
        return np.nan

    return ss_between / ss_total


def _build_group_summary(temp: pd.DataFrame, num_col: str, cat_col: str) -> pd.DataFrame:
    return (
        temp.groupby(cat_col)[num_col]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )


def _build_group_test_interpretation(
    num_col: str,
    cat_col: str,
    test_name: str,
    statistic: float,
    p_value: float,
    effect_size_name: str,
    effect_size_value: float,
) -> str:
    significance = (
        "statistically significant"
        if pd.notna(p_value) and p_value < 0.05
        else "not statistically significant"
    )

    if pd.notna(effect_size_value):
        effect_text = (
            f"The estimated effect size is <b>{effect_size_name} = {effect_size_value:.3f}</b>."
        )
    else:
        effect_text = "The effect size could not be computed reliably."

    return (
        f"The comparison of <b>{num_col}</b> across <b>{cat_col}</b> groups used <b>{test_name}</b>. "
        f"The test statistic was <b>{statistic:.3f}</b> with p = <b>{p_value:.4g}</b>. "
        f"The result is <b>{significance}</b>. {effect_text}"
    )


def render_group_mean_test_ui(df: pd.DataFrame, cols_for_stats: list[str]):
    valid_cols = _get_valid_columns(df, cols_for_stats)
    numeric_cols = _get_numeric_columns(df, valid_cols)
    categorical_cols = _get_categorical_columns(df, valid_cols)

    if not numeric_cols:
        _render_alert("warning", "At least one numeric variable is required for a group mean comparison.")
        return

    if not categorical_cols:
        _render_alert("warning", "At least one categorical variable is required for a group mean comparison.")
        return

    st.markdown('<div class="sttest-toolbar">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        num_col = st.selectbox(
            "Numeric Variable",
            numeric_cols,
            key="group_num",
            help="Numeric outcome to compare across groups.",
        )

    with c2:
        cat_col = st.selectbox(
            "Grouping Variable",
            categorical_cols,
            key="group_cat",
            help="Categorical variable defining the groups.",
        )

    with c3:
        test_type = st.selectbox(
            "Test",
            ["Auto", "t-test", "ANOVA"],
            key="group_test_type",
            help="Auto uses t-test for 2 groups and ANOVA for 3+ groups.",
        )

    st.markdown(
        """
        <div class="sttest-small-muted">
            Group mean tests compare whether numeric values differ across categories. The dependency estimate is the group mean.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    temp, total_rows, valid_rows, valid_pct = _prepare_group_mean_data(df, num_col, cat_col)

    if temp.empty:
        _render_alert("warning", "No valid numeric observations were found.")
        return

    n_groups = int(temp[cat_col].nunique())

    if n_groups < 2:
        _render_alert("info", "At least two groups are required.")
        return

    group_summary = _build_group_summary(temp, num_col, cat_col)
    grouped_values = [g[num_col].dropna() for _, g in temp.groupby(cat_col)]

    if test_type == "Auto":
        resolved_test = "t-test" if n_groups == 2 else "ANOVA"
    else:
        resolved_test = test_type

    if resolved_test == "t-test" and n_groups != 2:
        _render_alert("warning", "t-test requires exactly 2 groups. Use Auto or ANOVA for 3+ groups.")
        return

    if resolved_test == "ANOVA" and n_groups < 2:
        _render_alert("warning", "ANOVA requires at least 2 groups.")
        return

    if resolved_test == "t-test":
        group_names = list(temp[cat_col].unique())
        g1 = temp[temp[cat_col] == group_names[0]][num_col].dropna()
        g2 = temp[temp[cat_col] == group_names[1]][num_col].dropna()

        if len(g1) < 2 or len(g2) < 2:
            _render_alert("warning", "Each group must contain at least 2 valid values for the t-test.")
            return

        statistic, p_value = stats.ttest_ind(g1, g2, equal_var=False)
        effect_size = _cohens_d(g1, g2)
        effect_name = "Cohen's d"
        test_label = "Welch t-test"

    else:
        if not all(len(g) > 1 for g in grouped_values):
            _render_alert("warning", "Each group should contain at least 2 valid values for ANOVA.")
            return

        statistic, p_value = stats.f_oneway(*grouped_values)
        effect_size = _eta_squared_anova(grouped_values)
        effect_name = "eta squared"
        test_label = "One-way ANOVA"

    readiness = _validity_badge(valid_pct)

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        _render_test_kpi("Test", test_label, f"{n_groups} groups")

    with k2:
        _render_test_kpi("Statistic", _format_number(statistic), resolved_test)

    with k3:
        _render_test_kpi("p-value", _format_number(p_value, 4), _p_value_label(p_value))

    with k4:
        _render_test_kpi("Valid rows", _format_int(valid_rows), f"{valid_pct}% · {readiness}")

    tabs = st.tabs(["Result", "Groups", "Distribution", "Group prediction rule"])

    with tabs[0]:
        _render_current_config(
            title="Group mean comparison result",
            subtitle=f"<b>{num_col}</b> was compared across groups of <b>{cat_col}</b> using <b>{test_label}</b>.",
            badge=_p_value_label(p_value),
        )

        interpretation = _build_group_test_interpretation(
            num_col=num_col,
            cat_col=cat_col,
            test_name=test_label,
            statistic=statistic,
            p_value=p_value,
            effect_size_name=effect_name,
            effect_size_value=effect_size,
        )

        _render_alert("info", interpretation)

        if group_summary["count"].min() < 5:
            _render_alert(
                "warning",
                "At least one group has fewer than 5 observations. Results may be unstable.",
            )

    with tabs[1]:
        _render_section_title("Grouped descriptive statistics")
        st.dataframe(group_summary, use_container_width=True, hide_index=True)

    with tabs[2]:
        _render_section_title(
            "Distribution by group",
            "Boxplots help compare median, spread, and potential outliers across groups.",
        )

        fig = px.box(
            temp,
            x=cat_col,
            y=num_col,
            points="outliers",
            labels={cat_col: cat_col, num_col: num_col},
        )
        fig = _plot_layout(fig, 450, cat_col, num_col)

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=_safe_key("sttest_group_boxplot", num_col, cat_col, test_label),
        )

    with tabs[3]:
        _render_group_dependency_summary(
            group_summary=group_summary,
            num_col=num_col,
            cat_col=cat_col,
        )


# ============================================================
# MAIN STATISTICAL TESTS COMPONENT
# ============================================================

def render_statistical_tests(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown(
        """
        <div class="sttest-header">
            <div class="sttest-title">Statistical tests</div>
            <div class="sttest-subtitle">
                Run guided hypothesis tests for numeric associations, categorical associations,
                and group mean comparisons.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.warning("No valid dataframe is available for statistical testing.")
        return

    valid_cols = _get_valid_columns(df, cols_for_stats)

    if not valid_cols:
        st.warning("No valid columns are available for statistical testing.")
        return

    st.markdown('<div class="sttest-toolbar">', unsafe_allow_html=True)

    test_type = st.selectbox(
        "Test family",
        [
            "Correlation Test",
            "Chi-square Test",
            "Group Mean Comparison",
        ],
        key="test_family",
        help="Choose the type of statistical test you want to run.",
    )

    st.markdown(
        """
        <div class="sttest-small-muted">
            Statistical tests help detect patterns, but practical relevance also depends on effect size, sample size, and data quality.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if test_type == "Correlation Test":
        render_correlation_test_ui(df, valid_cols)

    elif test_type == "Chi-square Test":
        render_chi_square_test_ui(df, valid_cols)

    elif test_type == "Group Mean Comparison":
        render_group_mean_test_ui(df, valid_cols)