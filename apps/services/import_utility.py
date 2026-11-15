"""
Some incoming category values are just a single label ("Milk", "animal feed").
Others are a header followed by a numbered list ("VACCINES\n1. ...\n2. ...").
Either way: the header/single-value goes in `name`, everything else goes in
`description` — nothing from the original text is dropped.
"""


FIELD_NAME_MAX_LENGTH = 255


def parse_text(raw_text: str) -> dict:
    """
    Parse NABL category/product/parameter text safely.
    Handles multiline strings with leading spaces, quotes, or newlines.
    """
    if not raw_text:
        return {'name': None, 'description': None}

    complete_text = str(raw_text).replace('\xa0', ' ').strip().strip('"\'').strip()

    if not complete_text:
        return {'name': None, 'description': None}

    lines = [
        _normalize_header(line)
        for line in complete_text.splitlines()
        if _normalize_header(line)
    ]

    if not lines:
        return {'name': None, 'description': None}

    first_line_name = lines[0][:FIELD_NAME_MAX_LENGTH].rstrip()

    return {
        'name': first_line_name,
        'description': complete_text,
    }

def _normalize_header(header: str) -> str:
    """'VACCINES' -> 'Vaccines'. Leaves mixed-case text ('Animal Feed') untouched."""
    return header.title() if header.isupper() else header



import base64
import binascii
import mimetypes
import uuid
import requests

from django.core.files.base import ContentFile
from urllib.parse import urlparse


def save_image_db_field(model_name, image, field_name):
    """
    Save an image to a specified model ImageField/FileField.

    Supported image formats:
    1. Base64 string
    2. Direct image URL
    3. Dictionary containing 'base64' or 'url'

    Priority:
    1. Base64
    2. URL
    """
    if not image:
        return False

    base64_data = None
    image_url = None

    # ---------------------------------------------------------
    # 1. Identify image format
    # ---------------------------------------------------------
    if isinstance(image, dict):
        base64_data = image.get("base64")
        image_url = image.get("url")

    elif isinstance(image, str):
        image = image.strip()

        if image.startswith("data:image/"):
            base64_data = image

        elif image.startswith(("http://", "https://")):
            image_url = image

        else:
            # Assume a raw base64 string
            base64_data = image

    else:
        return False

    # ---------------------------------------------------------
    # 2. Try BASE64
    # ---------------------------------------------------------
    if base64_data:
        try:
            if "," in base64_data and base64_data.startswith("data:"):
                header, encoded_data = base64_data.split(",", 1)
                mime_type = header.split(";", 1)[0].replace(
                    "data:", ""
                )
                extension = mimetypes.guess_extension(mime_type) or ".png"
            else:
                encoded_data = base64_data
                extension = ".png"
            file_data = base64.b64decode(
                encoded_data,
                validate=True
            )
            if not file_data:
                raise ValueError("Empty image data")
            filename = f"image_{uuid.uuid4().hex}{extension}"
            getattr(model_name, field_name).save(
                filename,
                ContentFile(file_data),
                save=False
            )
            return True
        except (ValueError, binascii.Error, TypeError):
            pass

    # ---------------------------------------------------------
    # 3. Fallback to IMAGE URL
    # ---------------------------------------------------------
    if image_url:
        try:
            response = requests.get(
                image_url,
                timeout=15,
                stream=True
            )
            response.raise_for_status()
            content_type = response.headers.get(
                "Content-Type", ""
            ).split(";")[0].lower()
            # Ensure the response is an image
            if not content_type.startswith("image/"):
                return False
            extension = mimetypes.guess_extension(content_type) or ".png"
            filename = f"image_{uuid.uuid4().hex}{extension}"
            getattr(model_name, field_name).save(
                filename,
                ContentFile(response.content),
                save=False
            )
            return True
        except requests.RequestException:
            return False
    return False



