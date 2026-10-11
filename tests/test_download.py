import io
from zipfile import ZipFile

import pytest

from demandpilot.data import download


def test_original_workbook_preserved_and_archive_reused(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with ZipFile(payload, "w") as bundle:
        bundle.writestr(download.WORKBOOK_NAME, b"original workbook bytes")
    requests = []
    def fetch(url, timeout):
        requests.append(url)
        return io.BytesIO(payload.getvalue())
    monkeypatch.setattr(download, "urlopen", fetch)
    workbook = download.download_dataset(tmp_path)
    digest = download.sha256(workbook)
    workbook.write_bytes(b"changed locally")
    download.download_dataset(tmp_path)
    assert workbook.read_bytes() == b"original workbook bytes"
    assert download.sha256(workbook) == digest
    assert requests == [download.SOURCE_URL]


def test_unexpected_archive_not_cached(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with ZipFile(payload, "w") as bundle:
        bundle.writestr("unexpected.txt", b"content")
    monkeypatch.setattr(download, "urlopen", lambda *args, **kwargs: io.BytesIO(payload.getvalue()))
    with pytest.raises(ValueError, match="Unexpected"):
        download.download_dataset(tmp_path)
    assert not (tmp_path / "online_retail.zip").exists()
    assert not list(tmp_path.glob("*.part"))
