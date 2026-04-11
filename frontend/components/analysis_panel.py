import streamlit as st

from components.analysis.global_summary import render_global_summary
from components.analysis.univariate_analysis import render_univariate_analysis
from components.analysis.bivariate_analysis import render_bivariate_analysis
from components.analysis.threevariate_analysis import render_three_variable_analysis
from components.analysis.multivariate_analysis import render_multivariate_analysis
from components.analysis.statistical_tests import render_statistical_tests


def render_analysis_panel():
    st.markdown("## Analysis")

    current_df = st.session_state.get("df")

    if current_df is None or current_df.empty:
        st.warning("The dataset is empty.")
        return

    # Exclude internal/comment column if present
    comment_col = st.session_state.get("COMMENT_COL", "comment")
    cols_for_stats = [c for c in current_df.columns if c != comment_col]

    if not cols_for_stats:
        st.warning("There are no analyzable columns.")
        return

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview",
        "Univariate Analysis",
        "Bivariate Analysis",
        "Three-Variable Analysis",
        "Multivariate Analysis",
        "Statistical Tests",
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