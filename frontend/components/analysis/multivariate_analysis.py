import numpy as np
import pandas as pd
import plotly.express as px
import statsmodels.api as sm
import streamlit as st

from statsmodels.stats.outliers_influence import variance_inflation_factor

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

    return f"{value:,.{decimals}f}"


def _format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _truncate_text(value, max_len: int = 28) -> str:
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


def _get_valid_columns(df: pd.DataFrame, cols_for_stats: list[str]) -> list[str]:
    if not cols_for_stats:
        return list(df.columns)

    return [col for col in cols_for_stats if col in df.columns]


# ============================================================
# UI HELPERS
# ============================================================

def _render_mv_kpi(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="mv-card mv-kpi">
            <div class="mv-kpi-title">{title}</div>
            <div class="mv-kpi-value">{value}</div>
            <div class="mv-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str):
    valid_kinds = {"info", "success", "warning", "danger", "note"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="mv-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="mv-panel-title">{title}</div>
        <div class="mv-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_current_config(target: str, predictors: list[str], valid_pct: float):
    readiness = _quality_badge_from_validity(valid_pct)

    predictors_text = ", ".join(predictors)

    st.markdown(
        f"""
        <div class="mv-card">
            <div class="mv-panel-title">Current configuration</div>
            <div class="mv-panel-subtitle">
                Outcome: <b>{target}</b><br>
                Predictors: <b>{predictors_text}</b>
            </div>
            <div class="mv-badge">{readiness}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# NUMERIC COLUMN DETECTION
# ============================================================

def _get_numeric_columns(df: pd.DataFrame, valid_cols: list[str]) -> list[str]:
    numeric_cols = []

    for col in valid_cols:
        s = _normalize_missing(df[col])
        is_numeric, _ = detect_is_numeric(s)

        if is_numeric:
            numeric_cols.append(col)

    return numeric_cols


def _prepare_model_data(df: pd.DataFrame, target: str, predictors: list[str]) -> tuple[pd.DataFrame, int, int, float]:
    selected_cols = [target] + predictors
    temp = df[selected_cols].copy()

    for col in selected_cols:
        temp[col] = pd.to_numeric(_normalize_missing(temp[col]), errors="coerce")

    total_rows = len(temp)
    temp = temp.dropna()
    valid_rows = len(temp)
    valid_pct = _safe_pct(valid_rows, total_rows)

    return temp, total_rows, valid_rows, valid_pct


def _quality_badge_from_validity(valid_pct: float) -> str:
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


def _validity_message(valid_pct: float) -> str:
    if valid_pct >= 95:
        return "Data readiness is high. The regression uses nearly all available rows."

    if valid_pct >= 80:
        return "Data readiness is good. The model should remain broadly representative."

    if valid_pct >= 60:
        return "A notable share of rows is removed because of missing values. Interpret results with caution."

    return "Data readiness is low. The model may represent only a filtered subset of the dataset."


# ============================================================
# CORRELATION HELPERS
# ============================================================

def _correlation_strength(value: float) -> str:
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


def _build_correlation_pairs(corr: pd.DataFrame) -> pd.DataFrame:
    pairs = []
    cols = corr.columns.tolist()

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.loc[cols[i], cols[j]]

            if pd.notna(value):
                pairs.append(
                    {
                        "Variable 1": cols[i],
                        "Variable 2": cols[j],
                        "Correlation": value,
                        "Absolute correlation": abs(value),
                        "Strength": _correlation_strength(value),
                    }
                )

    if not pairs:
        return pd.DataFrame()

    pairs_df = pd.DataFrame(pairs)
    pairs_df = pairs_df.sort_values("Absolute correlation", ascending=False)
    pairs_df["Correlation"] = pairs_df["Correlation"].round(3)
    pairs_df["Absolute correlation"] = pairs_df["Absolute correlation"].round(3)

    return pairs_df


def render_correlation_interpretation(corr: pd.DataFrame):
    _render_section_title(
        "Correlation interpretation",
        "The strongest pairwise linear relationships among the selected numeric variables.",
    )

    if corr.empty or len(corr.columns) < 2:
        _render_alert("info", "Not enough numeric variables to interpret correlations.")
        return

    pairs_df = _build_correlation_pairs(corr)

    if pairs_df.empty:
        _render_alert("info", "No valid pairwise correlations were found.")
        return

    top = pairs_df.iloc[0]

    if top["Absolute correlation"] < 0.2:
        _render_alert(
            "info",
            "No clearly relevant linear correlations were detected among the selected numeric variables.",
        )
    else:
        direction = "positive" if top["Correlation"] > 0 else "negative"

        _render_alert(
            "info",
            f"The strongest observed linear relationship is between <b>{top['Variable 1']}</b> and "
            f"<b>{top['Variable 2']}</b>, with a <b>{direction}</b> correlation of "
            f"<b>{top['Correlation']:.3f}</b>. This is considered <b>{top['Strength']}</b>.",
        )

    st.dataframe(pairs_df, use_container_width=True, hide_index=True)


def render_correlation_matrix(temp: pd.DataFrame):
    corr = temp.corr(numeric_only=True)

    if corr.empty:
        _render_alert("warning", "No valid correlation matrix could be computed.")
        return corr

    tabs = st.tabs(["Heatmap", "Table", "Ranking"])

    with tabs[0]:
        fig = px.imshow(
            corr,
            text_auto=True,
            aspect="auto",
            zmin=-1,
            zmax=1,
            labels=dict(color="Correlation"),
        )
        fig = _plot_layout(fig, 460, "", "")
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.dataframe(corr.round(3), use_container_width=True)

    with tabs[2]:
        render_correlation_interpretation(corr)

    return corr


# ============================================================
# REGRESSION HELPERS
# ============================================================

def _fit_regression_model(temp: pd.DataFrame, target: str, predictors: list[str]):
    X = sm.add_constant(temp[predictors])
    y = temp[target]

    model = sm.OLS(y, X).fit()
    return model


def _build_coef_df(model) -> pd.DataFrame:
    conf = model.conf_int()

    coef_df = pd.DataFrame(
        {
            "Variable": model.params.index,
            "Coefficient": model.params.values,
            "p-value": model.pvalues.values,
            "CI Low": conf[0].values,
            "CI High": conf[1].values,
        }
    )

    coef_df["Significant"] = coef_df["p-value"].apply(
        lambda p: "Yes" if pd.notna(p) and p < 0.05 else "No"
    )

    return coef_df


def _build_vif_df(temp: pd.DataFrame, predictors: list[str]) -> pd.DataFrame:
    if len(predictors) < 2:
        return pd.DataFrame(
            [{"Variable": predictors[0], "VIF": np.nan, "Interpretation": "Only one predictor"}]
        )

    X = temp[predictors].copy()
    X = sm.add_constant(X)

    rows = []

    for index, col in enumerate(X.columns):
        if col == "const":
            continue

        try:
            vif_value = variance_inflation_factor(X.values, index)
        except Exception:
            vif_value = np.nan

        if pd.isna(vif_value):
            interpretation = "Unavailable"
        elif vif_value < 5:
            interpretation = "Low concern"
        elif vif_value < 10:
            interpretation = "Moderate concern"
        else:
            interpretation = "High concern"

        rows.append(
            {
                "Variable": col,
                "VIF": vif_value,
                "Interpretation": interpretation,
            }
        )

    vif_df = pd.DataFrame(rows)

    if not vif_df.empty:
        vif_df["VIF"] = vif_df["VIF"].round(3)

    return vif_df


def build_multivariate_interpretation(target: str, predictors: list[str], model, valid_rows: int) -> str:
    significant = []

    for var, pval in model.pvalues.items():
        if var == "const":
            continue

        if pd.notna(pval) and pval < 0.05:
            significant.append(var)

    if significant:
        sig_text = ", ".join(significant)
        sig_sentence = (
            f"The predictors showing statistically significant associations with <b>{target}</b> are: "
            f"<b>{sig_text}</b>."
        )
    else:
        sig_sentence = f"No predictor reached conventional statistical significance for <b>{target}</b>."

    if pd.notna(model.f_pvalue) and model.f_pvalue < 0.05:
        model_sentence = "The overall model is statistically significant."
    else:
        model_sentence = "The overall model is not statistically significant at the conventional 0.05 level."

    return (
        f"A multiple linear regression model was fitted with <b>{target}</b> as the outcome and "
        f"<b>{', '.join(predictors)}</b> as predictors, using <b>{valid_rows:,}</b> complete rows. "
        f"The model explains approximately <b>{model.rsquared:.1%}</b> of the variance in <b>{target}</b> "
        f"(adjusted R² = <b>{model.rsquared_adj:.1%}</b>). "
        f"{model_sentence} {sig_sentence}"
    )


def _build_model_next_steps(model, vif_df: pd.DataFrame, target: str) -> list[str]:
    steps = [
        "Review significant predictors, but also inspect effect size and confidence intervals.",
        "Use the residual plot to check whether residuals are randomly scattered around zero.",
        "Check whether the adjusted R² is meaningfully lower than R², which can indicate overfitting.",
    ]

    if not vif_df.empty and "VIF" in vif_df.columns:
        high_vif = vif_df[pd.to_numeric(vif_df["VIF"], errors="coerce") >= 10]

        if not high_vif.empty:
            steps.append(
                "High VIF values suggest possible multicollinearity. Consider removing or combining highly related predictors."
            )

    if pd.notna(model.f_pvalue) and model.f_pvalue >= 0.05:
        steps.append(
            f"The overall model is not statistically significant, so predictions for {target} should be interpreted cautiously."
        )

    return steps


# ============================================================
# MAIN COMPONENT
# ============================================================

def render_multivariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown(
        """
        <div class="mv-header">
            <div class="mv-title">Multivariate analysis</div>
            <div class="mv-subtitle">
                Build a multiple linear regression model, inspect correlations, review predictor effects,
                and diagnose model quality.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.warning("No valid dataframe is available for multivariate analysis.")
        return

    valid_cols = _get_valid_columns(df, cols_for_stats)
    numeric_cols = _get_numeric_columns(df, valid_cols)

    if len(numeric_cols) < 2:
        st.warning("At least two numeric variables are required for multivariate analysis.")
        return

    st.markdown('<div class="mv-toolbar">', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])

    with c1:
        target = st.selectbox(
            "Target variable",
            numeric_cols,
            key="multi_target",
            help="The outcome variable the model will try to explain.",
        )

    available_predictors = [col for col in numeric_cols if col != target]

    with c2:
        predictors = st.multiselect(
            "Predictor variables",
            available_predictors,
            default=available_predictors[: min(3, len(available_predictors))],
            key="multi_predictors",
            help="Choose one or more numeric predictors.",
        )

    st.markdown(
        """
        <div class="mv-small-muted">
            This module fits an OLS multiple linear regression using complete rows for the selected variables.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if not predictors:
        _render_alert("info", "Choose at least one predictor to run the model.")
        return

    temp, total_rows, valid_rows, valid_pct = _prepare_model_data(df, target, predictors)
    removed_rows = total_rows - valid_rows

    if valid_rows < 5:
        _render_alert(
            "warning",
            "Not enough complete rows for multivariate analysis. At least 5 valid rows are required.",
        )
        return

    if valid_rows <= len(predictors) + 1:
        _render_alert(
            "warning",
            "There are too many predictors for the number of valid rows. Reduce predictors or add more data.",
        )
        return

    model = _fit_regression_model(temp, target, predictors)
    coef_df = _build_coef_df(model)
    vif_df = _build_vif_df(temp, predictors)

    readiness = _quality_badge_from_validity(valid_pct)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_mv_kpi("Target", _truncate_text(target), "Outcome variable")

    with k2:
        _render_mv_kpi("Predictors", _format_int(len(predictors)), "Selected inputs")

    with k3:
        _render_mv_kpi("Valid rows", _format_int(valid_rows), f"{valid_pct}% · {readiness}")

    with k4:
        _render_mv_kpi("R²", _format_number(model.rsquared), "Variance explained")

    with k5:
        _render_mv_kpi("Adjusted R²", _format_number(model.rsquared_adj), "Adjusted fit")

    tabs = st.tabs(
        [
            "Overview",
            "Correlations",
            "Regression",
            "Diagnostics",
            "Interpretation",
            "Next steps",
        ]
    )

    with tabs[0]:
        _render_current_config(target, predictors, valid_pct)

        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title(
                "Model readiness",
                "How much data remains after removing missing values in the selected variables.",
            )

            readiness_df = pd.DataFrame(
                [
                    {"Metric": "Total rows", "Value": total_rows},
                    {"Metric": "Valid complete rows", "Value": valid_rows},
                    {"Metric": "Removed rows", "Value": removed_rows},
                    {"Metric": "Validity %", "Value": f"{valid_pct}%"},
                    {"Metric": "Target", "Value": target},
                    {"Metric": "Predictor count", "Value": len(predictors)},
                ]
            )

            st.dataframe(readiness_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Readiness signal")

            validity_kind = _alert_type_from_validity(valid_pct)
            validity_msg = _validity_message(valid_pct)
            _render_alert(validity_kind, validity_msg)

            if len(predictors) >= max(3, valid_rows // 5):
                _render_alert(
                    "warning",
                    "The model has many predictors relative to the number of valid rows. Interpret coefficients carefully.",
                )
            else:
                _render_alert(
                    "success",
                    "The predictor count appears reasonable relative to the available complete rows.",
                )

    with tabs[1]:
        _render_section_title(
            "Correlation analysis",
            "Pairwise correlations among the target and selected predictors.",
        )

        render_correlation_matrix(temp[[target] + predictors])

    with tabs[2]:
        _render_section_title(
            "Regression results",
            "Model fit, coefficients, confidence intervals, and multicollinearity checks.",
        )

        m1, m2, m3, m4 = st.columns(4)

        with m1:
            _render_mv_kpi("R²", _format_number(model.rsquared), "Variance explained")

        with m2:
            _render_mv_kpi("Adjusted R²", _format_number(model.rsquared_adj), "Adjusted model fit")

        with m3:
            model_p = _format_number(model.f_pvalue, 4) if pd.notna(model.f_pvalue) else "—"
            _render_mv_kpi("Model p-value", model_p, "Overall F-test")

        with m4:
            _render_mv_kpi("AIC", _format_number(model.aic), "Model comparison")

        sub_tabs = st.tabs(["Coefficients", "VIF", "Formula"])

        with sub_tabs[0]:
            st.dataframe(coef_df, use_container_width=True, hide_index=True)

        with sub_tabs[1]:
            st.dataframe(vif_df, use_container_width=True, hide_index=True)

            if not vif_df.empty:
                high_vif = vif_df[pd.to_numeric(vif_df["VIF"], errors="coerce") >= 10]

                if not high_vif.empty:
                    _render_alert(
                        "warning",
                        "Some predictors have high VIF values, which may indicate multicollinearity.",
                    )
                else:
                    _render_alert(
                        "success",
                        "VIF values do not show severe multicollinearity based on the usual threshold of 10.",
                    )

        with sub_tabs[2]:
            st.code(build_prediction_formula(model))

    with tabs[3]:
        _render_section_title(
            "Residual diagnostics",
            "Residuals should ideally be scattered around zero without a clear pattern.",
        )

        residual_df = pd.DataFrame(
            {
                "Fitted": model.fittedvalues,
                "Residuals": model.resid,
            }
        )

        c1, c2 = st.columns([1.2, 1])

        with c1:
            fig_res = px.scatter(
                residual_df,
                x="Fitted",
                y="Residuals",
                labels={"Fitted": "Fitted values", "Residuals": "Residuals"},
            )
            fig_res.add_hline(y=0)
            fig_res = _plot_layout(fig_res, 440, "Fitted values", "Residuals")
            st.plotly_chart(fig_res, use_container_width=True)

        with c2:
            fig_hist = px.histogram(
                residual_df,
                x="Residuals",
                nbins=min(40, max(8, int(np.sqrt(len(residual_df))))),
                labels={"Residuals": "Residuals"},
            )
            fig_hist = _plot_layout(fig_hist, 440, "Residuals", "Count")
            st.plotly_chart(fig_hist, use_container_width=True)

    with tabs[4]:
        _render_section_title(
            "Automatic interpretation",
            "Plain-language explanation of the fitted multivariate model.",
        )

        interpretation = build_multivariate_interpretation(
            target=target,
            predictors=predictors,
            model=model,
            valid_rows=valid_rows,
        )

        _render_alert("info", interpretation)

        significant_df = coef_df[
            (coef_df["Variable"] != "const")
            & (pd.to_numeric(coef_df["p-value"], errors="coerce") < 0.05)
        ]

        if significant_df.empty:
            _render_alert(
                "warning",
                "No individual predictor is statistically significant at the 0.05 level.",
            )
        else:
            sig_vars = ", ".join(significant_df["Variable"].tolist())
            _render_alert(
                "success",
                f"Significant predictors at the 0.05 level: <b>{sig_vars}</b>.",
            )

    with tabs[5]:
        _render_section_title(
            "Suggested next steps",
            "Recommended checks before using this model for conclusions or prediction.",
        )

        steps = _build_model_next_steps(model, vif_df, target)

        for step in steps:
            _render_alert("success", step)