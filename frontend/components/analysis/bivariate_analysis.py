import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from scipy import stats
import statsmodels.api as sm

from services.stat_service import detect_is_numeric
from utils.ui_helpers import build_prediction_formula


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

    if abs(value) >= 1000:
        return f"{value:,.{decimals}f}"

    return f"{value:.{decimals}f}"


def _format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


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

    return s_clean.mask(s_clean.str.lower().isin(missing_like), np.nan)


def _plot_layout(fig, height: int = 420, x_title: str = "", y_title: str = ""):
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


def _detected_pair_label(a_is_num: bool, b_is_num: bool) -> str:
    if a_is_num and b_is_num:
        return "Numeric vs Numeric"

    if (not a_is_num) and (not b_is_num):
        return "Categorical vs Categorical"

    return "Numeric vs Categorical"


def _quality_badge_from_pair_validity(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "High readiness"
    if valid_pct >= 80:
        return "Good readiness"
    if valid_pct >= 60:
        return "Moderate readiness"
    return "Low readiness"


def _alert_type_from_pair_validity(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "success"
    if valid_pct >= 80:
        return "info"
    if valid_pct >= 60:
        return "warning"
    return "danger"


def _association_strength_from_correlation(value: float) -> str:
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


def _association_strength_from_cramers_v(value: float) -> str:
    if pd.isna(value):
        return "undefined"

    if value < 0.1:
        return "very weak"
    if value < 0.3:
        return "weak"
    if value < 0.5:
        return "moderate"

    return "strong"


# ============================================================
# UI HELPERS
# ============================================================

def _render_bi_kpi(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="bi-card bi-kpi">
            <div class="bi-kpi-title">{title}</div>
            <div class="bi-kpi-value">{value}</div>
            <div class="bi-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str):
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="bi-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="bi-panel-title">{title}</div>
        <div class="bi-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_current_config(col_a: str, col_b: str, final_mode: str, decision_source: str, badge_text: str):
    st.markdown(
        f"""
        <div class="bi-card">
            <div class="bi-panel-title">Current configuration</div>
            <div class="bi-panel-subtitle">
                <b>{col_a}</b> and <b>{col_b}</b> are being analyzed as <b>{final_mode}</b>.
                Detection mode: <b>{decision_source}</b>.
            </div>
            <div class="bi-badge">{badge_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# METADATA / SUGGESTIONS
# ============================================================

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
    final_mode: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
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
        ]
    )


def _build_suggested_tests_for_pair(final_mode: str) -> pd.DataFrame:
    mapping = {
        "Numeric vs Numeric": [
            {
                "Scenario": "Linear association",
                "Suggested test / method": "Pearson correlation, scatter plot, trend line",
                "Why": "Quantify linear relationship between two numeric variables",
            },
            {
                "Scenario": "Monotonic association",
                "Suggested test / method": "Spearman correlation",
                "Why": "Useful when rank-order relation matters more than strict linearity",
            },
            {
                "Scenario": "Prediction",
                "Suggested test / method": "Simple linear regression",
                "Why": "Estimate the expected change in one variable from another",
            },
        ],
        "Categorical vs Categorical": [
            {
                "Scenario": "Association between groups",
                "Suggested test / method": "Contingency table, chi-square test",
                "Why": "Evaluate whether two categorical variables are independent",
            },
            {
                "Scenario": "Association strength",
                "Suggested test / method": "Cramér's V",
                "Why": "Measure how strong the categorical association is",
            },
            {
                "Scenario": "Group composition",
                "Suggested test / method": "Row/column percentages, stacked bars",
                "Why": "Compare category distribution across groups",
            },
        ],
        "Numeric vs Categorical": [
            {
                "Scenario": "Group comparison",
                "Suggested test / method": "Boxplot, grouped means, grouped medians",
                "Why": "Compare numeric distributions across categories",
            },
            {
                "Scenario": "Two groups",
                "Suggested test / method": "t-test",
                "Why": "Test whether two group means differ",
            },
            {
                "Scenario": "Three or more groups",
                "Suggested test / method": "ANOVA",
                "Why": "Test whether at least one group mean differs",
            },
        ],
    }

    return pd.DataFrame(mapping.get(final_mode, []))


# ============================================================
# NUMERIC VS NUMERIC
# ============================================================

def build_numeric_numeric_interpretation(
    col_a: str,
    col_b: str,
    pearson_r: float,
    pearson_p: float,
    slope: float,
    slope_ci_low: float,
    slope_ci_high: float,
    r_squared: float,
    n: int,
) -> str:
    strength = _association_strength_from_correlation(pearson_r)

    if pearson_r > 0:
        direction = "positive"
    elif pearson_r < 0:
        direction = "negative"
    else:
        direction = "no clear"

    significance = "statistically significant" if pearson_p < 0.05 else "not statistically significant"

    if slope_ci_low <= 0 <= slope_ci_high:
        ci_text = "The slope confidence interval includes 0, so the linear effect should be interpreted cautiously."
    else:
        ci_text = "The slope confidence interval does not include 0, which supports a non-zero linear trend."

    return (
        f"A <b>{strength}</b> {direction} linear relationship was observed between <b>{col_a}</b> and <b>{col_b}</b> "
        f"(Pearson r = <b>{pearson_r:.3f}</b>, p = <b>{pearson_p:.4g}</b>, n = <b>{n}</b>). "
        f"The fitted regression suggests that a one-unit increase in <b>{col_a}</b> is associated with an average "
        f"change of <b>{slope:.3f}</b> units in <b>{col_b}</b>. "
        f"The model explains approximately <b>{r_squared:.1%}</b> of the variance in <b>{col_b}</b>. "
        f"The result is <b>{significance}</b>. {ci_text}"
    )


def _compute_numeric_numeric(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    temp = pd.DataFrame(
        {
            col_a: pd.to_numeric(sa, errors="coerce"),
            col_b: pd.to_numeric(sb, errors="coerce"),
        }
    ).dropna()

    if len(temp) < 3:
        return None

    x = temp[col_a]
    y = temp[col_b]

    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)
    cov_val = x.cov(y)

    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()

    slope = float(model.params[col_a])
    intercept = float(model.params["const"])
    r_squared = float(model.rsquared)
    slope_p = float(model.pvalues[col_a])

    conf_int = model.conf_int()
    slope_ci_low = float(conf_int.loc[col_a, 0])
    slope_ci_high = float(conf_int.loc[col_a, 1])

    return {
        "temp": temp,
        "n": len(temp),
        "pearson_r": pearson_r,
        "pearson_p": pearson_p,
        "spearman_r": spearman_r,
        "spearman_p": spearman_p,
        "covariance": cov_val,
        "model": model,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "slope_p": slope_p,
        "slope_ci_low": slope_ci_low,
        "slope_ci_high": slope_ci_high,
    }


def render_numeric_numeric(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    _render_section_title(
        "Numeric vs Numeric",
        "Correlation, regression trend, variance explained, and residual diagnostics.",
    )

    result = _compute_numeric_numeric(sa, sb, col_a, col_b)

    if result is None:
        _render_alert("warning", "Not enough valid numeric observations. At least 3 paired numeric values are required.")
        return None

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        _render_bi_kpi("Pearson r", _format_number(result["pearson_r"]), _association_strength_from_correlation(result["pearson_r"]))

    with m2:
        _render_bi_kpi("Spearman ρ", _format_number(result["spearman_r"]), "Rank correlation")

    with m3:
        _render_bi_kpi("R²", _format_number(result["r_squared"]), "Variance explained")

    with m4:
        _render_bi_kpi("Slope", _format_number(result["slope"]), f"p = {_format_number(result['slope_p'], 4)}")

    tabs = st.tabs(["Scatter", "Residuals", "Details"])

    with tabs[0]:
        _render_section_title("Scatter plot with regression line")

        fig = px.scatter(
            result["temp"],
            x=col_a,
            y=col_b,
            trendline="ols",
            labels={col_a: col_a, col_b: col_b},
        )
        fig = _plot_layout(fig, 440, col_a, col_b)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        _render_section_title(
            "Residual plot",
            "Residuals should ideally be scattered around zero without a strong pattern.",
        )

        residual_df = pd.DataFrame(
            {
                "Fitted": result["model"].fittedvalues,
                "Residuals": result["model"].resid,
            }
        )

        fig_res = px.scatter(
            residual_df,
            x="Fitted",
            y="Residuals",
            labels={"Fitted": "Fitted values", "Residuals": "Residuals"},
        )
        fig_res.add_hline(y=0)
        fig_res = _plot_layout(fig_res, 420, "Fitted values", "Residuals")
        st.plotly_chart(fig_res, use_container_width=True)

    with tabs[2]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title("Detailed numeric results")

            details_df = pd.DataFrame(
                [
                    {"Metric": "Sample size", "Value": result["n"]},
                    {"Metric": "Pearson r", "Value": result["pearson_r"]},
                    {"Metric": "Pearson p-value", "Value": result["pearson_p"]},
                    {"Metric": "Spearman rho", "Value": result["spearman_r"]},
                    {"Metric": "Spearman p-value", "Value": result["spearman_p"]},
                    {"Metric": "Covariance", "Value": result["covariance"]},
                    {"Metric": "Slope", "Value": result["slope"]},
                    {"Metric": "Intercept", "Value": result["intercept"]},
                    {"Metric": "Slope p-value", "Value": result["slope_p"]},
                    {"Metric": "Slope CI low", "Value": result["slope_ci_low"]},
                    {"Metric": "Slope CI high", "Value": result["slope_ci_high"]},
                    {"Metric": "R-squared", "Value": result["r_squared"]},
                ]
            )

            st.dataframe(details_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Prediction formula")
            st.code(build_prediction_formula(result["model"]))

            interpretation = build_numeric_numeric_interpretation(
                col_a=col_a,
                col_b=col_b,
                pearson_r=result["pearson_r"],
                pearson_p=result["pearson_p"],
                slope=result["slope"],
                slope_ci_low=result["slope_ci_low"],
                slope_ci_high=result["slope_ci_high"],
                r_squared=result["r_squared"],
                n=result["n"],
            )

            _render_alert("info", interpretation)

    return result


# ============================================================
# NUMERIC VS CATEGORICAL
# ============================================================

def build_numeric_categorical_interpretation(
    group_summary: pd.DataFrame,
    num_col: str,
    cat_col: str,
    anova_p: float,
) -> str:
    top_row = group_summary.iloc[0]
    bottom_row = group_summary.iloc[-1]

    base = (
        f"The highest average <b>{num_col}</b> appears in <b>{top_row[cat_col]}</b> "
        f"(mean = <b>{top_row['mean']:.3f}</b>), while the lowest appears in <b>{bottom_row[cat_col]}</b> "
        f"(mean = <b>{bottom_row['mean']:.3f}</b>). "
    )

    if pd.notna(anova_p):
        if anova_p < 0.05:
            base += f"ANOVA suggests statistically significant mean differences across <b>{cat_col}</b> groups (p = <b>{anova_p:.4g}</b>)."
        else:
            base += f"ANOVA does not suggest statistically significant mean differences across <b>{cat_col}</b> groups (p = <b>{anova_p:.4g}</b>)."

    return base


def _compute_numeric_categorical(sa, sb, col_a, col_b, a_is_num):
    if a_is_num:
        num_col = col_a
        cat_col = col_b
        temp = pd.DataFrame(
            {
                "value": pd.to_numeric(sa, errors="coerce"),
                "category": _normalize_missing(sb).fillna("(missing)").astype(str),
            }
        )
    else:
        num_col = col_b
        cat_col = col_a
        temp = pd.DataFrame(
            {
                "value": pd.to_numeric(sb, errors="coerce"),
                "category": _normalize_missing(sa).fillna("(missing)").astype(str),
            }
        )

    n_before = len(temp)
    temp = temp.dropna(subset=["value"])
    n_after = len(temp)

    if temp.empty or temp["category"].nunique() < 2:
        return None

    group_summary = (
        temp.groupby("category")["value"]
        .agg(["count", "mean", "median", "min", "max", "std"])
        .reset_index()
        .rename(columns={"category": cat_col})
        .sort_values("mean", ascending=False)
    )

    grouped = [g["value"].values for _, g in temp.groupby("category")]
    anova_p = np.nan

    if len(grouped) >= 2 and all(len(g) > 1 for g in grouped):
        _, anova_p = stats.f_oneway(*grouped)

    return {
        "temp": temp,
        "num_col": num_col,
        "cat_col": cat_col,
        "n_before": n_before,
        "n_after": n_after,
        "groups": int(temp["category"].nunique()),
        "group_summary": group_summary,
        "anova_p": anova_p,
    }


def render_numeric_categorical(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str, a_is_num: bool):
    _render_section_title(
        "Numeric vs Categorical",
        "Grouped summaries, mean comparison, distribution by category, and ANOVA when applicable.",
    )

    result = _compute_numeric_categorical(sa, sb, col_a, col_b, a_is_num)

    if result is None:
        _render_alert("warning", "Not enough valid grouped data. This comparison requires a numeric variable and at least two category groups.")
        return None

    m1, m2, m3 = st.columns(3)

    with m1:
        _render_bi_kpi("Groups", _format_int(result["groups"]), result["cat_col"])

    with m2:
        _render_bi_kpi("Valid rows", _format_int(result["n_after"]), f"of {result['n_before']:,}")

    with m3:
        anova_value = f"{result['anova_p']:.4g}" if pd.notna(result["anova_p"]) else "—"
        _render_bi_kpi("ANOVA p-value", anova_value, "Mean difference test")

    tabs = st.tabs(["Summary", "Mean chart", "Boxplot"])

    with tabs[0]:
        left, right = st.columns([1.25, 1])

        with left:
            _render_section_title("Grouped descriptive statistics")
            st.dataframe(result["group_summary"], use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Interpretation")

            interpretation = build_numeric_categorical_interpretation(
                group_summary=result["group_summary"],
                num_col=result["num_col"],
                cat_col=result["cat_col"],
                anova_p=result["anova_p"],
            )

            _render_alert("info", interpretation)

            if result["groups"] > 20:
                _render_alert(
                    "warning",
                    "There are many groups. Consider grouping rare categories for a cleaner comparison.",
                )

    with tabs[1]:
        _render_section_title("Mean by category")

        fig_bar = px.bar(
            result["group_summary"].sort_values("mean", ascending=True),
            x="mean",
            y=result["cat_col"],
            orientation="h",
            text="mean",
            labels={"mean": f"Mean of {result['num_col']}", result["cat_col"]: result["cat_col"]},
        )
        fig_bar.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_bar = _plot_layout(fig_bar, 430, f"Mean of {result['num_col']}", result["cat_col"])
        st.plotly_chart(fig_bar, use_container_width=True)

    with tabs[2]:
        _render_section_title("Distribution by category")

        fig_box = px.box(
            result["temp"],
            x="category",
            y="value",
            points="outliers",
            labels={"category": result["cat_col"], "value": result["num_col"]},
        )
        fig_box = _plot_layout(fig_box, 440, result["cat_col"], result["num_col"])
        st.plotly_chart(fig_box, use_container_width=True)

    return result


# ============================================================
# CATEGORICAL VS CATEGORICAL
# ============================================================

def build_categorical_categorical_interpretation(
    col_a: str,
    col_b: str,
    p_value: float,
    cramers_v: float,
    low_expected: int,
) -> str:
    strength = _association_strength_from_cramers_v(cramers_v)

    if p_value < 0.05:
        significance = "a statistically significant association"
    else:
        significance = "no statistically significant association"

    expected_note = (
        f"There are <b>{low_expected}</b> cells with expected frequency below 5, so the chi-square approximation may be less reliable."
        if low_expected > 0
        else "Expected frequencies look acceptable for the chi-square approximation."
    )

    return (
        f"The analysis suggests <b>{significance}</b> between <b>{col_a}</b> and <b>{col_b}</b> "
        f"(Chi-square p = <b>{p_value:.4g}</b>). "
        f"The association strength based on Cramér's V is <b>{strength}</b>. "
        f"{expected_note}"
    )


def _compute_categorical_categorical(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    temp = pd.DataFrame(
        {
            col_a: _normalize_missing(sa).fillna("(missing)").astype(str),
            col_b: _normalize_missing(sb).fillna("(missing)").astype(str),
        }
    )

    if temp.empty:
        return None

    ctab = pd.crosstab(temp[col_a], temp[col_b])

    if ctab.empty:
        return None

    row_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="index") * 100
    col_pct = pd.crosstab(temp[col_a], temp[col_b], normalize="columns") * 100

    chi2, p_value, dof, expected = stats.chi2_contingency(ctab)

    n = ctab.to_numpy().sum()
    min_dim = min(ctab.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else np.nan
    low_expected = int((expected < 5).sum())

    expected_df = pd.DataFrame(expected, index=ctab.index, columns=ctab.columns)

    return {
        "temp": temp,
        "ctab": ctab,
        "row_pct": row_pct,
        "col_pct": col_pct,
        "chi2": chi2,
        "p_value": p_value,
        "dof": dof,
        "expected": expected_df,
        "cramers_v": cramers_v,
        "low_expected": low_expected,
    }


def render_categorical_categorical(sa: pd.Series, sb: pd.Series, col_a: str, col_b: str):
    _render_section_title(
        "Categorical vs Categorical",
        "Contingency tables, normalized proportions, chi-square testing, and association strength.",
    )

    result = _compute_categorical_categorical(sa, sb, col_a, col_b)

    if result is None:
        _render_alert("warning", "No valid contingency data is available for this pair.")
        return None

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        _render_bi_kpi("Chi-square", _format_number(result["chi2"]), "Association test")

    with m2:
        _render_bi_kpi("p-value", _format_number(result["p_value"], 4), "Significance")

    with m3:
        _render_bi_kpi("Cramér's V", _format_number(result["cramers_v"]), _association_strength_from_cramers_v(result["cramers_v"]))

    with m4:
        _render_bi_kpi("Low expected cells", _format_int(result["low_expected"]), "Reliability check")

    tabs = st.tabs(["Counts", "Percentages", "Heatmap", "Expected"])

    with tabs[0]:
        left, right = st.columns([1.25, 1])

        with left:
            _render_section_title("Contingency table")
            st.dataframe(result["ctab"], use_container_width=True)

        with right:
            _render_section_title("Interpretation")
            interpretation = build_categorical_categorical_interpretation(
                col_a=col_a,
                col_b=col_b,
                p_value=result["p_value"],
                cramers_v=result["cramers_v"],
                low_expected=result["low_expected"],
            )
            _render_alert("info", interpretation)

    with tabs[1]:
        c1, c2 = st.columns(2)

        with c1:
            _render_section_title("Row percentages")
            st.dataframe(result["row_pct"].round(2), use_container_width=True)

        with c2:
            _render_section_title("Column percentages")
            st.dataframe(result["col_pct"].round(2), use_container_width=True)

    with tabs[2]:
        _render_section_title("Heatmap")

        fig = px.imshow(
            result["ctab"],
            text_auto=True,
            aspect="auto",
            labels=dict(color="Count"),
        )
        fig = _plot_layout(fig, 460, col_b, col_a)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        _render_section_title(
            "Expected frequencies",
            "Used internally by the chi-square test. Very low expected counts can reduce reliability.",
        )
        st.dataframe(result["expected"].round(3), use_container_width=True)

    return result


# ============================================================
# MAIN INTERPRETATION / NEXT STEPS
# ============================================================

def _build_pair_interpretation(
    col_a: str,
    col_b: str,
    final_mode: str,
    mode: str,
    valid_pairs: int,
    total_rows: int,
    valid_pct: float,
    a_unique: int,
    b_unique: int,
) -> list[str]:
    insights = [
        f"The selected pair is <b>{col_a}</b> and <b>{col_b}</b>, with <b>{valid_pairs:,}</b> valid paired observations out of <b>{total_rows:,}</b> total rows.",
    ]

    if final_mode == "Numeric vs Numeric":
        insights.append(
            "Both variables are treated as numeric. The main focus is correlation, trend direction, regression fit, and possible outliers."
        )

        if a_unique <= 5 or b_unique <= 5:
            insights.append(
                "At least one numeric variable has very few distinct values, so the relationship may behave more like an ordinal comparison."
            )

    elif final_mode == "Categorical vs Categorical":
        insights.append(
            "Both variables are treated as categorical. The main focus is whether category membership in one variable is associated with the other."
        )

        if a_unique > 20 or b_unique > 20:
            insights.append(
                "At least one variable has many categories, which can create sparse contingency tables and crowded visuals."
            )
        else:
            insights.append(
                "The category structure appears manageable for contingency tables, proportions, and association testing."
            )

    elif final_mode == "Numeric vs Categorical":
        insights.append(
            "This pair is treated as numeric versus categorical. The main focus is whether the numeric distribution changes across groups."
        )

        if max(a_unique, b_unique) > 20:
            insights.append(
                "One side may have many levels, so group summaries may be clearer after grouping rare categories."
            )

    if valid_pct < 80:
        insights.append(
            "Pair completeness is reduced, so the relationship may reflect a filtered subset rather than the full dataset."
        )

    insights.append(
        f"The final analysis mode comes from <b>{'automatic detection' if mode == 'Auto' else 'manual override'}</b>, so interpretation should match the intended analytical role of each variable."
    )

    return insights


def _build_workflow_steps(final_mode: str) -> list[str]:
    if final_mode == "Numeric vs Numeric":
        return [
            "Inspect the scatter plot for linearity, clusters, curvature, and extreme points.",
            "Compare Pearson and Spearman correlations to understand linear versus rank-based association.",
            "Use the regression line if prediction or trend estimation matters.",
            "Review residuals to check whether the linear model looks reasonable.",
        ]

    if final_mode == "Categorical vs Categorical":
        return [
            "Start with the contingency table of counts.",
            "Inspect row and column percentages to understand category composition.",
            "Use chi-square to test whether the variables appear dependent.",
            "Use Cramér's V to judge the strength of the association.",
        ]

    if final_mode == "Numeric vs Categorical":
        return [
            "Inspect grouped summaries before interpreting statistical tests.",
            "Use boxplots to compare distribution, spread, and outliers across groups.",
            "Use ANOVA when there are three or more groups and assumptions are acceptable.",
            "If there are many rare categories, consolidate them before inference.",
        ]

    return []


# ============================================================
# MAIN COMPONENT
# ============================================================

def render_bivariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown(
        """
        <div class="bi-header">
            <div class="bi-title">Bivariate analysis</div>
            <div class="bi-subtitle">
                Select two variables and inspect their relationship with automatic type detection,
                readiness checks, interpretation, and method-specific diagnostics.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    st.markdown('<div class="bi-toolbar">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1.2, 1.1])

    with c1:
        col_a = st.selectbox(
            "Variable A",
            valid_cols,
            key="biv_col_a",
            help="First variable in the relationship.",
        )

    with c2:
        default_index_b = 1 if len(valid_cols) > 1 else 0
        col_b = st.selectbox(
            "Variable B",
            valid_cols,
            index=default_index_b,
            key="biv_col_b",
            help="Second variable in the relationship.",
        )

    with c3:
        mode = st.selectbox(
            "Analysis mode",
            [
                "Auto",
                "Numeric vs Numeric",
                "Categorical vs Categorical",
                "Numeric vs Categorical",
            ],
            key="biv_mode",
            help="Use Auto unless the detected type does not match your intended analysis.",
        )

    st.markdown(
        """
        <div class="bi-small-muted">
            Auto mode chooses the relationship type from detected column types. You can override it when the analytical meaning is different from the stored data type.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if col_a == col_b:
        _render_alert("info", "Choose two different variables to run a bivariate analysis.")
        return

    sa_raw = df[col_a]
    sb_raw = df[col_b]

    sa = _normalize_missing(sa_raw)
    sb = _normalize_missing(sb_raw)

    a_is_num, _ = detect_is_numeric(sa)
    b_is_num, _ = detect_is_numeric(sb)

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

    badge_text = _quality_badge_from_pair_validity(valid_pct)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_bi_kpi("Variable A", _truncate_text(col_a), a_label)

    with k2:
        _render_bi_kpi("Variable B", _truncate_text(col_b), b_label)

    with k3:
        _render_bi_kpi("Detected pair", auto_mode, decision_source)

    with k4:
        _render_bi_kpi("Valid pairs", _format_int(valid_pairs), f"{valid_pct}%")

    with k5:
        _render_bi_kpi("Final mode", final_mode, badge_text)

    tabs = st.tabs(
        [
            "Analysis",
            "Interpretation",
            "Next steps",
            "Metadata",
            "Suggested tests",
        ]
    )

    with tabs[0]:
        _render_current_config(
            col_a=col_a,
            col_b=col_b,
            final_mode=final_mode,
            decision_source=decision_source,
            badge_text=badge_text,
        )

        if valid_pairs == 0:
            _render_alert(
                "danger",
                "There are no valid paired observations after removing rows with missing values in either variable. Bivariate analysis cannot be computed.",
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
        _render_section_title(
            "Automatic interpretation",
            "Plain-language reading of the selected variable pair.",
        )

        insights = _build_pair_interpretation(
            col_a=col_a,
            col_b=col_b,
            final_mode=final_mode,
            mode=mode,
            valid_pairs=valid_pairs,
            total_rows=total_rows,
            valid_pct=valid_pct,
            a_unique=a_unique,
            b_unique=b_unique,
        )

        for insight in insights:
            _render_alert("info", insight)

    with tabs[2]:
        _render_section_title(
            "Suggested next steps",
            "Recommended workflow for this type of relationship.",
        )

        for step in _build_workflow_steps(final_mode):
            _render_alert("success", step)

        if valid_pct < 80:
            _render_alert(
                "warning",
                "Because pair completeness is below 80%, consider checking missingness before making strong conclusions.",
            )

    with tabs[3]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title(
                "Pair metadata",
                "Structural description of the selected variable pair.",
            )

            meta_df = _build_bivariate_meta_df(
                col_a=col_a,
                col_b=col_b,
                a_dtype=str(sa_raw.dtype),
                b_dtype=str(sb_raw.dtype),
                a_detected=a_label,
                b_detected=b_label,
                valid_pairs=valid_pairs,
                total_rows=total_rows,
                pair_missing=pair_missing,
                valid_pct=valid_pct,
                final_mode=final_mode,
            )

            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title(
                "Quick structural signals",
                "Readiness and potential issues before interpreting results.",
            )

            readiness_kind = _alert_type_from_pair_validity(valid_pct)

            if valid_pct >= 95:
                readiness_msg = "Pair completeness is very high, so this relationship can be analyzed with minimal missing-data concern."
            elif valid_pct >= 80:
                readiness_msg = "Pair completeness is good. The analysis should remain broadly reliable."
            elif valid_pct >= 60:
                readiness_msg = "A notable share of rows is excluded by missingness, so results may be less stable or less representative."
            else:
                readiness_msg = "Pair completeness is low. Relationship analysis should be interpreted with caution."

            _render_alert(readiness_kind, readiness_msg)

            if final_mode == "Numeric vs Numeric":
                _render_alert(
                    "success",
                    "This setup is appropriate for scatter plots, correlation, and trend estimation.",
                )

            elif final_mode == "Categorical vs Categorical":
                if a_unique > 20 or b_unique > 20:
                    _render_alert(
                        "warning",
                        "At least one categorical variable has high cardinality, which may produce sparse contingency tables and crowded charts.",
                    )
                else:
                    _render_alert(
                        "success",
                        "Category counts appear manageable for contingency analysis and normalized comparisons.",
                    )

            elif final_mode == "Numeric vs Categorical":
                cat_unique = b_unique if a_is_num else a_unique

                if cat_unique > 20:
                    _render_alert(
                        "warning",
                        "The categorical side has many levels. Group comparison may be clearer after grouping rare categories.",
                    )
                else:
                    _render_alert(
                        "success",
                        "This setup is suitable for comparing numeric distributions across groups.",
                    )

            st.markdown(
                f"""
                <div class="bi-card">
                    <div class="bi-panel-title">Variable profile</div>
                    <div class="bi-panel-subtitle">
                        <b>{col_a}</b>: {a_non_null:,} non-null, {a_unique:,} unique<br>
                        <b>{col_b}</b>: {b_non_null:,} non-null, {b_unique:,} unique
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tabs[4]:
        _render_section_title(
            "Suggested tests and methods",
            "Recommended statistical methods and visuals for the selected relationship type.",
        )

        tests_df = _build_suggested_tests_for_pair(final_mode)

        if tests_df.empty:
            st.info("No suggestions are available for the current pair configuration.")
        else:
            st.dataframe(tests_df, use_container_width=True, hide_index=True)