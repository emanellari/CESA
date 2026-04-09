import pandas as pd
import numpy as np


def detect_is_numeric(series, threshold=0.8):
    s_num = pd.to_numeric(series, errors="coerce")
    ratio = s_num.notna().mean()
    return ratio >= threshold, s_num


def safe_mode(series):
    m = series.mode(dropna=True)
    if m.empty:
        return None
    return m.iloc[0]


def describe_numeric(series_raw):
    s_num = pd.to_numeric(series_raw, errors="coerce")
    s_clean = s_num.dropna()

    total_count = len(series_raw)
    valid_count = int(s_clean.shape[0])
    missing_count = int(s_num.isna().sum())
    unique_count = int(s_clean.nunique())

    if s_clean.empty:
        return None

    q1 = float(s_clean.quantile(0.25))
    q2 = float(s_clean.quantile(0.50))
    q3 = float(s_clean.quantile(0.75))
    p5 = float(s_clean.quantile(0.05))
    p10 = float(s_clean.quantile(0.10))
    p90 = float(s_clean.quantile(0.90))
    p95 = float(s_clean.quantile(0.95))

    min_val = float(s_clean.min())
    max_val = float(s_clean.max())
    mean_val = float(s_clean.mean())
    median_val = float(s_clean.median())
    sum_val = float(s_clean.sum())
    var_val = float(s_clean.var()) if len(s_clean) > 1 else 0.0
    std_val = float(s_clean.std()) if len(s_clean) > 1 else 0.0
    range_val = float(max_val - min_val)
    iqr_val = float(q3 - q1)
    skew_val = float(s_clean.skew()) if len(s_clean) > 2 else None
    kurt_val = float(s_clean.kurt()) if len(s_clean) > 3 else None
    mad_val = float((s_clean - mean_val).abs().mean())

    mode_val = safe_mode(s_clean)
    mode_val = float(mode_val) if mode_val is not None else None

    zeros_val = int((s_clean == 0).sum())
    positives_val = int((s_clean > 0).sum())
    negatives_val = int((s_clean < 0).sum())

    cv_val = float(std_val / mean_val) if mean_val != 0 else None

    lower_iqr = q1 - 1.5 * iqr_val
    upper_iqr = q3 + 1.5 * iqr_val
    outliers_iqr = int(((s_clean < lower_iqr) | (s_clean > upper_iqr)).sum())

    return {
        "series_clean": s_clean,
        "count": valid_count,
        "total": total_count,
        "missing": missing_count,
        "unique": unique_count,
        "sum": sum_val,
        "mean": mean_val,
        "median": median_val,
        "mode": mode_val,
        "min": min_val,
        "max": max_val,
        "range": range_val,
        "variance": var_val,
        "std": std_val,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "iqr": iqr_val,
        "p5": p5,
        "p10": p10,
        "p90": p90,
        "p95": p95,
        "skewness": skew_val,
        "kurtosis": kurt_val,
        "mad": mad_val,
        "zeros": zeros_val,
        "positives": positives_val,
        "negatives": negatives_val,
        "coef_var": cv_val,
        "outliers_iqr": outliers_iqr,
        "lower_iqr_bound": lower_iqr,
        "upper_iqr_bound": upper_iqr,
    }


def describe_categorical(series_raw):
    s = series_raw.copy()
    missing_count = int(s.isna().sum())
    s_cat = s.fillna("(missing)").astype(str)

    freq = s_cat.value_counts(dropna=False)
    rel = (s_cat.value_counts(dropna=False, normalize=True) * 100).round(2)

    mode_val = safe_mode(s_cat)
    top_count = int(freq.iloc[0]) if len(freq) else 0
    top_pct = float(rel.iloc[0]) if len(rel) else 0.0

    rare_freq = freq[freq == freq.min()]
    rare_values = list(rare_freq.index)

    avg_len = float(s_cat.map(len).mean()) if len(s_cat) else 0.0
    min_len = int(s_cat.map(len).min()) if len(s_cat) else 0
    max_len = int(s_cat.map(len).max()) if len(s_cat) else 0

    out_df = pd.DataFrame({
        "category": freq.index,
        "count": freq.values,
        "percent": rel.values
    })

    return {
        "series_cat": s_cat,
        "count": int(s.notna().sum()),
        "total": int(len(s)),
        "missing": missing_count,
        "unique": int(s.nunique(dropna=True)),
        "mode": mode_val,
        "top_count": top_count,
        "top_percent": top_pct,
        "rare_values": rare_values,
        "avg_len": avg_len,
        "min_len": min_len,
        "max_len": max_len,
        "freq_df": out_df,
    }