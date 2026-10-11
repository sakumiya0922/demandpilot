"""Download the original UCI archive without modifying the workbook."""

import hashlib
import shutil
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
WORKBOOK_NAME = "Online Retail.xlsx"


def download_dataset(raw_dir: Path = Path("data/raw")) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive = raw_dir / "online_retail.zip"
    if not archive.exists():
        temporary = archive.with_suffix(".zip.part")
        try:
            with urlopen(SOURCE_URL, timeout=120) as response, temporary.open("wb") as target:
                shutil.copyfileobj(response, target)
            with ZipFile(temporary) as bundle:
                if bundle.testzip() is not None or WORKBOOK_NAME not in bundle.namelist():
                    raise ValueError("Unexpected or damaged UCI archive")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    workbook = raw_dir / WORKBOOK_NAME
    # Re-extract from the cached original so the workbook always matches it.
    temporary_workbook = workbook.with_suffix(".xlsx.part")
    try:
        with ZipFile(archive) as bundle, bundle.open(WORKBOOK_NAME) as source:
            with temporary_workbook.open("wb") as target:
                shutil.copyfileobj(source, target)
        temporary_workbook.replace(workbook)
    finally:
        temporary_workbook.unlink(missing_ok=True)
    return workbook


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
