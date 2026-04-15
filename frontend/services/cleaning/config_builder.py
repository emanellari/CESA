import pandas as pd

from services.cleaning.profiles import get_preserved_unique_values, detect_boolean_defaults


def generate_form_options_from_config(df: pd.DataFrame, config: dict) -> dict:
    options = {}

    for col, cfg in config.items():
        final_type = cfg.get("final_type")

        if final_type == "number":
            options[col] = {"type": "number", "options": []}

        elif final_type == "date":
            options[col] = {"type": "date", "options": []}

        elif final_type == "boolean":
            options[col] = {"type": "checkbox", "options": []}

        elif final_type == "categorical":
            if cfg.get("use_auto_choices", True):
                vals = get_preserved_unique_values(df[col])
            else:
                vals = [
                    x.strip()
                    for x in cfg.get("manual_choices_text", "").splitlines()
                    if x.strip()
                ]

            form_type = cfg.get("form_type", "select")
            if form_type not in ["select", "radio"]:
                form_type = "select"

            options[col] = {"type": form_type, "options": vals}

        else:
            options[col] = {"type": "text", "options": []}

    return options

def build_default_config(df: pd.DataFrame, profiles: dict) -> dict:
    config = {}

    for col in df.columns:
        p = profiles[col]
        inferred = p["inferred_type"]
        unique_values = p.get("unique_values", [])

        # defaults

        if inferred == "boolean_candidate":
            pass

        if inferred == "boolean":
            final_type = "boolean"
            form_type = "checkbox"

        elif inferred == "date_candidate":
            final_type = "date"
            form_type = "date"

        elif inferred == "number":
            final_type = "number"
            form_type = "number"

        elif inferred == "categorical" and len(unique_values)>4:
            final_type = "categorical"
            form_type = "select"

        elif inferred == "categorical" and len(unique_values)<=4:
            final_type = "categorical"
            form_type = "radio"

        else:
            final_type = "text"
            form_type = "text"

        true_default, false_default = detect_boolean_defaults(unique_values)

        config[col] = {
            "final_type": final_type,
            "form_type": form_type,
            "use_auto_choices": True,
            "null_strategy": "keep",
            "null_fill_value": "",
            "replacements": [],
            "replacements_text": "",
            "convert_to_date": inferred == "date_candidate",
            "convert_to_boolean": False,
            "true_value": true_default,
            "false_value": false_default,
            "other_values_strategy": "null",
            "manual_choices_text": "\n".join(str(v) for v in unique_values) if unique_values else "",
            "force_checkbox": False,
            "outlier_strategy": "none",
            "outlier_iqr_multiplier": 1.5,
            "outlier_zscore_threshold": 3.0
        }

    return config