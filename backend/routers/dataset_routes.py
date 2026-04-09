from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, List, Literal
from pydantic import BaseModel, Field
import pandas as pd
import io
import json
from typing import Dict, List, Optional, Any

from ..db import SessionLocal
from ..models import Dataset, User
from ..deps import get_current_user

router = APIRouter(prefix="/dataset", tags=["dataset"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Pydantic payloads
# -------------------------
class FieldConfig(BaseModel):
    type: Literal["text", "number", "date", "radio", "checkbox", "select"]
    options: List[str] = Field(default_factory=list)

class CreateDatasetPayload(BaseModel):
    name: str = Field(..., min_length=1)
    columns: List[str] = Field(..., min_length=1)
    options: Dict[str, FieldConfig] = Field(default_factory=dict)


class UpdateDatasetPayload(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)


def _require_owned_dataset(db: Session, user: User, dataset_id: int) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
    return dataset


def _safe_load_json(s: Optional[str], default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


# -------------------------
# ✅ Crear dataset desde 0
@router.post("/create")
def create_dataset(
    payload: CreateDatasetPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    columns = [c.strip() for c in payload.columns if c and c.strip()]
    if not columns:
        raise HTTPException(status_code=400, detail="columns no puede estar vacío")

    if len(columns) != len(set(columns)):
        raise HTTPException(status_code=400, detail="Las columnas deben ser únicas")

    options_clean: Dict[str, Dict[str, Any]] = {}

    for col, field_cfg in (payload.options or {}).items():
        if col in columns:
            clean_type = field_cfg.type
            clean_options = [o.strip() for o in field_cfg.options if o and o.strip()]

            options_clean[col] = {
                "type": clean_type,
                "options": clean_options,
            }

    for col in columns:
        options_clean.setdefault(col, {"type": "text", "options": []})

    df = pd.DataFrame(columns=columns)

    meta = {
        "columns": columns,
        "options": options_clean,
    }

    dataset = Dataset(
        name=payload.name,
        data_json=df.to_json(orient="records"),
        meta_json=json.dumps(meta),
        user_id=user.id,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": columns,
        "meta": meta,
        "data": [],
    }

# -------------------------
# 🔹 Upload Excel
# -------------------------
@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    options: Optional[str] = Form(None),
    columns: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filename = file.filename.lower()
    allowed_extensions = (".xlsx", ".xls", ".csv", ".tsv")

    if not filename.endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Solo archivos .xlsx, .xls, .csv o .tsv"
        )

    content = await file.read()

    import zipfile
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise HTTPException(
            status_code=400,
            detail="El archivo subido no es un .xlsx válido (no es ZIP interno)."
        )

    df = pd.read_excel(io.BytesIO(content), engine="openpyxl").fillna("")
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    detected_columns = list(df.columns)

    # Parse columns enviados desde frontend
    parsed_columns=detected_columns
    if len(parsed_columns) == len(df.columns):
        df.columns = parsed_columns
    else:
        raise HTTPException(status_code=400, detail="columns no coincide con el archivo")

    if columns:
        try:
            columns_candidate = json.loads(columns)
            if isinstance(columns_candidate, list):
                parsed_columns = [
                    c.strip() if isinstance(c, str) else c
                    for c in columns_candidate
                    if (c.strip() if isinstance(c, str) else c) != ""
                ]
        except Exception:
            raise HTTPException(status_code=400, detail="columns inválido")

    # Parse options enviados desde frontend
    parsed_options: Dict[str, Dict[str, Any]] = {}
    if options:
        try:
            raw_options = json.loads(options)
            if not isinstance(raw_options, dict):
                raise ValueError("options debe ser objeto")
        except Exception:
            raise HTTPException(status_code=400, detail="options inválido")

        for col in parsed_columns:
            raw_cfg = raw_options.get(col, {})
            if not isinstance(raw_cfg, dict):
                raw_cfg = {}

            raw_type = raw_cfg.get("type", "text")
            raw_opts = raw_cfg.get("options", [])

            if raw_type not in {"text", "number", "date", "radio", "checkbox", "select"}:
                raw_type = "text"

            if not isinstance(raw_opts, list):
                raw_opts = []

            clean_opts = []
            for o in raw_opts:
                if isinstance(o, str):
                    o_clean = o.strip()
                    if o_clean:
                        clean_opts.append(o_clean)
                elif o is not None:
                    clean_opts.append(o)

            parsed_options[col] = {
                "type": raw_type,
                "options": clean_opts,
            }
    else:
        for col in parsed_columns:
            parsed_options[col] = {
                "type": "text",
                "options": [],
            }

    meta = {
        "columns": parsed_columns,
        "options": parsed_options,
    }

    dataset = Dataset(
        name=file.filename,
        data_json=df.to_json(orient="records"),
        meta_json=json.dumps(meta),
        user_id=user.id,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": parsed_columns,
        "meta": meta,
        "preview": df.head(20).to_dict(orient="records"),
    }

# -------------------------
# 🔹 Obtener dataset
# -------------------------
@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(db, user, dataset_id)

    data = _safe_load_json(dataset.data_json, default=[])
    df = pd.DataFrame(data).fillna("")

    meta = _safe_load_json(getattr(dataset, "meta_json", None), default=None)
    # si no hay meta en DB (datasets viejos), construimos una mínima
    if meta is None:
        cols = list(df.columns)
        meta = {
            "columns": cols,
            "options": {c: {"type": "text", "options": []} for c in cols}
        }
    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": list(df.columns),
        "meta": meta,
        "data": df.to_dict(orient="records"),
    }


# -------------------------
# 🔹 Actualizar dataset (desde Streamlit editor)
# -------------------------
@router.post("/{dataset_id}/update")
def update_dataset(
    dataset_id: int,
    payload: UpdateDatasetPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(db, user, dataset_id)

    rows = payload.rows or []
    df = pd.DataFrame(rows).fillna("")

    dataset.data_json = df.to_json(orient="records")
    db.commit()

    return {"ok": True, "rows": len(df)}


# -------------------------
# 🔹 Export Excel
# -------------------------
@router.get("/{dataset_id}/export")
def export_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(db, user, dataset_id)

    data = _safe_load_json(dataset.data_json, default=[])
    df = pd.DataFrame(data).fillna("")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="export.xlsx"'},
    )


# -------------------------
# 🔹 Export metadata JSON
# -------------------------
@router.get("/{dataset_id}/meta")
def export_dataset_meta(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(db, user, dataset_id)
    meta = _safe_load_json(getattr(dataset, "meta_json", None), default={})
    # lo devolvemos como JSON normal
    return {"dataset_id": dataset.id, "meta": meta}


# -------------------------
# 🔹 Listar datasets del usuario (id + nombre + fecha)
# -------------------------
@router.get("")
def list_datasets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    datasets = (
        db.query(Dataset)
        .filter(Dataset.user_id == user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    return [
        {
            "dataset_id": d.id,
            "name": d.name,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


# -------------------------
# 🔹 Borrar dataset
# -------------------------
@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(db, user, dataset_id)
    db.delete(dataset)
    db.commit()
    return {"ok": True}