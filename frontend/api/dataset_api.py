import json
from api.client import api_get, api_post, api_delete


def _guess_mime_type(filename: str) -> str:
    filename = filename.lower()

    if filename.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if filename.endswith(".xls"):
        return "application/vnd.ms-excel"
    if filename.endswith(".csv"):
        return "text/csv"
    if filename.endswith(".tsv"):
        return "text/tab-separated-values"

    return "application/octet-stream"


def list_datasets():
    return api_get("/dataset")


def get_dataset(dataset_id: int):
    return api_get(f"/dataset/{dataset_id}")


def delete_dataset(dataset_id: int):
    return api_delete(f"/dataset/{dataset_id}")


def upload_dataset(uploaded_file, options: dict | None = None, columns: list[str] | None = None):
    mime_type = _guess_mime_type(uploaded_file.name)

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            mime_type,
        )
    }

    data = {}
    if options is not None:
        data["options"] = json.dumps(options)
    if columns is not None:
        data["columns"] = json.dumps(columns)

    return api_post("/dataset/upload", files=files, data=data)


def update_dataset(dataset_id: int, rows: list[dict]):
    return api_post(f"/dataset/{dataset_id}/update", json={"rows": rows})


def export_dataset(dataset_id: int):
    return api_get(f"/dataset/{dataset_id}/export")


def create_dataset_from_scratch(payload: dict):
    return api_post("/dataset/create", json=payload)