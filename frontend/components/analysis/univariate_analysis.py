import pandas as pd
import streamlit as st
from services.stat_service import detect_is_numeric
import plotly.express as px
import numpy as np
def _safe_pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0

def _normalize_missing(s: pd.Series) -> pd.Series:
    s_clean = s.astype(str).str.strip().str.lower()

    return s_clean.replace(
        {
            "": np.nan,
            "na": np.nan,
            "n/a": np.nan,
            "n.a": np.nan,
            "null": np.nan,
            "none": np.nan,
        }
    )
def _render_stat_card(title: str, value: str, subtitle: str = "", accent: str = "#2563eb"):
    st.markdown(
        f"""
        <div class="uni-card uni-stat-card">
            <div class="uni-stat-line" style="background:{accent};"></div>
            <div class="uni-stat-title">{title}</div>
            <div class="uni-stat-value">{value}</div>
            <div class="uni-stat-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def _ensure_univariate_styles():
    st.markdown("""
    <style>
    .uni-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 0.95rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
    }
    .uni-stat-card {
        min-height: 112px;
        position: relative;
        overflow: hidden;
    }
    .uni-stat-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.75rem;
    }
    .uni-stat-title {
        font-size: 0.84rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 0.28rem;
    }
    .uni-stat-value {
        font-size: 1.45rem;
        line-height: 1.15;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.16rem;
    }
    .uni-stat-subtitle {
        font-size: 0.81rem;
        color: #64748b;
    }
    .uni-panel-title {
        font-size: 1.02rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.45rem;
    }
    .uni-panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.8rem;
    }
    .uni-info {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .uni-success {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .uni-warning {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    .uni-danger {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
    }
    </style>
    """, unsafe_allow_html=True)

def render_numeric_univariate(s: pd.Series, col_name: str):
    _ensure_univariate_styles()
    s_clean=_normalize_missing(s)
    s_num = pd.to_numeric(s_clean, errors="coerce")
    valid = s_num.dropna()

    total_n = len(s)
    valid_n = len(valid)
    missing_n = int(s_num.isna().sum())
    missing_pct = _safe_pct(missing_n, total_n)
    unique_n = int(valid.nunique())

    st.markdown('<div class="uni-panel-title">Numeric variable overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="uni-panel-subtitle">Distribution, spread, outlier profile, and statistical shape of the selected numeric variable.</div>', unsafe_allow_html=True)

    if valid.empty:
        st.markdown(
            """
            <div class="uni-danger">
                No valid numeric values are available after conversion. This variable cannot be analyzed as numeric in its current form.
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    mean_val = float(valid.mean())
    median_val = float(valid.median())
    std_val = float(valid.std()) if len(valid) > 1 else 0.0
    min_val = float(valid.min())
    max_val = float(valid.max())
    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1
    skew_val = float(valid.skew()) if len(valid) > 2 else np.nan
    kurt_val = float(valid.kurt()) if len(valid) > 3 else np.nan

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = valid[(valid < lower_bound) | (valid > upper_bound)]
    outlier_count = int(len(outliers))
    outlier_pct = _safe_pct(outlier_count, valid_n)

    k3, k4, k5 = st.columns(3)

    with k3:
        _render_stat_card("Mean", f"{mean_val:,.3f}", "Average", "#16a34a")
    with k4:
        _render_stat_card("Median", f"{median_val:,.3f}", "Central value", "#0ea5e9")
    with k5:
        _render_stat_card("Outliers", f"{outlier_count:,}", f"{outlier_pct}% by IQR", "#dc2626")

    tabs = st.tabs([
        "Summary statistics",
        "Distribution",
        "Shape & outliers",
        "Interpretation"
    ])

    with tabs[0]:
        left, right = st.columns([1.2, 1])

        with left:
            st.markdown('<div class="uni-panel-title">Descriptive statistics</div>', unsafe_allow_html=True)

            stats_df = pd.DataFrame([
                {"Metric": "Count", "Value": valid_n},
                {"Metric": "Missing", "Value": missing_n},
                {"Metric": "Missing %", "Value": missing_pct},
                {"Metric": "Unique values", "Value": unique_n},
                {"Metric": "Mean", "Value": round(mean_val, 6)},
                {"Metric": "Median", "Value": round(median_val, 6)},
                {"Metric": "Standard deviation", "Value": round(std_val, 6)},
                {"Metric": "Minimum", "Value": round(min_val, 6)},
                {"Metric": "Q1 (25%)", "Value": round(q1, 6)},
                {"Metric": "Q3 (75%)", "Value": round(q3, 6)},
                {"Metric": "Maximum", "Value": round(max_val, 6)},
                {"Metric": "IQR", "Value": round(iqr, 6)},
            ])
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="uni-panel-title">Quick read</div>', unsafe_allow_html=True)

            range_val = max_val - min_val

            st.markdown(
                f"""
                <div class="uni-card">
                    <div class="uni-panel-subtitle">
                        <b>Range:</b> {range_val:,.3f}<br>
                        <b>Q1:</b> {q1:,.3f}<br>
                        <b>Q3:</b> {q3:,.3f}<br>
                        <b>IQR:</b> {iqr:,.3f}<br>
                        <b>Std. dev.:</b> {std_val:,.3f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if missing_pct <= 5:
                st.markdown('<div class="uni-success">Completeness is strong, so descriptive statistics should be fairly stable.</div>', unsafe_allow_html=True)
            elif missing_pct <= 20:
                st.markdown('<div class="uni-info">Some missing data exists, but the variable is still broadly usable.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-warning">Missingness is substantial and may affect the representativeness of summary statistics.</div>', unsafe_allow_html=True)

            if unique_n <= 5:
                st.markdown('<div class="uni-warning">This numeric variable has very few distinct values and may behave more like an ordinal or grouped score.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-success">The variable has enough numeric variation for distributional analysis.</div>', unsafe_allow_html=True)

    with tabs[1]:
        c1, c2 = st.columns([1.35, 1])

        with c1:
            st.markdown('<div class="uni-panel-title">Histogram</div>', unsafe_allow_html=True)
            fig_hist = px.histogram(
                x=valid,
                nbins=min(40, max(10, int(np.sqrt(valid_n)))),
                labels={"x": col_name, "y": "Count"}
            )
            fig_hist.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title=col_name,
                yaxis_title="Count"
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        with c2:
            st.markdown('<div class="uni-panel-title">Boxplot</div>', unsafe_allow_html=True)
            fig_box = px.box(
                y=valid,
                points="outliers",
                labels={"y": col_name}
            )
            fig_box.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title=col_name,
                xaxis_title=""
            )
            st.plotly_chart(fig_box, use_container_width=True)

    with tabs[2]:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown('<div class="uni-panel-title">Shape diagnostics</div>', unsafe_allow_html=True)

            shape_df = pd.DataFrame([
                {"Metric": "Skewness", "Value": round(skew_val, 6) if pd.notna(skew_val) else None},
                {"Metric": "Kurtosis", "Value": round(kurt_val, 6) if pd.notna(kurt_val) else None},
                {"Metric": "Lower IQR bound", "Value": round(lower_bound, 6)},
                {"Metric": "Upper IQR bound", "Value": round(upper_bound, 6)},
                {"Metric": "Outlier count", "Value": outlier_count},
                {"Metric": "Outlier %", "Value": outlier_pct},
            ])
            st.dataframe(shape_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="uni-panel-title">Diagnostic interpretation</div>', unsafe_allow_html=True)

            if pd.notna(skew_val):
                if skew_val > 1:
                    st.markdown('<div class="uni-warning">The distribution appears strongly right-skewed.</div>', unsafe_allow_html=True)
                elif skew_val < -1:
                    st.markdown('<div class="uni-warning">The distribution appears strongly left-skewed.</div>', unsafe_allow_html=True)
                elif abs(skew_val) <= 0.5:
                    st.markdown('<div class="uni-success">The distribution appears relatively symmetric.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="uni-info">The distribution shows mild-to-moderate skewness.</div>', unsafe_allow_html=True)

            if outlier_pct == 0:
                st.markdown('<div class="uni-success">No IQR-based outliers were detected.</div>', unsafe_allow_html=True)
            elif outlier_pct <= 5:
                st.markdown('<div class="uni-info">A small proportion of IQR-based outliers was detected.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-warning">The variable contains a notable share of potential outliers.</div>', unsafe_allow_html=True)

            if pd.notna(kurt_val):
                if kurt_val > 3:
                    st.markdown('<div class="uni-info">High kurtosis suggests heavier tails or more extreme values than a normal-like shape.</div>', unsafe_allow_html=True)
                elif kurt_val < 0:
                    st.markdown('<div class="uni-info">Low kurtosis suggests a flatter distribution with lighter tails.</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="uni-panel-title">Automatic interpretation</div>', unsafe_allow_html=True)

        insights = [
            f"The variable <b>{col_name}</b> has <b>{valid_n:,}</b> valid numeric observations and <b>{missing_n:,}</b> missing values.",
            f"The central tendency is summarized by a mean of <b>{mean_val:,.3f}</b> and a median of <b>{median_val:,.3f}</b>.",
            f"The observed range goes from <b>{min_val:,.3f}</b> to <b>{max_val:,.3f}</b>, with an IQR of <b>{iqr:,.3f}</b>.",
        ]

        if pd.notna(skew_val):
            if abs(skew_val) <= 0.5:
                insights.append("The distribution appears relatively balanced around its center.")
            elif skew_val > 0:
                insights.append("The distribution is tilted toward higher-end values with a right tail.")
            else:
                insights.append("The distribution is tilted toward lower-end values with a left tail.")

        if outlier_count > 0:
            insights.append(f"IQR screening detected <b>{outlier_count}</b> potential outliers, so extreme values may influence the mean and standard deviation.")
        else:
            insights.append("No IQR-based outliers were detected, which supports a cleaner summary profile.")

        if unique_n <= 5:
            insights.append("Because the number of distinct values is very low, the variable may be better treated as ordinal in some analyses.")

        for item in insights:
            st.markdown(f'<div class="uni-info">{item}</div>', unsafe_allow_html=True)

        st.markdown('<div class="uni-panel-title">Suggested next steps</div>', unsafe_allow_html=True)
        next_steps = [
            "Compare this variable against a categorical field using boxplots and group means.",
            "Compare it with another numeric variable using scatter plots and correlation.",
            "Check whether outliers should be capped, kept, or investigated.",
            "If the variable is skewed, consider transformation or robust statistics."
        ]
        for step in next_steps:
            st.markdown(f'<div class="uni-success">{step}</div>', unsafe_allow_html=True)

def render_categorical_univariate(s: pd.Series, col_name: str, top_n: int = 12):
    _ensure_univariate_styles()

    s_cat = _normalize_missing(s.copy())
    total_n = len(s_cat)
    missing_n = int(s_cat.isna().sum())
    missing_pct = _safe_pct(missing_n, total_n)

    valid = s_cat.dropna().astype(str)
    valid_n = len(valid)
    unique_n = int(valid.nunique())

    st.markdown('<div class="uni-panel-title">Categorical variable overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="uni-panel-subtitle">Frequency structure, category concentration, rarity profile, and readability diagnostics.</div>', unsafe_allow_html=True)

    if valid.empty:
        st.markdown(
            """
            <div class="uni-danger">
                No valid categorical values are available. This variable cannot be analyzed categorically in its current form.
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    freq = valid.value_counts(dropna=False)
    freq_df = freq.reset_index()
    freq_df.columns = ["Category", "Count"]
    freq_df["Percent"] = freq_df["Count"].apply(lambda x: _safe_pct(x, valid_n))

    top_category = str(freq_df.iloc[0]["Category"])
    top_count = int(freq_df.iloc[0]["Count"])
    top_pct = float(freq_df.iloc[0]["Percent"])

    rare_df = freq_df[freq_df["Percent"] < 5].copy()
    rare_count = int(len(rare_df))

    k4, k5 = st.columns(2)
    with k4:
        _render_stat_card("Top category", top_category[:18] + ("..." if len(top_category) > 18 else ""), f"{top_pct}%", "#0ea5e9")
    with k5:
        _render_stat_card("Rare categories", f"{rare_count:,}", "< 5% each", "#dc2626")

    tabs = st.tabs([
        "Frequencies",
        "Visual summary",
        "Cardinality & rarity",
        "Interpretation"
    ])

    with tabs[0]:
        left, right = st.columns([1.2, 1])

        with left:
            st.markdown('<div class="uni-panel-title">Frequency table</div>', unsafe_allow_html=True)
            st.dataframe(freq_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="uni-panel-title">Quick read</div>', unsafe_allow_html=True)

            st.markdown(
                f"""
                <div class="uni-card">
                    <div class="uni-panel-subtitle">
                        <b>Most frequent category:</b> {top_category}<br>
                        <b>Count:</b> {top_count:,}<br>
                        <b>Share:</b> {top_pct}%<br>
                        <b>Total categories:</b> {unique_n:,}<br>
                        <b>Rare categories:</b> {rare_count:,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if unique_n == 1:
                st.markdown('<div class="uni-danger">Only one observed category exists, so the variable offers almost no segmentation value.</div>', unsafe_allow_html=True)
            elif unique_n <= 10:
                st.markdown('<div class="uni-success">The number of categories is manageable for direct analysis and clean visualization.</div>', unsafe_allow_html=True)
            elif unique_n <= 20:
                st.markdown('<div class="uni-info">The variable has moderate category diversity and may still be interpretable with careful plotting.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-warning">High cardinality may make charts cluttered and may require grouping or top-category filtering.</div>', unsafe_allow_html=True)

            if missing_pct > 20:
                st.markdown('<div class="uni-warning">Missingness is substantial, so category proportions may not fully reflect the full dataset.</div>', unsafe_allow_html=True)

    with tabs[1]:
        c1, c2 = st.columns([1.35, 1])

        plot_df = freq_df.head(top_n).copy()

        with c1:
            st.markdown('<div class="uni-panel-title">Top categories bar chart</div>', unsafe_allow_html=True)
            fig_bar = px.bar(
                plot_df,
                x="Category",
                y="Count",
                text="Count"
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Category",
                yaxis_title="Count"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            st.markdown('<div class="uni-panel-title">Top categories share</div>', unsafe_allow_html=True)
            fig_pie = px.pie(
                plot_df,
                names="Category",
                values="Count",
                hole=0.58
            )
            fig_pie.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with tabs[2]:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown('<div class="uni-panel-title">Cardinality diagnostics</div>', unsafe_allow_html=True)

            cardinality_df = pd.DataFrame([
                {"Metric": "Valid values", "Value": valid_n},
                {"Metric": "Missing values", "Value": missing_n},
                {"Metric": "Missing %", "Value": missing_pct},
                {"Metric": "Unique categories", "Value": unique_n},
                {"Metric": "Most frequent category", "Value": top_category},
                {"Metric": "Top category %", "Value": top_pct},
                {"Metric": "Rare categories (<5%)", "Value": rare_count},
            ])
            st.dataframe(cardinality_df, use_container_width=True, hide_index=True)

            if rare_count > 0:
                st.markdown('<div class="uni-panel-title">Rare categories</div>', unsafe_allow_html=True)
                st.dataframe(rare_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="uni-panel-title">Diagnostic interpretation</div>', unsafe_allow_html=True)

            if unique_n == 1:
                st.markdown('<div class="uni-danger">Only one category is present, so this variable has no real discriminatory power.</div>', unsafe_allow_html=True)
            elif unique_n > 20:
                st.markdown('<div class="uni-warning">High cardinality suggests recoding, grouping, or top-N filtering before downstream analysis.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-success">Category count is manageable for descriptive and comparative analysis.</div>', unsafe_allow_html=True)

            if top_pct >= 70:
                st.markdown('<div class="uni-warning">One category dominates the variable strongly, which may reduce segmentation usefulness.</div>', unsafe_allow_html=True)
            elif top_pct >= 40:
                st.markdown('<div class="uni-info">The variable has a visible dominant category, but still retains some diversity.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="uni-success">Category distribution appears reasonably spread out.</div>', unsafe_allow_html=True)

            if rare_count >= max(3, unique_n * 0.4):
                st.markdown('<div class="uni-warning">A large share of categories is rare, which can make plots noisy and contingency tables sparse.</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="uni-panel-title">Automatic interpretation</div>', unsafe_allow_html=True)

        insights = [
            f"The variable <b>{col_name}</b> contains <b>{unique_n:,}</b> observed categories across <b>{valid_n:,}</b> valid values.",
            f"The most frequent category is <b>{top_category}</b>, representing <b>{top_pct}%</b> of non-missing entries.",
        ]

        if unique_n == 1:
            insights.append("Because only one category is observed, the variable has almost no analytical value for segmentation or comparison.")
        elif unique_n <= 10:
            insights.append("The number of categories is compact enough for direct visualization and clean summary reporting.")
        elif unique_n <= 20:
            insights.append("The category count is moderate, so grouped summaries remain usable but should be designed carefully.")
        else:
            insights.append("The variable has high cardinality, so raw charts may become cluttered and some grouping strategy may be helpful.")

        if rare_count > 0:
            insights.append(f"There are <b>{rare_count}</b> rare categories below 5%, which may dilute readability and statistical stability in later cross-analysis.")

        if missing_pct > 20:
            insights.append("Missingness is large enough that category proportions should be interpreted with caution.")

        for item in insights:
            st.markdown(f'<div class="uni-info">{item}</div>', unsafe_allow_html=True)

        st.markdown('<div class="uni-panel-title">Suggested next steps</div>', unsafe_allow_html=True)
        next_steps = [
            "Use this variable for segmentation in two-column analysis.",
            "Compare it with numeric variables using boxplots, violin plots, or group means.",
            "Compare it with another categorical variable using contingency tables and chi-square tests.",
            "If there are many rare categories, consider grouping infrequent labels into an 'Other' bucket."
        ]
        for step in next_steps:
            st.markdown(f'<div class="uni-success">{step}</div>', unsafe_allow_html=True)

def _render_mini_kpi(title: str, value: str, subtitle: str = "", accent: str = "#2563eb"):
    st.markdown(
        f"""
        <div class="uv-card uv-kpi">
            <div class="uv-kpi-line" style="background:{accent};"></div>
            <div class="uv-kpi-title">{title}</div>
            <div class="uv-kpi-value">{value}</div>
            <div class="uv-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def _quality_badge_from_missing(missing_pct: float) -> tuple[str, str]:
    if missing_pct <= 5:
        return "High completeness", "#16a34a"
    if missing_pct <= 20:
        return "Moderate completeness", "#2563eb"
    if missing_pct <= 40:
        return "Needs review", "#f59e0b"
    return "High missingness", "#dc2626"

def _ensure_uv_styles():
    st.markdown("""
    <style>
    .uv-header {
        padding: 1.15rem 1.25rem 1rem 1.25rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 55%, #eef6ff 100%);
        border: 1px solid #e5e7eb;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }
    .uv-title {
        font-size: 1.45rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .uv-subtitle {
        color: #64748b;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    .uv-card {
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 0.95rem 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .uv-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.07);
    }
    .uv-kpi {
        min-height: 118px;
        position: relative;
        overflow: hidden;
    }
    .uv-kpi-line {
        height: 4px;
        width: 100%;
        border-radius: 999px;
        margin-bottom: 0.75rem;
    }
    .uv-kpi-title {
        font-size: 0.84rem;
        font-weight: 700;
        color: #64748b;
        margin-bottom: 0.28rem;
    }
    .uv-kpi-value {
        font-size: 1.48rem;
        line-height: 1.1;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.16rem;
        letter-spacing: -0.02em;
    }
    .uv-kpi-subtitle {
        font-size: 0.81rem;
        color: #64748b;
    }
    .uv-panel-title {
        font-size: 1.02rem;
        font-weight: 750;
        color: #0f172a;
        margin-bottom: 0.4rem;
    }
    .uv-panel-subtitle {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.8rem;
        line-height: 1.45;
    }
    .uv-info {
        border-left: 4px solid #2563eb;
        background: #f8fbff;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
        line-height: 1.5;
    }
    .uv-success {
        border-left: 4px solid #16a34a;
        background: #f6fdf8;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
        line-height: 1.5;
    }
    .uv-warning {
        border-left: 4px solid #f59e0b;
        background: #fffaf0;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
        line-height: 1.5;
    }
    .uv-danger {
        border-left: 4px solid #dc2626;
        background: #fff7f7;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.65rem;
        color: #0f172a;
        font-size: 0.93rem;
        line-height: 1.5;
    }
    .uv-badge {
        display: inline-block;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    </style>
    """, unsafe_allow_html=True)
def render_univariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    _ensure_uv_styles()
    st.markdown("""
    <div class="uv-header">
        <div class="uv-title">Single column analysis</div>
        <div class="uv-subtitle">
            Detailed univariate analysis for one selected variable, including type detection,
            completeness profile, structure diagnostics, and analysis-specific recommendations.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df is None or df.empty:
        st.warning("No valid dataframe is available for single-column analysis.")
        return

    if not cols_for_stats:
        st.warning("No columns are available for analysis.")
        return

    valid_cols = [c for c in cols_for_stats if c in df.columns]
    if not valid_cols:
        st.warning("None of the selected columns exist in the dataframe.")
        return

    top_left, top_right = st.columns([1.3, 1])

    with top_left:
        chosen_col = st.selectbox(
            "Select a column",
            valid_cols,
            key="chosen_col"
        )

    s =_normalize_missing( df[chosen_col])
    auto_is_num, s_num = detect_is_numeric(s)

    with top_right:
        analysis_type = st.radio(
            "Detected as",
            ["Auto", "Numeric", "Categorical"],
            horizontal=True,
            key="analysis_type_single"
        )

    if analysis_type == "Auto":
        is_numeric = auto_is_num
        detection_source = "Automatic detection"
    else:
        is_numeric = analysis_type == "Numeric"
        detection_source = "Manual override"

    non_null = int(s.notna().sum())
    missing = int(s.isna().sum())
    missing_pct = _safe_pct(missing, len(s))
    completeness_pct = round(100 - missing_pct, 2)
    unique = int(s.nunique(dropna=True))

    if is_numeric:
        usable_series = s_num
        valid_values = usable_series.dropna()
        detected_label = "Numeric"
    else:
        usable_series = s
        valid_values = s.dropna()
        detected_label = "Categorical"

    badge_text, badge_color = _quality_badge_from_missing(missing_pct)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        _render_mini_kpi("Variable", chosen_col, "Selected field", "#2563eb")
    with k2:
        _render_mini_kpi("Analysis type", detected_label, detection_source, "#0ea5e9")
    with k3:
        _render_mini_kpi("Non-null", f"{non_null:,}", "Available values", "#16a34a")
    with k4:
        _render_mini_kpi("Missing", f"{missing:,}", f"{missing_pct}%", "#f59e0b")
    with k5:
        _render_mini_kpi("Unique", f"{unique:,}", "Distinct values", badge_color)

    tabs = st.tabs([
        "Analysis",
        "Metadata",
        "Interpretation",
        "Suggested next steps"
    ])

    with tabs[0]:
        st.markdown(
            f"""
            <div class="uv-card" style="margin-bottom: 0.9rem;">
                <div class="uv-panel-title">Current configuration</div>
                <div class="uv-panel-subtitle">
                    Variable <b>{chosen_col}</b> is being analyzed as <b>{detected_label}</b>.
                </div>
                <div class="uv-badge" style="background:{badge_color}18;color:{badge_color};border:1px solid {badge_color}40;">
                    {badge_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if is_numeric:
            render_numeric_univariate(s, chosen_col)
        else:
            render_categorical_univariate(s, chosen_col)

    with tabs[1]:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown('<div class="uv-panel-title">Variable metadata</div>', unsafe_allow_html=True)
            st.markdown('<div class="uv-panel-subtitle">High-level structural profile of the selected column.</div>', unsafe_allow_html=True)

            meta_df = pd.DataFrame([
                {"Property": "Column name", "Value": chosen_col},
                {"Property": "Analyzed as", "Value": detected_label},
                {"Property": "Detection mode", "Value": detection_source},
                {"Property": "Original dtype", "Value": str(s.dtype)},
                {"Property": "Rows", "Value": len(s)},
                {"Property": "Non-null values", "Value": non_null},
                {"Property": "Missing values", "Value": missing},
                {"Property": "Missing %", "Value": f"{missing_pct}%"},
                {"Property": "Completeness %", "Value": f"{completeness_pct}%"},
                {"Property": "Unique values", "Value": unique},
            ])

            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown('<div class="uv-panel-title">Quick structural signals</div>', unsafe_allow_html=True)
            st.markdown('<div class="uv-panel-subtitle">Signals that may affect interpretation and later tests.</div>', unsafe_allow_html=True)

            if missing_pct <= 5:
                st.markdown(
                    """
                    <div class="uv-success">
                        The variable has very high completeness, so missing data is unlikely to distort interpretation.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif missing_pct <= 20:
                st.markdown(
                    """
                    <div class="uv-info">
                        The variable has some missing values, but analysis is still likely to be reliable with minimal preprocessing.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif missing_pct <= 40:
                st.markdown(
                    """
                    <div class="uv-warning">
                        Missingness is substantial. Interpretation should account for possible bias or reduced sample size.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class="uv-danger">
                        Missingness is high. This variable may require imputation, exclusion, or special handling.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if is_numeric:
                if unique <= 5:
                    st.markdown(
                        """
                        <div class="uv-warning">
                            This variable is numeric but has very low distinct-value count. It may behave more like an ordinal or grouped variable.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
                        <div class="uv-success">
                            The variable has enough numeric variation for standard univariate quantitative analysis.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                if unique > 20:
                    st.markdown(
                        """
                        <div class="uv-warning">
                            This categorical variable has high cardinality, which may make charts harder to read and aggregation less stable.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                elif unique == 1:
                    st.markdown(
                        """
                        <div class="uv-danger">
                            The variable contains only one observed category, so it provides almost no analytical discrimination.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
                        <div class="uv-success">
                            The variable has a manageable number of categories for descriptive analysis and plotting.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    with tabs[2]:
        st.markdown('<div class="uv-panel-title">Automatic interpretation</div>', unsafe_allow_html=True)
        st.markdown('<div class="uv-panel-subtitle">System-generated narrative for the selected variable.</div>', unsafe_allow_html=True)

        insights = []

        if is_numeric:
            valid_num = s_num.dropna()

            if valid_num.empty:
                insights.append("No valid numeric values are available after conversion, so numeric interpretation is not possible.")
            else:
                insights.append(f"The variable is currently treated as numeric, with {len(valid_num):,} valid numeric observations.")

                if missing_pct <= 5:
                    insights.append("Completeness is strong, so summary statistics should be relatively stable.")
                elif missing_pct <= 20:
                    insights.append("Some missing data is present, but the variable remains usable for most descriptive analyses.")
                else:
                    insights.append("Missingness is substantial and may weaken conclusions or reduce the effective sample size.")

                if unique <= 5:
                    insights.append("Although numeric, the variable has very few unique values, so it may represent ordered levels, scores, or grouped bins rather than a continuous measure.")
                elif unique <= 20:
                    insights.append("The variable has moderate variation, which is suitable for distributions, comparisons, and simple trend inspection.")
                else:
                    insights.append("The variable has broad variation, making it suitable for rich distributional analysis and later relationship testing.")
        else:
            valid_cat = s.dropna()

            if valid_cat.empty:
                insights.append("No valid non-null category values are available, so categorical interpretation is limited.")
            else:
                insights.append(f"The variable is currently treated as categorical, with {len(valid_cat):,} non-null observations.")

                if unique == 1:
                    insights.append("Only one observed category is present, so the variable carries almost no segmentation value.")
                elif unique <= 10:
                    insights.append("The number of categories is manageable, which is good for frequency analysis and visual summaries.")
                elif unique <= 20:
                    insights.append("The variable has moderate category diversity, which may still be usable for grouped analysis with careful visualization.")
                else:
                    insights.append("The variable has high cardinality, so top-category filtering or recoding may be needed for readable results.")

                if missing_pct > 20:
                    insights.append("Missingness is large enough that category frequencies may not fully reflect the real structure of the data.")

        insights.append(
            f"The selected analysis mode comes from {'automatic detection' if analysis_type == 'Auto' else 'manual override'}, "
            f"so interpretation should be aligned with the intended analytical role of the variable."
        )

        for txt in insights:
            st.markdown(f'<div class="uv-info">{txt}</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="uv-panel-title">Suggested next steps</div>', unsafe_allow_html=True)
        st.markdown('<div class="uv-panel-subtitle">Recommended follow-up analyses for this variable.</div>', unsafe_allow_html=True)

        steps = []

        if is_numeric:
            steps.append("Review summary statistics such as mean, median, standard deviation, min, and max.")
            steps.append("Inspect the distribution with histogram and boxplot to identify skewness and possible outliers.")
            if missing_pct > 10:
                steps.append("Decide whether missing numeric values should be imputed, removed, or kept as-is depending on the use case.")
            if unique <= 5:
                steps.append("Consider whether this variable should instead be analyzed as ordinal or categorical.")
            steps.append("Use this variable later in two-column analysis against categorical groups or other numeric variables.")
        else:
            steps.append("Review category frequencies and percentages to understand the dominant groups.")
            if unique > 20:
                steps.append("Consider grouping rare categories or focusing on the top categories for clearer visualization.")
            if missing_pct > 10:
                steps.append("Assess whether missing category values need a separate 'Unknown' group or should be excluded.")
            if unique >= 2:
                steps.append("Use this variable later for segmentation, contingency tables, or group comparison analysis.")
            else:
                steps.append("Because only one category is present, this variable has limited value for comparison tasks.")

        for step in steps:
            st.markdown(f'<div class="uv-success">{step}</div>', unsafe_allow_html=True)
