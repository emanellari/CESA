from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, List, Sequence, Tuple, Optional
from dateutil.parser import parse


def is_number(x: Any) -> bool:
    """True si x puede convertirse a float."""
    try:
        if x is None:
            return False
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return False
        float(s)
        return True
    except Exception:
        return False


def to_float(x: Any) -> Optional[float]:
    """Convierte a float o devuelve None si no se puede."""
    if is_number(x):
        return float(str(x).strip())
    return None


def is_date(string: Any, fuzzy: bool = False) -> bool:
    """Detecta si un valor parece fecha."""
    try:
        if string is None:
            return False
        s = str(string).strip()
        if s == "":
            return False
        parse(s, fuzzy=fuzzy)
        return True
    except Exception:
        return False


def columns(data: List[List[Any]]) -> List[List[Any]]:
    """Convierte lista de filas a lista de columnas."""
    if not data:
        return []
    return [list(col) for col in zip(*data)]


def auto_options(data: List[List[Any]]) -> List[List[Any]]:
    """
    Para cada columna, devuelve valores únicos si hay más de 1,
    si no, [''] (compatible con tu UI anterior).
    """
    cols = columns(data)
    ops: List[List[Any]] = []
    for col in cols:
        unique_vals = sorted({"" if (v is None) else v for v in col}, key=lambda x: str(x))
        ops.append(unique_vals if len(unique_vals) > 1 else [""])
    return ops


def frequency_table(col: Sequence[Any]) -> Tuple[List[Any], List[int]]:
    """Devuelve (labels, counts) preservando el orden de frecuencia."""
    cleaned = ["" if (v is None or str(v).lower() == "nan") else v for v in col]
    counts = Counter(cleaned)
    labels = list(counts.keys())
    values = list(counts.values())
    return labels, values


def mode_values(col: Sequence[Any]) -> List[Any]:
    labels, counts = frequency_table(col)
    if not counts:
        return []
    m = max(counts)
    return [labels[i] for i, c in enumerate(counts) if c == m]


def most_rare_values(col: Sequence[Any]) -> List[Any]:
    labels, counts = frequency_table(col)
    if not counts:
        return []
    m = min(counts)
    return [labels[i] for i, c in enumerate(counts) if c == m]


def detect_numeric_column(col: Sequence[Any], threshold: float = 0.8) -> bool:
    """
    Considera una columna numérica si al menos threshold de valores no vacíos
    se convierten a número.
    """
    non_empty = [v for v in col if v is not None and str(v).strip() != "" and str(v).lower() != "nan"]
    if not non_empty:
        return False
    numeric = sum(1 for v in non_empty if is_number(v))
    return (numeric / len(non_empty)) >= threshold


def len_max(vector: Sequence[Any], header: str, minw: int = 10, maxw: int = 40) -> int:
    maximum = max((len(str(x)) for x in vector), default=0)
    maximum = max(maximum, len(header))
    return min(max(minw, maximum), maxw)


def det_height(items: Sequence[Any]) -> int:
    """Para UI: altura en función de cuántos items."""
    return (len(items) + 1) * 7


# Helpers numéricos (por si luego los quieres)
def sum_col(col: Sequence[Any]) -> float:
    vals = [to_float(x) for x in col]
    return float(sum(v for v in vals if v is not None))


def min_col(col: Sequence[Any]) -> Optional[float]:
    vals = [to_float(x) for x in col]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None


def max_col(col: Sequence[Any]) -> Optional[float]:
    vals = [to_float(x) for x in col]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None