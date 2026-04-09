import pandas as pd
import numpy as np


def fmt_metric(val, decimals=4):
    if val is None:
        return "-"
    try:
        if pd.isna(val):
            return "-"
    except Exception:
        pass

    if isinstance(val, (int, np.integer)):
        return str(int(val))
    if isinstance(val, (float, np.floating)):
        return f"{val:.{decimals}f}"
    return str(val)