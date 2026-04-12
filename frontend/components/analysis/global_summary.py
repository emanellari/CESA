import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from services.stat_service import detect_is_numeric


def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


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


def _render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    accent: str = "#2563eb",
    icon: str = "•"
):
    st.markdown(
        f"""
        <div class="gs-card kpi-card">
            <div class="kpi-top-line" style="background:{accent};"></div>
            <div class="kpi-header-row">
                <div class="kpi-title">{title}</div>
                <div class="kpi-icon" style="color:{accent};">{icon}</div>
            </div>
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
        padding: 1.35rem 1.35rem 1.1rem 1.35rem;
        border-radius: 22px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 55%, #eef6ff 100%);
        border: 1px solid #e5e7eb;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.055);
        margin-bottom: 1rem;
    }
    .gs-title {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.03em;
    }
    .gs-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        line-height: 1.55;
    }
    .gs-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 1rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .gs-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.07);
    }
    .kpi-card {
        min-height: 132px;
        position: relative;
        overflow: hidden;
    }
    .kpi-top-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.9rem;
    }
    .kpi-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.25rem;
    }
    .kpi-title {
        font-size: 0.84rem;
        font-weight: 700;
        color: #64748b;
        letter-spacing: 0.01em;
    }
    .kpi-icon {
        font-size: 1rem;
        font-weight: 700;
        opacity: 0.95;
    }
    .kpi-value {
        font-size: 1.85rem;
        line-height: 1.1;
        font-weight: 850;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.03em;
    }
    .kpi-subtitle {
        font-size: 0.82rem;
        color: #64748b;
    }
    .panel-title {
        font-size: 1.04rem;
        font-weight: 750;
        color: #0f172a;
        margin-bottom: 0.35rem;
    }
    .panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.85rem;
        line-height: 1.45;
    }
    .insight-box {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.9rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.7rem;
        color: #0f172a;
        font-size: 0.94rem;
        line-height: 1.5;
    }
    .success-box {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.9rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.7rem;
        color: #0f172a;
        font-size: 0.94rem;
        line-height: 1.5;
    }
    .warning-box {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.9rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.7rem;
        color: #0f172a;
        font-size: 0.94rem;
        line-height: 1.5;
    }
    .danger-box {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.9rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.7rem;
        color: #0f172a;
        font-size: 0.94rem;
        line-height: 1.5;
    }
    .badge {
        display: inline-block;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    .section-gap {
        height: 0.6rem;
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

    summary_df["Risk"] = summary_df["Missing %"].apply(
        lambda x: "High" if x >= 30 else "Medium" if x >= 10 else "Low"
    )

    numeric_count = int((summary_df["Detected type"] == "Numeric").sum())
    categorical_count = int((summary_df["Detected type"] == "Categorical").sum())

    quality_score = _compute_quality_score(summary_df)
    quality_text, quality_color = _quality_label(quality_score)

    high_missing = summary_df[summary_df["Missing %"] >= 30].copy()
    moderate_missing = summary_df[
        (summary_df["Missing %"] >= 10) & (summary_df["Missing %"] < 30)
    ].copy()
    high_cardinality = summary_df[
        (summary_df["Detected type"] == "Categorical") & (summary_df["Unique"] > 20)
    ].copy()

    if completeness == 100:
        quick_insight = "Dataset is fully complete with no missing values."
        quick_box = "success-box"
    elif completeness > 90:
        quick_insight = "Dataset is highly complete with only minor missingness."
        quick_box = "insight-box"
    else:
        quick_insight = "Dataset has noticeable missing data that may impact analysis quality."
        quick_box = "warning-box"

    st.markdown(
        f"""
        <div class="{quick_box}">
            <b>Quick insight:</b> {quick_insight}
        </div>
        """,
        unsafe_allow_html=True
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_kpi_card("Rows", f"{total_rows:,}", "Observations", "#2563eb", "▦")
    with k2:
        _render_kpi_card("Columns", f"{total_cols:,}", "Selected variables", "#0ea5e9", "◫")
    with k3:
        _render_kpi_card("Missing cells", f"{total_missing:,}", "Null / empty values", "#f59e0b", "!")
    with k4:
        _render_kpi_card("Completeness", f"{completeness}%", "Coverage across cells", "#16a34a", "✓")
    with k5:
        _render_kpi_card("Quality score", f"{quality_score}/100", quality_text, quality_color, "★")

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    tabs = st.tabs([
        "Overview",
        "Missingness",
        "Correlations",
        "Insights",
        "Suggested tests"
    ])

    with tabs[0]:
        left, right = st.columns([1.85, 1])

        with left:
            st.markdown('<div class="panel-title">Column summary</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-subtitle">Detected variable type, completeness, missingness risk, and cardinality.</div>',
                unsafe_allow_html=True
            )

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
                    "Risk": st.column_config.TextColumn("Risk", width="small"),
                }
            )

            st.download_button(
                "Download summary CSV",
                data=_to_csv_download_bytes(summary_df),
                file_name="dataset_summary.csv",
                mime="text/csv"
            )

        with right:
            st.markdown('<div class="panel-title">Schema balance</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-subtitle">Detected variable-type distribution.</div>',
                unsafe_allow_html=True
            )

            schema_df = pd.DataFrame({
                "Type": ["Numeric", "Categorical"],
                "Count": [numeric_count, categorical_count]
            })

            fig_schema = px.pie(
                schema_df,
                names="Type",
                values="Count",
                hole=0.62
            )
            fig_schema.update_traces(textposition="inside", textinfo="percent+label")
            fig_schema.update_layout(
                height=310,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=True
            )
            st.plotly_chart(fig_schema, use_container_width=True)

            dominant_type = "Numeric" if numeric_count > categorical_count else "Categorical"
            avg_missing = round(summary_df["Missing %"].mean(), 2)
            max_missing = round(summary_df["Missing %"].max(), 2)
            avg_unique = round(summary_df["Unique"].mean(), 2)

            st.markdown(
                f"""
                <div class="insight-box">
                    <b>Schema insight:</b> The dataset is dominated by <b>{dominant_type}</b> variables.
                </div>
                """,
                unsafe_allow_html=True
            )

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

    with tabs[1]:
        left, right = st.columns([1.65, 1])

        with left:
            st.markdown('<div class="panel-title">Missingness by column</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-subtitle">Ranking of variables by missing-value percentage.</div>',
                unsafe_allow_html=True
            )

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
                height=max(340, 42 * len(miss_plot_df)),
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Missing percentage",
                yaxis_title=""
            )
            st.plotly_chart(fig_missing, use_container_width=True)

        with right:
            st.markdown('<div class="panel-title">Data quality risks</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-subtitle">Potential structural issues worth checking before analysis.</div>',
                unsafe_allow_html=True
            )

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

    with tabs[2]:
        if len(numeric_cols_detected) >= 2:
            numeric_df = subset_df[numeric_cols_detected].apply(pd.to_numeric, errors="coerce")
            corr = numeric_df.corr(numeric_only=True)

            st.markdown('<div class="panel-title">Correlation matrix</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-subtitle">Linear relationships among detected numeric variables.</div>',
                unsafe_allow_html=True
            )

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
                            <b>Key relationship detected</b><br>
                            This is the strongest linear dependency in the dataset.<br><br>
                            <b>{strongest["Variable A"]}</b> ↔ <b>{strongest["Variable B"]}</b><br>
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

    with tabs[3]:
        st.markdown('<div class="panel-title">Automatic interpretation</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-subtitle">System-generated summary of dataset quality and analysis readiness.</div>',
            unsafe_allow_html=True
        )

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
            st.markdown(
                f"""
                <div class="insight-box">{txt}</div>
                """,
                unsafe_allow_html=True
            )

        if quality_score >= 85:
            recommendation = "Dataset is ready for modeling."
            box_cls = "success-box"
        elif quality_score >= 70:
            recommendation = "Minor preprocessing is recommended before modeling."
            box_cls = "warning-box"
        else:
            recommendation = "Significant preprocessing is required before reliable analysis."
            box_cls = "danger-box"

        st.markdown(
            f"""
            <div class="{box_cls}">
                <b>Recommendation:</b> {recommendation}
            </div>
            """,
            unsafe_allow_html=True
        )

    with tabs[4]:
        st.markdown('<div class="panel-title">Suggested next analyses</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-subtitle">Recommended statistical directions based on the detected dataset structure.</div>',
            unsafe_allow_html=True
        )

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
            st.markdown(
                f"""
                <div class="success-box">{step}</div>
                """,
                unsafe_allow_html=True
            )