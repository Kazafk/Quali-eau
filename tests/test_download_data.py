import os
import zipfile

from pipeline.download_data import _extract, download_all, RAW_DIR


def test_extract_creates_year_directory_with_files(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.download_data.RAW_DIR", str(tmp_path))
    zip_path = tmp_path / "dis-2099.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("DIS_PLV_2099.txt", "cddept,referenceprel\n001,ABC\n")
        z.writestr("DIS_RESULT_2099.txt", "cddept,referenceprel\n001,ABC\n")

    dest_dir = _extract(str(zip_path), 2099)

    assert os.path.isdir(dest_dir)
    assert set(os.listdir(dest_dir)) == {"DIS_PLV_2099.txt", "DIS_RESULT_2099.txt"}


def test_download_all_skips_when_local_size_matches_remote(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.download_data.RAW_DIR", str(tmp_path))
    monkeypatch.setattr("pipeline.download_data.ZIPS", [
        {"year": 2099, "filename": "dis-2099.zip", "url": "https://example.invalid/dis-2099.zip"},
    ])
    zip_path = tmp_path / "dis-2099.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("DIS_PLV_2099.txt", "x\n")
    local_size = os.path.getsize(zip_path)

    calls = {"download": 0}

    def fake_remote_size(url):
        return local_size

    def fake_download(url, dest):
        calls["download"] += 1

    monkeypatch.setattr("pipeline.download_data._remote_size", fake_remote_size)
    monkeypatch.setattr("pipeline.download_data._download", fake_download)

    download_all()

    assert calls["download"] == 0  # size matches -> no re-download
    assert os.path.isdir(tmp_path / "2099")  # but extraction still ran
