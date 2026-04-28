
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import statsmodels.api as sm

from services.stat_service import detect_is_numeric

from helpers import build_prediction_formula


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
    numeric_cols = df[cols_for_stats].select_dtypes(include=[np.number]).columns.tolist()

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
        st.markdown("#### Prediction Formula")
        st.code(build_prediction_formula(model))
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