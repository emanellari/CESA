import pandas as pd

def normalize_string_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()

def get_mode_value(series: pd.Series):
    s = series.dropna()
    if s.empty:
        return ""
    mode = s.mode()
    return mode.iloc[0] if not mode.empty else ""

def get_median_value(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 0
    return float(s.median())

def safe_strip_value(value):
    return value.strip() if isinstance(value, str) else value

def detect_boolean_defaults(unique_values: list) -> tuple[str, str]:

    if not unique_values or len(unique_values) < 2:
        return "", ""

    normalized_map = {}
    for v in unique_values:
        normalized_map[str(v).strip().lower()] = v

    known_pairs = [
        # English
        ("true", "false"),
        ("yes", "no"),
        ("y", "n"),
        ("1", "0"),
        ("t", "f"),

        # Albanian
        ("po", "jo"),

        # Spanish
        ("si", "no"),
        ("sí", "no"),
        ("verdadero", "falso"),

        # Italian
        ("si", "no"),
        ("vero", "falso"),

        # French
        ("oui", "non"),
        ("vrai", "faux"),

        # German
        ("ja", "nein"),
        ("wahr", "falsch"),

        # Portuguese
        ("sim", "nao"),
        ("não", "sim"),
        ("verdadeiro", "falso"),

        # Turkish
        ("evet", "hayir"),
        ("hayır", "evet"),

        # Dutch
        ("ja", "nee"),
        ("waar", "onwaar"),

        # Swedish
        ("ja", "nej"),
        ("sant", "falskt"),

        # Danish
        ("ja", "nej"),
        ("sand", "falsk"),

        # Norwegian
        ("ja", "nei"),
        ("sann", "usann"),

        # Finnish
        ("kylla", "ei"),
        ("kyllä", "ei"),
        ("tosi", "epatosi"),
        ("tosi", "epätosi"),

        # Polish
        ("tak", "nie"),
        ("prawda", "falsz"),
        ("prawda", "fałsz"),

        # Czech / Slovak
        ("ano", "ne"),
        ("pravda", "nepravda"),

        # Romanian
        ("da", "nu"),
        ("adevarat", "fals"),
        ("adevărat", "fals"),

        # Hungarian
        ("igen", "nem"),
        ("igaz", "hamis"),

        # Russian
        ("da", "net"),
        ("pravda", "lozh"),
        ("правда", "ложь"),
        ("да", "нет"),

        # Greek
        ("nai", "oxi"),
        ("ναι", "όχι"),
        ("alithes", "psema"),
        ("αληθες", "ψευδές"),

        # Arabic
        ("naam", "la"),
        ("نعم", "لا"),
        ("sahih", "khata"),
        ("صحيح", "خطأ"),

        # Hindi
        ("haan", "nahin"),
        ("सही", "गलत"),

        # Chinese
        ("shi", "fou"),
        ("是", "否"),
        ("dui", "cuo"),
        ("对", "错"),

        # Japanese
        ("hai", "iie"),
        ("はい", "いいえ"),
        ("tadashii", "machigai"),
        ("正しい", "間違い"),

        # Korean
        ("ne", "aniyo"),
        ("네", "아니요"),
        ("majda", "teullida"),
        ("맞다", "틀리다"),
    ]

    for true_norm, false_norm in known_pairs:
        if true_norm in normalized_map and false_norm in normalized_map:
            return str(normalized_map[true_norm]), str(normalized_map[false_norm])

    # fallback: conserva orden si no reconoce el par
    return str(unique_values[0]), str(unique_values[1])

def get_preserved_unique_values(series: pd.Series) -> list:
    """
    Devuelve valores únicos preservando tipos originales.
    Solo limpia espacios en strings.
    """
    cleaned = [safe_strip_value(v) for v in series.dropna().tolist()]

    uniques = []
    for v in cleaned:
        if v not in uniques:
            uniques.append(v)

    try:
        return sorted(uniques)
    except Exception:
        return uniques

def infer_column_type(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "text"

    s_str = s.astype(str).str.strip().str.lower()
    s_str = s_str[s_str != ""]

    if s_str.empty:
        return "text"

    boolean_pairs = [
        # English
        ("true", "false"),
        ("yes", "no"),
        ("y", "n"),
        ("1", "0"),
        ("t", "f"),

        # Albanian
        ("po", "jo"),

        # Spanish
        ("si", "no"),
        ("sí", "no"),
        ("verdadero", "falso"),

        # Italian
        ("si", "no"),
        ("vero", "falso"),

        # French
        ("oui", "non"),
        ("vrai", "faux"),

        # German
        ("ja", "nein"),
        ("wahr", "falsch"),

        # Portuguese
        ("sim", "nao"),
        ("não", "sim"),
        ("verdadeiro", "falso"),

        # Turkish
        ("evet", "hayir"),
        ("hayır", "evet"),

        # Dutch
        ("ja", "nee"),
        ("waar", "onwaar"),

        # Swedish
        ("ja", "nej"),
        ("sant", "falskt"),

        # Danish
        ("ja", "nej"),
        ("sand", "falsk"),

        # Norwegian
        ("ja", "nei"),
        ("sann", "usann"),

        # Finnish
        ("kylla", "ei"),
        ("kyllä", "ei"),
        ("tosi", "epatosi"),
        ("tosi", "epätosi"),

        # Polish
        ("tak", "nie"),
        ("prawda", "falsz"),
        ("prawda", "fałsz"),

        # Czech / Slovak
        ("ano", "ne"),
        ("pravda", "nepravda"),

        # Romanian
        ("da", "nu"),
        ("adevarat", "fals"),
        ("adevărat", "fals"),

        # Hungarian
        ("igen", "nem"),
        ("igaz", "hamis"),

        # Russian
        ("da", "net"),
        ("pravda", "lozh"),
        ("правда", "ложь"),
        ("да", "нет"),

        # Greek
        ("nai", "oxi"),
        ("ναι", "όχι"),
        ("alithes", "psema"),
        ("αληθες", "ψευδές"),

        # Arabic
        ("naam", "la"),
        ("نعم", "لا"),
        ("sahih", "khata"),
        ("صحيح", "خطأ"),

        # Hindi
        ("haan", "nahin"),
        ("सही", "गलत"),

        # Chinese
        ("shi", "fou"),
        ("是", "否"),
        ("dui", "cuo"),
        ("对", "错"),

        # Japanese
        ("hai", "iie"),
        ("はい", "いいえ"),
        ("tadashii", "machigai"),
        ("正しい", "間違い"),

        # Korean
        ("ne", "aniyo"),
        ("네", "아니요"),
        ("majda", "teullida"),
        ("맞다", "틀리다"),
    ]

    unique_vals = set(s_str.unique())

    # Boolean confirmado
    if len(unique_vals) in (1, 2):
        for pair in boolean_pairs:
            if unique_vals.issubset(pair):
                return "boolean"

    # Boolean candidato: 80% dentro de un mismo par
    for pair in boolean_pairs:
        pair_ratio = s_str.isin(pair).mean()
        if pair_ratio >= 0.80:
            return "boolean_candidate"

    numeric_conv = pd.to_numeric(s_str, errors="coerce")
    if numeric_conv.notna().mean() >= 0.9:
        return "number"

    date_conv = pd.to_datetime(s_str, errors="coerce")
    if date_conv.notna().mean() >= 0.9:
        return "date_candidate"

    unique_count = s.nunique(dropna=True)
    unique_ratio = unique_count / len(s) if len(s) else 1

    if unique_ratio < 0.50:
        return "categorical"

    return "text"

def get_column_profile(series: pd.Series) -> dict:
    s_non_null = series.dropna()
    inferred = infer_column_type(series)
    unique_count = s_non_null.nunique(dropna=True)
    non_null_count = len(s_non_null)
    unique_ratio = unique_count / non_null_count if non_null_count else 0

    unique_values = []
    max_preview_uniques = 300

    try:
        cleaned_unique_values = [
            v.strip() if isinstance(v, str) else v
            for v in s_non_null.unique().tolist()
        ]

        if inferred in ["categorical", "boolean_candidate"]:
            unique_values = cleaned_unique_values[:max_preview_uniques]

        elif inferred == "text":
            # también mostrar opciones reemplazables para texto,
            # pero solo si no son demasiadas
            if unique_count <= max_preview_uniques:
                unique_values = cleaned_unique_values[:max_preview_uniques]
            else:
                unique_values = cleaned_unique_values[:max_preview_uniques]

        try:
            unique_values = sorted(unique_values)
        except Exception:
            pass

    except Exception:
        unique_values = []

    return {
        "inferred_type": inferred,
        "null_count": int(series.isna().sum()),
        "non_null_count": int(non_null_count),
        "unique_count": int(unique_count),
        "unique_ratio": float(unique_ratio),
        "unique_values": unique_values,
        "sample_values": [
            v.strip() if isinstance(v, str) else v
            for v in series.dropna().head(5).tolist()
        ],
    }

def profile_dataset(df: pd.DataFrame) -> dict:
    return {col: get_column_profile(df[col]) for col in df.columns}

