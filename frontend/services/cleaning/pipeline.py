import pandas as pd

from services.cleaning.transforms import apply_user_config

def run_cleaning_pipeline(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    return apply_user_config(df, config)