import matplotlib.pyplot as plt
import streamlit as st


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