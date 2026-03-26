# mira/utils/drive_utils.py
import os
import io
import json
import base64
from functools import lru_cache
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build

@lru_cache(maxsize=1)
def load_drive_service():
    """Cache the Drive service so we don't rebuild + re-auth every time."""
    encoded_creds = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if not encoded_creds:
        raise ValueError("Missing GOOGLE_CREDENTIALS_BASE64 in environment")

    creds_dict = json.loads(base64.b64decode(encoded_creds).decode())
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    # cache_discovery=False avoids writing discovery cache files
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def download_image(drive_service, file_id):
    request = drive_service.files().get_media(fileId=file_id)
    image_data = io.BytesIO(request.execute())
    return Image.open(image_data).convert("RGB")


def download_image_to_path(drive_service, file_id: str, out_path: str) -> str:
    """Download Drive image and save to disk. Returns out_path."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img = download_image(drive_service, file_id).convert("RGB")
    img.save(out_path, format="PNG")
    return out_path
