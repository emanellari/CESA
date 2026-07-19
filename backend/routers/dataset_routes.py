from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import csv
import io
import json
import zipfile

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pandas.errors import EmptyDataError, ParserError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..deps import get_current_user
from ..models import Dataset, User


router = APIRouter(prefix="/dataset", tags=["dataset"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}
ALLOWED_FIELD_TYPES = {
    "text",
    "number",
    "date",
    "radio",
    "checkbox",
    "select",
}

XLS_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------
# Request models
# -------------------------------------------------------------------

class FieldConfig(BaseModel):
    type: Literal[
        "text",
        "number",
        "date",
        "radio",
        "checkbox",
        "select",
    ]
    options: List[str] = Field(default_factory=list)


class CreateDatasetPayload(BaseModel):
    name: str = Field(..., min_length=1)
    columns: List[str] = Field(..., min_length=1)
    options: Dict[str, FieldConfig] = Field(default_factory=dict)


class UpdateDatasetPayload(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)


# -------------------------------------------------------------------
# Dataset helpers
# -------------------------------------------------------------------

def _require_owned_dataset(
    db: Session,
    user: User,
    dataset_id: int,
) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.user_id == user.id,
        )
        .first()
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    return dataset


def _safe_load_json(value: Optional[str], default: Any) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _normalize_columns(values: List[Any]) -> List[str]:
    normalized: List[str] = []

    for index, value in enumerate(values):
        column = str(value).strip()

        # Remove a possible UTF-8 BOM from the first CSV header.
        if index == 0:
            column = column.lstrip("\ufeff")

        normalized.append(column)

    if not normalized or any(not column for column in normalized):
        raise HTTPException(
            status_code=400,
            detail="Column names cannot be empty.",
        )

    if len(normalized) != len(set(normalized)):
        raise HTTPException(
            status_code=400,
            detail="Column names must be unique.",
        )

    return normalized


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
        raise HTTPException(
            status_code=400,
            detail="The columns parameter is not valid JSON.",
        ) from exc

    if not isinstance(candidate, list):
        raise HTTPException(
            status_code=400,
            detail="The columns parameter must be a JSON array.",
        )

    parsed = _normalize_columns(candidate)

    if len(parsed) != len(detected):
        raise HTTPException(
            status_code=400,
            detail=(
                "The provided column names do not match the file. "
                f"Expected {len(detected)} names, but received "
                f"{len(parsed)}."
            ),
        )

    return parsed


# -------------------------------------------------------------------
# File-reading helpers
# -------------------------------------------------------------------

def _decode_text_file(content: bytes) -> Tuple[str, str]:
    if not content:
        raise ValueError("The uploaded file is empty.")

    # Plain CSV and TSV files should not normally contain null bytes.
    if b"\x00" in content[:4096]:
        raise ValueError(
            "The uploaded text file contains binary data. "
            "Check that the filename extension matches the actual file type."
        )

    last_error: Optional[UnicodeDecodeError] = None

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc

    raise ValueError(
        "The text encoding could not be detected."
    ) from last_error


def _detect_delimiter(text: str, default: str = ",") -> str:
    non_empty_lines = [
        line
        for line in text.splitlines()
        if line.strip()
    ]

    if not non_empty_lines:
        raise ValueError("The uploaded file does not contain data.")

    sample = "\n".join(non_empty_lines[:25])

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;\t|",
        )
        return dialect.delimiter
    except csv.Error:
        delimiter_counts = {
            ",": sample.count(","),
            ";": sample.count(";"),
            "\t": sample.count("\t"),
            "|": sample.count("|"),
        }

        detected = max(
            delimiter_counts,
            key=delimiter_counts.get,
        )

        if delimiter_counts[detected] == 0:
            return default

        return detected


def _read_delimited_file(
    content: bytes,
    expected_separator: Optional[str] = None,
) -> pd.DataFrame:
    text, _encoding = _decode_text_file(content)

    if expected_separator == "\t":
        separators = ["\t"]
    else:
        detected_separator = _detect_delimiter(text)

        separators = [
            detected_separator,
            ",",
            ";",
            "\t",
            "|",
        ]

    # Remove duplicates while preserving order.
    separators = list(dict.fromkeys(separators))

    last_error: Optional[Exception] = None
    one_column_result: Optional[pd.DataFrame] = None

    for separator in separators:
        try:
            dataframe = pd.read_csv(
                io.StringIO(text),
                sep=separator,
                engine="python",
                skipinitialspace=True,
                keep_default_na=True,
                on_bad_lines="error",
            )

            dataframe = dataframe.dropna(how="all")

            if len(dataframe.columns) > 1:
                return dataframe

            # Keep this in case the file legitimately has one column.
            one_column_result = dataframe

        except (
            EmptyDataError,
            ParserError,
            UnicodeError,
            ValueError,
        ) as exc:
            last_error = exc

    if one_column_result is not None:
        return one_column_result

    raise ValueError(
        "The CSV or TSV structure could not be parsed."
    ) from last_error


def _read_uploaded_dataframe(
    content: bytes,
    extension: str,
) -> pd.DataFrame:
    """
    Read the uploaded file using its real binary format when possible.

    This also handles a frontend-generated XLSX file that accidentally
    keeps its original CSV filename.
    """

    # XLSX files are ZIP containers internally.
    if zipfile.is_zipfile(io.BytesIO(content)):
        return pd.read_excel(
            io.BytesIO(content),
            engine="openpyxl",
        )

    # Legacy XLS files use the OLE compound-file signature.
    if content.startswith(XLS_SIGNATURE):
        return pd.read_excel(
            io.BytesIO(content),
            engine="xlrd",
        )

    if extension == ".xlsx":
        return pd.read_excel(
            io.BytesIO(content),
            engine="openpyxl",
        )

    if extension == ".xls":
        return pd.read_excel(
            io.BytesIO(content),
            engine="xlrd",
        )

    if extension == ".csv":
        return _read_delimited_file(
            content,
            expected_separator=None,
        )

    if extension == ".tsv":
        return _read_delimited_file(
            content,
            expected_separator="\t",
        )

    raise ValueError(
        f"Unsupported file format: {extension}"
    )


def _prepare_dataframe_after_read(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    if dataframe is None:
        raise ValueError("The file did not produce a dataset.")

    dataframe = dataframe.dropna(how="all").copy()

    if dataframe.columns.empty:
        raise ValueError("The file does not contain columns.")

    return dataframe


def _parse_upload_options(
    options_json: Optional[str],
    original_columns: List[str],
    final_columns: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not options_json:
        return {
            column: {
                "type": "text",
                "options": [],
            }
            for column in final_columns
        }

    try:
        raw_options = json.loads(options_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The options parameter is not valid JSON.",
        ) from exc

    if not isinstance(raw_options, dict):
        raise HTTPException(
            status_code=400,
            detail="The options parameter must be a JSON object.",
        )

    parsed_options: Dict[str, Dict[str, Any]] = {}

    for original_column, final_column in zip(
        original_columns,
        final_columns,
    ):
        # Support configurations keyed by either the original name
        # or the renamed final column name.
        raw_config = raw_options.get(
            final_column,
            raw_options.get(original_column, {}),
        )

        if not isinstance(raw_config, dict):
            raw_config = {}

        field_type = raw_config.get("type", "text")
        field_options = raw_config.get("options", [])

        if field_type not in ALLOWED_FIELD_TYPES:
            field_type = "text"

        if not isinstance(field_options, list):
            field_options = []

        clean_options: List[str] = []

        for option in field_options:
            if option is None:
                continue

            clean_option = str(option).strip()

            if clean_option:
                clean_options.append(clean_option)

        parsed_options[final_column] = {
            "type": field_type,
            "options": clean_options,
        }

    return parsed_options


# -------------------------------------------------------------------
# Create a dataset manually
# -------------------------------------------------------------------

@router.post("/create")
def create_dataset(
    payload: CreateDatasetPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    columns = _normalize_columns(payload.columns)

    options_clean: Dict[str, Dict[str, Any]] = {}

    for column, field_config in payload.options.items():
        if column not in columns:
            continue

        clean_options = [
            option.strip()
            for option in field_config.options
            if option and option.strip()
        ]

        options_clean[column] = {
            "type": field_config.type,
            "options": clean_options,
        }

    for column in columns:
        options_clean.setdefault(
            column,
            {
                "type": "text",
                "options": [],
            },
        )

    dataframe = pd.DataFrame(columns=columns)

    metadata = {
        "columns": columns,
        "options": options_clean,
    }

    dataset = Dataset(
        name=payload.name.strip(),
        data_json=dataframe.to_json(orient="records"),
        meta_json=json.dumps(metadata),
        user_id=user.id,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": columns,
        "meta": metadata,
        "data": [],
    }


# -------------------------------------------------------------------
# Upload CSV, TSV, XLS or XLSX
# -------------------------------------------------------------------

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    options: Optional[str] = Form(None),
    columns: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only .xlsx, .xls, .csv and .tsv files "
                "are supported."
            ),
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    try:
        dataframe = _read_uploaded_dataframe(
            content,
            extension,
        )
        dataframe = _prepare_dataframe_after_read(dataframe)

    except ImportError as exc:
        dependency = {
            ".xlsx": "openpyxl",
            ".xls": "xlrd",
        }.get(extension)

        if dependency:
            message = (
                f"The {dependency} dependency is required "
                f"to read {extension} files."
            )
        else:
            message = (
                "A required file-reading dependency is missing."
            )

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from exc

    except (
        ValueError,
        OSError,
        UnicodeError,
        EmptyDataError,
        ParserError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"The file could not be read: {exc}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file is invalid, damaged or "
                "does not match its filename extension."
            ),
        ) from exc

    original_columns = _normalize_columns(
        list(dataframe.columns)
    )

    final_columns = _parse_upload_columns(
        columns,
        original_columns,
    )

    dataframe.columns = final_columns

    parsed_options = _parse_upload_options(
        options,
        original_columns,
        final_columns,
    )

    # Replace pandas missing values before JSON serialization.
    dataframe = dataframe.where(
        pd.notna(dataframe),
        "",
    )

    metadata = {
        "columns": final_columns,
        "options": parsed_options,
    }

    dataset = Dataset(
        name=filename,
        data_json=dataframe.to_json(
            orient="records",
            date_format="iso",
        ),
        meta_json=json.dumps(metadata),
        user_id=user.id,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": final_columns,
        "meta": metadata,
        "preview": dataframe.head(20).to_dict(
            orient="records"
        ),
    }


# -------------------------------------------------------------------
# Retrieve a dataset
# -------------------------------------------------------------------

@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(
        db,
        user,
        dataset_id,
    )

    data = _safe_load_json(
        dataset.data_json,
        default=[],
    )

    dataframe = pd.DataFrame(data).fillna("")

    metadata = _safe_load_json(
        getattr(dataset, "meta_json", None),
        default=None,
    )

    # Build minimal metadata for datasets created by older versions.
    if metadata is None:
        columns = list(dataframe.columns)

        metadata = {
            "columns": columns,
            "options": {
                column: {
                    "type": "text",
                    "options": [],
                }
                for column in columns
            },
        }

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "columns": list(dataframe.columns),
        "meta": metadata,
        "data": dataframe.to_dict(orient="records"),
    }


# -------------------------------------------------------------------
# Update a dataset from the Streamlit editor
# -------------------------------------------------------------------

@router.post("/{dataset_id}/update")
def update_dataset(
    dataset_id: int,
    payload: UpdateDatasetPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(
        db,
        user,
        dataset_id,
    )

    dataframe = pd.DataFrame(
        payload.rows or []
    ).fillna("")

    dataset.data_json = dataframe.to_json(
        orient="records",
        date_format="iso",
    )

    db.commit()

    return {
        "ok": True,
        "rows": len(dataframe),
    }


# -------------------------------------------------------------------
# Export a dataset as XLSX
# -------------------------------------------------------------------

@router.get("/{dataset_id}/export")
def export_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(
        db,
        user,
        dataset_id,
    )

    data = _safe_load_json(
        dataset.data_json,
        default=[],
    )

    dataframe = pd.DataFrame(data).fillna("")

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Dataset",
        )

    buffer.seek(0)

    safe_stem = Path(dataset.name or "dataset").stem
    export_name = f"{safe_stem}_export.xlsx"

    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export_name}"'
            )
        },
    )


# -------------------------------------------------------------------
# Export dataset metadata
# -------------------------------------------------------------------

@router.get("/{dataset_id}/meta")
def export_dataset_meta(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(
        db,
        user,
        dataset_id,
    )

    metadata = _safe_load_json(
        getattr(dataset, "meta_json", None),
        default={},
    )

    return {
        "dataset_id": dataset.id,
        "meta": metadata,
    }


# -------------------------------------------------------------------
# List datasets belonging to the current user
# -------------------------------------------------------------------

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
            "dataset_id": dataset.id,
            "name": dataset.name,
            "created_at": (
                dataset.created_at.isoformat()
                if dataset.created_at
                else None
            ),
        }
        for dataset in datasets
    ]


# -------------------------------------------------------------------
# Delete a dataset
# -------------------------------------------------------------------

@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = _require_owned_dataset(
        db,
        user,
        dataset_id,
    )

    db.delete(dataset)
    db.commit()

    return {"ok": True}