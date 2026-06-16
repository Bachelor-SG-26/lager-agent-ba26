from pathlib import Path

import pytest

import config


@pytest.fixture
def test_database(monkeypatch):
    db_path = Path("test_lager.db")
    if db_path.exists():
        db_path.unlink()

    monkeypatch.setattr(config, "DATA_DIR", Path("."))
    monkeypatch.setattr(config, "DB_NAME", db_path)

    yield db_path

    if db_path.exists():
        db_path.unlink()
