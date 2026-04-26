import json
import logging
import os
from io import BytesIO

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")
_ROOT_FOLDER_NAME = "cleo-finance"


def build_drive_service():
    if os.path.exists(_SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    else:
        from backend.config import get_settings
        info = json.loads(get_settings().google_service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    query = (
        f"name = '{name}' and '{parent_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()
    return folder["id"]


class DriveClient:
    def __init__(self):
        self._service = build_drive_service()

    def upload_pdf(self, file_bytes: bytes, filename: str, doc_type: str, month: str) -> None:
        query = (
            f"name = '{_ROOT_FOLDER_NAME}' "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = self._service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])
        if not files:
            logger.warning(f"'{_ROOT_FOLDER_NAME}' folder not found in Drive; skipping upload")
            return
        root_id = files[0]["id"]
        type_id = _get_or_create_folder(self._service, doc_type, root_id)
        month_id = _get_or_create_folder(self._service, month, type_id)
        media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype="application/pdf")
        self._service.files().create(
            body={"name": filename, "parents": [month_id]},
            media_body=media,
            fields="id",
        ).execute()
