from __future__ import annotations

from collections import Counter
from typing import Any, List, Sequence, Tuple

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