from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
import json

from ..core.calculations import frequency_table, mode_values, most_rare_values, is_number
from ..db import SessionLocal
from ..models import Dataset, User
from ..deps import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{dataset_id}")
def stats(
    dataset_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.user_id == user.id
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    data = json.loads(dataset.data_json)
    df = pd.DataFrame(data)

    column_name = payload.get("column_name")
    kind = payload.get("kind")

    if column_name not in df.columns:
        raise HTTPException(status_code=400, detail="Columna inválida")

    col = df[column_name].fillna("").tolist()

    if kind == "table":
        table, count = frequency_table(col)
        return {"table": table, "count": count}

    if kind == "mode":
        return {"mode": mode_values(col)}

    if kind == "most_rare":
        return {"most_rare": most_rare_values(col)}

    if kind == "hist":
        numeric = [float(x) for x in col if is_number(x)]
        return {"values": numeric}

    raise HTTPException(status_code=400, detail="Tipo de estadística inválido")