import matplotlib.pyplot as plt
import streamlit as st
import plotly.express as px

def render_histogram(series, title, xlabel):
    fig = plt.figure()
    plt.hist(series, bins=10, edgecolor="black")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Frequency")
    plt.tight_layout()
    st.pyplot(fig)


def render_boxplot(series, title, ylabel):
    fig = plt.figure()
    plt.boxplot(series, vert=True)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    st.pyplot(fig)


def render_bar(categories, values, title, ylabel="Count"):
    fig = plt.figure()
    plt.bar(categories, values)
    plt.xticks(rotation=45, ha="right")
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    st.pyplot(fig)


def render_pie(values, labels, title):
    fig = plt.figure()
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title(title)
    plt.tight_layout()
    st.pyplot(fig)


def render_scatter(x, y, title, xlabel, ylabel):
    fig = plt.figure()
    plt.scatter(x, y)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    st.pyplot(fig)



def render_three_scatter_by_group(df, col_x, col_y, col_z, group_col="group"):

    required_cols = [col_x, col_y, col_z, group_col]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
        return

    if df.empty:
        st.warning("DataFrame is empty.")
        return


    fig = px.scatter_3d(
        df,
        x=col_x,
        y=col_y,
        z=col_z,
        color=group_col,
        opacity=0.8
    )

    fig.update_layout(
        margin=dict(l=0, r=0, b=0, t=30),
        legend_title_text=group_col
    )

    st.plotly_chart(fig, use_container_width=True)