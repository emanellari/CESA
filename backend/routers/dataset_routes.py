from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


def _read_delimited_file(content: bytes, separator: str) -> pd.DataFrame:
    """Read CSV/TSV bytes, accepting UTF-8 and common Windows encodings."""
    last_error: Optional[Exception] = None

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(
                io.BytesIO(content),
                sep=separator,
                encoding=encoding,
            )
        except UnicodeDecodeError as exc:
            last_error = exc

    raise ValueError("No se pudo detectar la codificación del archivo") from last_error


def _read_uploaded_dataframe(content: bytes, extension: str) -> pd.DataFrame:
    """Read an uploaded tabular file using the parser required by its extension."""
    stream = io.BytesIO(content)

    if extension == ".xlsx":
        return pd.read_excel(stream, engine="openpyxl")
    if extension == ".xls":
        return pd.read_excel(stream, engine="xlrd")
    if extension == ".csv":
        return _read_delimited_file(content, separator=",")
    if extension == ".tsv":
        return _read_delimited_file(content, separator="\t")

    raise ValueError(f"Formato no compatible: {extension}")


def _normalize_columns(values: List[Any]) -> List[str]:
    columns = [str(value).strip() for value in values]

    if not columns or any(not column for column in columns):
        raise HTTPException(
            status_code=400,
            detail="Los nombres de columna no pueden estar vacíos",
        )

    if len(columns) != len(set(columns)):
        raise HTTPException(
            status_code=400,
            detail="Los nombres de columna deben ser únicos",
        )

    return columns


def _parse_upload_columns(
    columns_json: Optional[str],
    detected_columns: List[Any],
) -> List[str]:
    detected = _normalize_columns(detected_columns)

    if not columns_json:
        return detected

    try:
        candidate = json.loads(columns_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="columns inválido") from exc

    if not isinstance(candidate, list):
        raise HTTPException(
            status_code=400,
            detail="columns debe ser una lista JSON",
        )

    parsed = _normalize_columns(candidate)

    if len(parsed) != len(detected):
        raise HTTPException(
            status_code=400,
            detail=(
                "columns no coincide con el archivo: "
                f"se esperaban {len(detected)} nombres y se recibieron {len(parsed)}"
            ),
        )

    return parsed


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
# 🔹 Upload tabular file
# -------------------------
@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    options: Optional[str] = Form(None),
    columns: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    allowed_extensions = {".xlsx", ".xls", ".csv", ".tsv"}

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Solo archivos .xlsx, .xls, .csv o .tsv",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    try:
        df = _read_uploaded_dataframe(content, extension)
    except ImportError as exc:
        dependency = {".xlsx": "openpyxl", ".xls": "xlrd"}.get(extension)
        detail = (
            f"Falta la dependencia {dependency} para leer {extension}"
            if dependency
            else f"Falta una dependencia para leer {extension}"
        )
        raise HTTPException(status_code=500, detail=detail) from exc
    except (ValueError, OSError, UnicodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo leer el archivo {extension}: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo {extension} no es válido o está dañado",
        ) from exc

    if df.columns.empty:
        raise HTTPException(
            status_code=400,
            detail="El archivo no contiene columnas",
        )

    # Primero se procesa y valida el parámetro recibido; después se aplica al DataFrame.
    parsed_columns = _parse_upload_columns(columns, list(df.columns))
    df.columns = parsed_columns
    df = df.fillna("")

    # Parse options enviados desde frontend usando los nombres finales de columna.
    parsed_options: Dict[str, Dict[str, Any]] = {}
    if options:
        try:
            raw_options = json.loads(options)
            if not isinstance(raw_options, dict):
                raise ValueError("options debe ser objeto")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="options inválido") from exc

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
            for option in raw_opts:
                if isinstance(option, str):
                    option = option.strip()
                    if option:
                        clean_opts.append(option)
                elif option is not None:
                    clean_opts.append(option)

            parsed_options[col] = {
                "type": raw_type,
                "options": clean_opts,
            }
    else:
        parsed_options = {
            col: {"type": "text", "options": []}
            for col in parsed_columns
        }

    meta = {
        "columns": parsed_columns,
        "options": parsed_options,
    }

    dataset = Dataset(
        name=filename,
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