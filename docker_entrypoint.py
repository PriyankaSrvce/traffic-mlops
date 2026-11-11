"""Fetch and verify an optional pinned model artifact, then start the API."""

import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while chunk := file_obj.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_model(url: str, expected_sha256: str, destination: Path) -> None:
    if urlparse(url).scheme != "https":
        raise ValueError("QUEUE_MODEL_URL must use HTTPS")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("QUEUE_MODEL_SHA256 must be a 64-character SHA-256 hex digest")

    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    temporary_path = None
    try:
        with urlopen(Request(url, headers={"User-Agent": "traffic-queue-api/1.0"}), timeout=60) as response:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Model download redirected to a non-HTTPS URL")
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary_path = Path(output.name)
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)

        if digest.hexdigest().lower() != expected_sha256.lower():
            raise ValueError("Downloaded model SHA-256 does not match QUEUE_MODEL_SHA256")
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    model_path = Path(os.environ.get("QUEUE_MODEL_PATH", "/tmp/queue-model.joblib"))
    model_url = os.environ.get("QUEUE_MODEL_URL")
    expected_sha256 = os.environ.get("QUEUE_MODEL_SHA256")

    if model_url:
        if not expected_sha256:
            raise ValueError("QUEUE_MODEL_SHA256 is required when QUEUE_MODEL_URL is set")
        fetch_model(model_url, expected_sha256, model_path)
    elif expected_sha256 and model_path.is_file():
        actual = sha256_file(model_path)
        if actual.lower() != expected_sha256.lower():
            raise ValueError("Configured model SHA-256 does not match the local model artifact")

    port = os.environ.get("PORT", "8000")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("PORT must be an integer from 1 to 65535")
    os.execv(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()
