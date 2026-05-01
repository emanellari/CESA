import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

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

    if abs(value) >= 1000:
        return f"{value:,.{decimals}f}"

    return f"{value:.{decimals}f}"


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

    return s_clean.mask(s_clean.str.lower().isin(missing_like), np.nan)


def _quality_badge_from_missing(missing_pct: float) -> str:
    if missing_pct <= 5:
        return "High completeness"
    if missing_pct <= 20:
        return "Moderate completeness"
    if missing_pct <= 40:
        return "Needs review"
    return "High missingness"


def _alert_type_from_missing(missing_pct: float) -> str:
    if missing_pct <= 5:
        return "success"
    if missing_pct <= 20:
        return "info"
    if missing_pct <= 40:
        return "warning"
    return "danger"


def _get_missing_message(missing_pct: float, prefix: str = "This variable") -> str:
    if missing_pct <= 5:
        return f"{prefix} has very high completeness. Missing data is unlikely to distort the analysis."

    if missing_pct <= 20:
        return f"{prefix} has some missing values, but it is still broadly usable for descriptive analysis."

    if missing_pct <= 40:
        return f"{prefix} has substantial missingness. Interpret summaries with caution."

    return f"{prefix} has high missingness. Consider imputation, exclusion, or special handling."


def _chart_height(n: int, minimum: int = 360, maximum: int = 520) -> int:
    return min(maximum, max(minimum, 260 + min(n, 12) * 18))


def _plot_layout(fig, height: int, x_title: str = "", y_title: str = ""):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=20, b=10),
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

    return [c for c in cols_for_stats if c in df.columns]


# ============================================================
# UI HELPERS
# ============================================================

def _render_mini_kpi(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="uv-card uv-kpi">
            <div class="uv-kpi-title">{title}</div>
            <div class="uv-kpi-value">{value}</div>
            <div class="uv-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alert(kind: str, message: str):
    valid_kinds = {"note", "info", "success", "warning", "danger"}
    kind = kind if kind in valid_kinds else "info"

    st.markdown(
        f"""
        <div class="uv-{kind}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stat_card(title: str, value: str, subtitle: str = ""):
    _render_mini_kpi(title, value, subtitle)


def _render_section_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="uv-panel-title">{title}</div>
        <div class="uv-panel-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# NUMERIC LOGIC
# ============================================================

def _numeric_stats(valid: pd.Series, total_n: int) -> dict:
    valid_n = len(valid)
    missing_n = total_n - valid_n
    missing_pct = _safe_pct(missing_n, total_n)

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = valid[(valid < lower_bound) | (valid > upper_bound)]

    return {
        "total_n": total_n,
        "valid_n": valid_n,
        "missing_n": int(missing_n),
        "missing_pct": missing_pct,
        "unique_n": int(valid.nunique()),
        "mean": float(valid.mean()),
        "median": float(valid.median()),
        "std": float(valid.std()) if valid_n > 1 else 0.0,
        "min": float(valid.min()),
        "max": float(valid.max()),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "range": float(valid.max() - valid.min()),
        "skew": float(valid.skew()) if valid_n > 2 else np.nan,
        "kurt": float(valid.kurt()) if valid_n > 3 else np.nan,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "outlier_count": int(len(outliers)),
        "outlier_pct": _safe_pct(len(outliers), valid_n),
    }


def _numeric_interpretation(col_name: str, stats: dict) -> list[str]:
    insights = [
        f"The variable <b>{col_name}</b> has <b>{stats['valid_n']:,}</b> valid numeric observations and <b>{stats['missing_n']:,}</b> missing or invalid values.",
        f"The central tendency is summarized by a mean of <b>{_format_number(stats['mean'])}</b> and a median of <b>{_format_number(stats['median'])}</b>.",
        f"The observed range goes from <b>{_format_number(stats['min'])}</b> to <b>{_format_number(stats['max'])}</b>, with an IQR of <b>{_format_number(stats['iqr'])}</b>.",
    ]

    skew = stats["skew"]

    if pd.notna(skew):
        if abs(skew) <= 0.5:
            insights.append("The distribution appears relatively balanced around its center.")
        elif skew > 0:
            insights.append("The distribution is tilted toward higher-end values with a right tail.")
        else:
            insights.append("The distribution is tilted toward lower-end values with a left tail.")

    if stats["outlier_count"] > 0:
        insights.append(
            f"IQR screening detected <b>{stats['outlier_count']:,}</b> potential outliers. Extreme values may influence the mean and standard deviation."
        )
    else:
        insights.append("No IQR-based outliers were detected, which supports a cleaner summary profile.")

    if stats["unique_n"] <= 5:
        insights.append(
            "Because the number of distinct numeric values is very low, the variable may be better treated as ordinal in some analyses."
        )

    return insights


def _numeric_next_steps(stats: dict) -> list[str]:
    steps = [
        "Compare mean and median to understand whether extreme values are pulling the average.",
        "Inspect the histogram and boxplot to evaluate skewness and possible outliers.",
        "Compare this variable against categorical groups using boxplots or group means.",
        "Compare it with another numeric variable using scatter plots and correlation.",
    ]

    if stats["missing_pct"] > 10:
        steps.append("Decide whether missing numeric values should be imputed, removed, or kept as-is.")

    if pd.notna(stats["skew"]) and abs(stats["skew"]) > 1:
        steps.append("Because skewness is strong, consider robust statistics or transformation before modeling.")

    if stats["outlier_count"] > 0:
        steps.append("Check whether outliers should be capped, kept, corrected, or investigated individually.")

    if stats["unique_n"] <= 5:
        steps.append("Consider whether this variable should instead be analyzed as ordinal or categorical.")

    return steps


# ============================================================
# NUMERIC UI
# ============================================================

def render_numeric_univariate(s: pd.Series, col_name: str):
    s_clean = _normalize_missing(s)
    s_num = pd.to_numeric(s_clean, errors="coerce")
    valid = s_num.dropna()
    total_n = len(s)

    _render_section_title(
        "Numeric variable overview",
        "Distribution, central tendency, spread, missingness, and potential outliers.",
    )

    if valid.empty:
        _render_alert(
            "danger",
            "No valid numeric values are available after conversion. This variable cannot be analyzed as numeric in its current form.",
        )
        return

    stats = _numeric_stats(valid, total_n)

    k1, k2, k3 = st.columns(3)

    with k1:
        _render_stat_card("Mean", _format_number(stats["mean"]), "Average value")

    with k2:
        _render_stat_card("Median", _format_number(stats["median"]), "Robust center")

    with k3:
        _render_stat_card(
            "Outliers",
            _format_int(stats["outlier_count"]),
            f'{stats["outlier_pct"]}% by IQR',
        )

    tabs = st.tabs(
        [
            "Summary",
            "Distribution",
            "Diagnostics",
        ]
    )

    with tabs[0]:
        left, right = st.columns([1.25, 1])

        with left:
            _render_section_title("Descriptive statistics")

            stats_df = pd.DataFrame(
                [
                    {"Metric": "Total rows", "Value": stats["total_n"]},
                    {"Metric": "Valid numeric values", "Value": stats["valid_n"]},
                    {"Metric": "Missing / invalid values", "Value": stats["missing_n"]},
                    {"Metric": "Missing / invalid %", "Value": f'{stats["missing_pct"]}%'},
                    {"Metric": "Unique values", "Value": stats["unique_n"]},
                    {"Metric": "Mean", "Value": round(stats["mean"], 6)},
                    {"Metric": "Median", "Value": round(stats["median"], 6)},
                    {"Metric": "Standard deviation", "Value": round(stats["std"], 6)},
                    {"Metric": "Minimum", "Value": round(stats["min"], 6)},
                    {"Metric": "Q1 (25%)", "Value": round(stats["q1"], 6)},
                    {"Metric": "Q3 (75%)", "Value": round(stats["q3"], 6)},
                    {"Metric": "Maximum", "Value": round(stats["max"], 6)},
                    {"Metric": "Range", "Value": round(stats["range"], 6)},
                    {"Metric": "IQR", "Value": round(stats["iqr"], 6)},
                ]
            )

            st.dataframe(stats_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Quick read")

            st.markdown(
                f"""
                <div class="uv-card">
                    <div class="uv-panel-subtitle">
                        <b>Range:</b> {_format_number(stats["range"])}<br>
                        <b>Q1:</b> {_format_number(stats["q1"])}<br>
                        <b>Q3:</b> {_format_number(stats["q3"])}<br>
                        <b>IQR:</b> {_format_number(stats["iqr"])}<br>
                        <b>Std. dev.:</b> {_format_number(stats["std"])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            missing_kind = _alert_type_from_missing(stats["missing_pct"])
            missing_message = _get_missing_message(
                stats["missing_pct"],
                "This numeric variable",
            )
            _render_alert(missing_kind, missing_message)

            if stats["unique_n"] <= 5:
                _render_alert(
                    "warning",
                    "This numeric variable has very few distinct values. It may behave more like an ordinal or grouped score.",
                )
            else:
                _render_alert(
                    "success",
                    "The variable has enough numeric variation for distributional analysis.",
                )

    with tabs[1]:
        c1, c2 = st.columns([1.35, 1])

        nbins = min(50, max(8, int(np.sqrt(stats["valid_n"]))))

        with c1:
            _render_section_title("Histogram")

            fig_hist = px.histogram(
                x=valid,
                nbins=nbins,
                labels={"x": col_name, "y": "Count"},
            )
            fig_hist = _plot_layout(fig_hist, 420, col_name, "Count")
            st.plotly_chart(fig_hist, use_container_width=True)

        with c2:
            _render_section_title("Boxplot")

            fig_box = px.box(
                y=valid,
                points="outliers",
                labels={"y": col_name},
            )
            fig_box = _plot_layout(fig_box, 420, "", col_name)
            st.plotly_chart(fig_box, use_container_width=True)

    with tabs[2]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title("Shape and outlier diagnostics")

            shape_df = pd.DataFrame(
                [
                    {
                        "Metric": "Skewness",
                        "Value": round(stats["skew"], 6)
                        if pd.notna(stats["skew"])
                        else None,
                    },
                    {
                        "Metric": "Kurtosis",
                        "Value": round(stats["kurt"], 6)
                        if pd.notna(stats["kurt"])
                        else None,
                    },
                    {"Metric": "Lower IQR bound", "Value": round(stats["lower_bound"], 6)},
                    {"Metric": "Upper IQR bound", "Value": round(stats["upper_bound"], 6)},
                    {"Metric": "Outlier count", "Value": stats["outlier_count"]},
                    {"Metric": "Outlier %", "Value": f'{stats["outlier_pct"]}%'},
                ]
            )

            st.dataframe(shape_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Diagnostic interpretation")

            skew_val = stats["skew"]

            if pd.notna(skew_val):
                if skew_val > 1:
                    _render_alert("warning", "The distribution appears strongly right-skewed.")
                elif skew_val < -1:
                    _render_alert("warning", "The distribution appears strongly left-skewed.")
                elif abs(skew_val) <= 0.5:
                    _render_alert("success", "The distribution appears relatively symmetric.")
                else:
                    _render_alert("info", "The distribution shows mild-to-moderate skewness.")

            if stats["outlier_pct"] == 0:
                _render_alert("success", "No IQR-based outliers were detected.")
            elif stats["outlier_pct"] <= 5:
                _render_alert("info", "A small proportion of IQR-based outliers was detected.")
            else:
                _render_alert("warning", "A notable share of potential outliers was detected.")

            kurt_val = stats["kurt"]

            if pd.notna(kurt_val):
                if kurt_val > 3:
                    _render_alert("info", "High kurtosis suggests heavier tails or more extreme values.")
                elif kurt_val < 0:
                    _render_alert("info", "Low kurtosis suggests a flatter distribution with lighter tails.")


# ============================================================
# CATEGORICAL LOGIC
# ============================================================

def _categorical_profile(s: pd.Series, top_n: int = 12) -> dict:
    s_cat = _normalize_missing(s.copy())
    total_n = len(s_cat)
    missing_n = int(s_cat.isna().sum())
    missing_pct = _safe_pct(missing_n, total_n)

    valid = s_cat.dropna().astype(str)
    valid_n = len(valid)
    unique_n = int(valid.nunique())

    if valid.empty:
        return {
            "empty": True,
            "total_n": total_n,
            "missing_n": missing_n,
            "missing_pct": missing_pct,
            "valid": valid,
        }

    freq = valid.value_counts(dropna=False)
    freq_df = freq.reset_index()
    freq_df.columns = ["Category", "Count"]
    freq_df["Percent"] = freq_df["Count"].apply(lambda x: _safe_pct(x, valid_n))

    top_category = str(freq_df.iloc[0]["Category"])
    top_count = int(freq_df.iloc[0]["Count"])
    top_pct = float(freq_df.iloc[0]["Percent"])

    rare_df = freq_df[freq_df["Percent"] < 5].copy()
    rare_count = int(len(rare_df))

    plot_df = freq_df.head(min(top_n, unique_n)).copy()

    return {
        "empty": False,
        "total_n": total_n,
        "valid": valid,
        "valid_n": valid_n,
        "missing_n": missing_n,
        "missing_pct": missing_pct,
        "unique_n": unique_n,
        "freq_df": freq_df,
        "plot_df": plot_df,
        "rare_df": rare_df,
        "rare_count": rare_count,
        "top_category": top_category,
        "top_count": top_count,
        "top_pct": top_pct,
    }


def _categorical_interpretation(col_name: str, profile: dict) -> list[str]:
    unique_n = profile["unique_n"]
    valid_n = profile["valid_n"]
    top_category = profile["top_category"]
    top_pct = profile["top_pct"]
    rare_count = profile["rare_count"]
    missing_pct = profile["missing_pct"]

    insights = [
        f"The variable <b>{col_name}</b> contains <b>{unique_n:,}</b> observed categories across <b>{valid_n:,}</b> valid values.",
        f"The most frequent category is <b>{top_category}</b>, representing <b>{top_pct}%</b> of non-missing entries.",
    ]

    if unique_n == 1:
        insights.append(
            "Because only one category is observed, the variable has almost no analytical value for segmentation or comparison."
        )
    elif unique_n <= 10:
        insights.append(
            "The number of categories is compact enough for direct visualization and clean summary reporting."
        )
    elif unique_n <= 20:
        insights.append(
            "The category count is moderate, so grouped summaries remain usable but should be designed carefully."
        )
    else:
        insights.append(
            "The variable has high cardinality, so raw charts may become cluttered and a grouping strategy may be helpful."
        )

    if rare_count > 0:
        insights.append(
            f"There are <b>{rare_count}</b> rare categories below 5%, which may reduce readability and statistical stability in later cross-analysis."
        )

    if missing_pct > 20:
        insights.append(
            "Missingness is large enough that category proportions should be interpreted with caution."
        )

    return insights


def _categorical_next_steps(profile: dict) -> list[str]:
    unique_n = profile["unique_n"]
    rare_count = profile["rare_count"]
    missing_pct = profile["missing_pct"]

    steps = [
        "Review category frequencies and percentages to understand dominant groups.",
        "Use this variable for segmentation in two-column analysis.",
        "Compare it with numeric variables using boxplots, violin plots, or group means.",
        "Compare it with another categorical variable using contingency tables and chi-square tests.",
    ]

    if unique_n > 20:
        steps.append("Consider grouping rare categories or focusing on the top categories for clearer visualization.")

    if rare_count > 0:
        steps.append("Consider grouping infrequent labels into an 'Other' bucket.")

    if missing_pct > 10:
        steps.append("Assess whether missing category values need an 'Unknown' group or should be excluded.")

    return steps


# ============================================================
# CATEGORICAL UI
# ============================================================

def render_categorical_univariate(s: pd.Series, col_name: str, top_n: int = 12):
    profile = _categorical_profile(s, top_n=top_n)

    _render_section_title(
        "Categorical variable overview",
        "Frequency structure, dominant categories, rare labels, and category readability.",
    )

    if profile["empty"]:
        _render_alert(
            "danger",
            "No valid categorical values are available. This variable cannot be analyzed categorically in its current form.",
        )
        return

    k1, k2, k3 = st.columns(3)

    with k1:
        _render_stat_card(
            "Top category",
            _truncate_text(profile["top_category"], 22),
            f"{profile['top_pct']}% of valid values",
        )

    with k2:
        _render_stat_card("Categories", _format_int(profile["unique_n"]), "Distinct labels")

    with k3:
        _render_stat_card("Rare categories", _format_int(profile["rare_count"]), "< 5% each")

    tabs = st.tabs(
        [
            "Frequencies",
            "Visual summary",
            "Diagnostics",
        ]
    )

    with tabs[0]:
        left, right = st.columns([1.25, 1])

        with left:
            _render_section_title("Frequency table")
            st.dataframe(profile["freq_df"], use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Quick read")

            st.markdown(
                f"""
                <div class="uv-card">
                    <div class="uv-panel-subtitle">
                        <b>Most frequent category:</b> {profile["top_category"]}<br>
                        <b>Count:</b> {profile["top_count"]:,}<br>
                        <b>Share:</b> {profile["top_pct"]}%<br>
                        <b>Total categories:</b> {profile["unique_n"]:,}<br>
                        <b>Rare categories:</b> {profile["rare_count"]:,}<br>
                        <b>Missing:</b> {profile["missing_n"]:,} ({profile["missing_pct"]}%)
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if profile["unique_n"] == 1:
                _render_alert(
                    "danger",
                    "Only one observed category exists, so the variable offers almost no segmentation value.",
                )
            elif profile["unique_n"] <= 10:
                _render_alert(
                    "success",
                    "The number of categories is manageable for direct analysis and clean visualization.",
                )
            elif profile["unique_n"] <= 20:
                _render_alert(
                    "info",
                    "The variable has moderate category diversity and can still be interpretable with careful plotting.",
                )
            else:
                _render_alert(
                    "warning",
                    "High cardinality may make charts cluttered. Consider grouping rare labels.",
                )

            if profile["missing_pct"] > 20:
                _render_alert(
                    "warning",
                    "Missingness is substantial, so category proportions may not fully reflect the full dataset.",
                )

    with tabs[1]:
        plot_df = profile["plot_df"]

        c1, c2 = st.columns([1.45, 0.9])

        with c1:
            _render_section_title("Top categories")

            fig_bar = px.bar(
                plot_df.sort_values("Count", ascending=True),
                x="Count",
                y="Category",
                orientation="h",
                text="Count",
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar = _plot_layout(
                fig_bar,
                _chart_height(len(plot_df)),
                "Count",
                "Category",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            _render_section_title("Category share")

            fig_pie = px.pie(
                plot_df,
                names="Category",
                values="Count",
                hole=0.58,
            )
            fig_pie = _plot_layout(fig_pie, _chart_height(len(plot_df)), "", "")
            st.plotly_chart(fig_pie, use_container_width=True)

    with tabs[2]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title("Cardinality diagnostics")

            cardinality_df = pd.DataFrame(
                [
                    {"Metric": "Total rows", "Value": profile["total_n"]},
                    {"Metric": "Valid values", "Value": profile["valid_n"]},
                    {"Metric": "Missing values", "Value": profile["missing_n"]},
                    {"Metric": "Missing %", "Value": f"{profile['missing_pct']}%"},
                    {"Metric": "Unique categories", "Value": profile["unique_n"]},
                    {"Metric": "Most frequent category", "Value": profile["top_category"]},
                    {"Metric": "Top category count", "Value": profile["top_count"]},
                    {"Metric": "Top category %", "Value": f"{profile['top_pct']}%"},
                    {"Metric": "Rare categories (<5%)", "Value": profile["rare_count"]},
                ]
            )

            st.dataframe(cardinality_df, use_container_width=True, hide_index=True)

            if profile["rare_count"] > 0:
                _render_section_title("Rare categories")
                st.dataframe(profile["rare_df"], use_container_width=True, hide_index=True)

        with right:
            _render_section_title("Diagnostic interpretation")

            if profile["unique_n"] == 1:
                _render_alert(
                    "danger",
                    "Only one category is present. This variable has no real discriminatory power.",
                )
            elif profile["unique_n"] > 20:
                _render_alert(
                    "warning",
                    "High cardinality suggests recoding, grouping, or top-N filtering before downstream analysis.",
                )
            else:
                _render_alert(
                    "success",
                    "Category count is manageable for descriptive and comparative analysis.",
                )

            if profile["top_pct"] >= 70:
                _render_alert(
                    "warning",
                    "One category dominates strongly, which may reduce segmentation usefulness.",
                )
            elif profile["top_pct"] >= 40:
                _render_alert(
                    "info",
                    "The variable has a visible dominant category, but still retains some diversity.",
                )
            else:
                _render_alert(
                    "success",
                    "Category distribution appears reasonably spread out.",
                )

            if profile["rare_count"] >= max(3, profile["unique_n"] * 0.4):
                _render_alert(
                    "warning",
                    "A large share of categories is rare, which can make plots noisy and contingency tables sparse.",
                )


# ============================================================
# MAIN UNIVARIATE COMPONENT
# ============================================================

def render_univariate_analysis(df: pd.DataFrame, cols_for_stats: list[str]):
    st.markdown(
        """
        <div class="uv-header">
            <div class="uv-title">Single column analysis</div>
            <div class="uv-subtitle">
                Select one variable and inspect its completeness, structure, distribution,
                diagnostics, interpretation, and recommended next steps.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.warning("No valid dataframe is available for single-column analysis.")
        return

    valid_cols = _get_valid_columns(df, cols_for_stats)

    if not valid_cols:
        st.warning("No columns are available for analysis.")
        return

    st.markdown('<div class="uv-toolbar">', unsafe_allow_html=True)

    top_left, top_mid, top_right = st.columns([1.6, 1, 1])

    with top_left:
        chosen_col = st.selectbox(
            "Column",
            valid_cols,
            key="chosen_col",
            help="Choose the variable you want to analyze.",
        )

    raw_s = df[chosen_col]
    s = _normalize_missing(raw_s)
    auto_is_num, s_num = detect_is_numeric(s)

    with top_mid:
        analysis_type = st.radio(
            "Analysis type",
            ["Auto", "Numeric", "Categorical"],
            horizontal=True,
            key="analysis_type_single",
            help="Use Auto unless the detected type does not match your analytical intent.",
        )

    with top_right:
        top_n = st.slider(
            "Top categories",
            min_value=5,
            max_value=30,
            value=12,
            step=1,
            help="Used only for categorical charts.",
        )

    st.markdown(
        """
        <div class="uv-small-muted">
            Auto detection is useful, but you can override it when a numeric-looking column is actually categorical or ordinal.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if analysis_type == "Auto":
        is_numeric = auto_is_num
        detection_source = "Automatic detection"
    else:
        is_numeric = analysis_type == "Numeric"
        detection_source = "Manual override"

    if is_numeric:
        usable_series = pd.to_numeric(s, errors="coerce")
        valid_values = usable_series.dropna()
        detected_label = "Numeric"
    else:
        usable_series = s
        valid_values = s.dropna()
        detected_label = "Categorical"

    non_null = int(valid_values.notna().sum())
    missing = int(len(s) - non_null)
    missing_pct = _safe_pct(missing, len(s))
    completeness_pct = round(100 - missing_pct, 2)
    unique = int(valid_values.nunique(dropna=True))
    badge_text = _quality_badge_from_missing(missing_pct)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        _render_mini_kpi("Variable", _truncate_text(chosen_col, 24), "Selected column")

    with k2:
        _render_mini_kpi("Type", detected_label, detection_source)

    with k3:
        _render_mini_kpi("Valid", _format_int(non_null), f"{completeness_pct}% complete")

    with k4:
        _render_mini_kpi("Missing", _format_int(missing), f"{missing_pct}%")

    with k5:
        _render_mini_kpi("Unique", _format_int(unique), badge_text)

    tabs = st.tabs(
        [
            "Analysis",
            "Interpretation",
            "Next steps",
            "Metadata",
        ]
    )

    with tabs[0]:
        st.markdown(
            f"""
            <div class="uv-card">
                <div class="uv-panel-title">Current configuration</div>
                <div class="uv-panel-subtitle">
                    Variable <b>{chosen_col}</b> is being analyzed as <b>{detected_label}</b>.
                    Detection mode: <b>{detection_source}</b>.
                </div>
                <div class="uv-badge">
                    {badge_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_numeric:
            render_numeric_univariate(raw_s, chosen_col)
        else:
            render_categorical_univariate(raw_s, chosen_col, top_n=top_n)

    with tabs[1]:
        _render_section_title(
            "Automatic interpretation",
            "A plain-language explanation of what this variable currently shows.",
        )

        if is_numeric:
            valid_num = pd.to_numeric(s, errors="coerce").dropna()

            if valid_num.empty:
                insights = [
                    "No valid numeric values are available after conversion, so numeric interpretation is not possible."
                ]
            else:
                stats = _numeric_stats(valid_num, len(s))
                insights = _numeric_interpretation(chosen_col, stats)
        else:
            profile = _categorical_profile(raw_s, top_n=top_n)

            if profile["empty"]:
                insights = [
                    "No valid non-null category values are available, so categorical interpretation is limited."
                ]
            else:
                insights = _categorical_interpretation(chosen_col, profile)

        insights.append(
            f"The selected analysis mode comes from <b>{'automatic detection' if analysis_type == 'Auto' else 'manual override'}</b>, "
            f"so interpretation should match the intended analytical role of the variable."
        )

        for txt in insights:
            _render_alert("info", txt)

    with tabs[2]:
        _render_section_title(
            "Suggested next steps",
            "Recommended follow-up actions based on this variable’s structure and quality.",
        )

        if is_numeric:
            valid_num = pd.to_numeric(s, errors="coerce").dropna()

            if valid_num.empty:
                steps = [
                    "Review the column values and confirm whether this variable should really be treated as numeric.",
                    "Check whether numeric values use commas, text labels, or special symbols that prevent conversion.",
                ]
            else:
                stats = _numeric_stats(valid_num, len(s))
                steps = _numeric_next_steps(stats)
        else:
            profile = _categorical_profile(raw_s, top_n=top_n)

            if profile["empty"]:
                steps = [
                    "Review whether the column contains only missing values or missing-like labels.",
                    "Consider whether this variable should be excluded or recoded before analysis.",
                ]
            else:
                steps = _categorical_next_steps(profile)

        for step in steps:
            _render_alert("success", step)

    with tabs[3]:
        left, right = st.columns([1.15, 1])

        with left:
            _render_section_title(
                "Variable metadata",
                "High-level structural profile of the selected column.",
            )

            meta_df = pd.DataFrame(
                [
                    {"Property": "Column name", "Value": chosen_col},
                    {"Property": "Analyzed as", "Value": detected_label},
                    {"Property": "Detection mode", "Value": detection_source},
                    {"Property": "Original dtype", "Value": str(raw_s.dtype)},
                    {"Property": "Rows", "Value": len(raw_s)},
                    {"Property": "Valid values", "Value": non_null},
                    {"Property": "Missing / invalid values", "Value": missing},
                    {"Property": "Missing / invalid %", "Value": f"{missing_pct}%"},
                    {"Property": "Completeness %", "Value": f"{completeness_pct}%"},
                    {"Property": "Unique values", "Value": unique},
                ]
            )

            st.dataframe(meta_df, use_container_width=True, hide_index=True)

        with right:
            _render_section_title(
                "Quick structural signals",
                "Signals that may affect interpretation and later tests.",
            )

            missing_kind = _alert_type_from_missing(missing_pct)
            missing_message = _get_missing_message(missing_pct)
            _render_alert(missing_kind, missing_message)

            if is_numeric:
                if unique <= 5:
                    _render_alert(
                        "warning",
                        "This variable is numeric but has very low distinct-value count. It may behave more like an ordinal or grouped variable.",
                    )
                else:
                    _render_alert(
                        "success",
                        "The variable has enough numeric variation for standard quantitative analysis.",
                    )
            else:
                if unique > 20:
                    _render_alert(
                        "warning",
                        "This categorical variable has high cardinality. Charts may need top-N filtering or grouped categories.",
                    )
                elif unique == 1:
                    _render_alert(
                        "danger",
                        "The variable contains only one observed category, so it provides almost no analytical discrimination.",
                    )
                else:
                    _render_alert(
                        "success",
                        "The variable has a manageable number of categories for descriptive analysis and plotting.",
                    )