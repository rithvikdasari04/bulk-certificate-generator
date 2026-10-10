"""API tests use temporary database and certificate paths."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

import app.main as main
from app import certificate_generator
from app.database import get_db, initialize_database


@pytest.fixture
def client(monkeypatch):
    # pytest's default tmp_path may point into a locked-down AppData Temp folder
    # on Windows. Keep each run's temporary files beneath the writable project.
    test_directory = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="pytest-", dir=test_directory) as temp_dir:
        temp_path = Path(temp_dir)
        database_path = temp_path / "test.sqlite3"
        database_url = f"sqlite:///{database_path.as_posix()}"
        test_engine = create_engine(
            database_url, connect_args={"check_same_thread": False}
        )
        test_sessions = sessionmaker(
            bind=test_engine, autoflush=False, autocommit=False
        )
        output_path = temp_path / "pdfs"
        monkeypatch.setattr(main, "engine", test_engine)
        monkeypatch.setattr(certificate_generator, "OUTPUT_DIR", output_path)

        def override_get_db():
            with test_sessions() as db:
                yield db

        main.app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(main.app) as test_client:
                test_client.test_output_dir = output_path
                yield test_client
        finally:
            main.app.dependency_overrides.clear()
            test_engine.dispose()


def test_create_job_generates_pdfs_and_reports_progress(client):
    response = client.post(
        "/api/jobs",
        json={
            "recipients": [
                {"full_name": "Ada Lovelace", "email": "ada@example.com"},
                {"full_name": "Grace Hopper", "email": "grace@example.com"},
            ]
        },
    )

    assert response.status_code == 201
    job = response.json()
    assert job == {"id": 1, "status": "completed"}

    progress = client.get(f"/api/jobs/{job['id']}")
    assert progress.status_code == 200
    assert progress.json() == {
        "id": 1,
        "status": "completed",
        "total_recipients": 2,
        "succeeded": 2,
        "failed": 0,
        "progress_percent": 100,
    }

    recipients = client.get(f"/api/jobs/{job['id']}/recipients").json()
    assert [recipient["generation_status"] for recipient in recipients] == [
        "succeeded",
        "succeeded",
    ]
    assert recipients[0]["pdf_path"] != recipients[1]["pdf_path"]
    for recipient in recipients:
        pdf = client.get(
            f"/api/jobs/{job['id']}/recipients/{recipient['id']}/pdf"
        )
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF-")
        assert b"CERTIFICATE OF INTERNSHIP COMPLETION" in pdf.content
        assert recipient["full_name"].encode() in pdf.content
    assert list(client.test_output_dir.glob("*.pdf"))


@pytest.mark.parametrize(
    "recipients",
    [
        [],
        [{"full_name": "Ada", "email": "not-an-email"}],
        [{"full_name": "  ", "email": "ada@example.com"}],
    ],
)
def test_invalid_recipient_input_returns_422(client, recipients):
    response = client.post("/api/jobs", json={"recipients": recipients})
    assert response.status_code == 422


def test_one_generation_failure_does_not_stop_other_recipients(client, monkeypatch):
    real_generator = certificate_generator.generate_certificate

    def fail_for_ada(full_name, output_dir=None):
        if full_name == "Ada Lovelace":
            raise RuntimeError("test rendering error")
        return real_generator(full_name, output_dir)

    monkeypatch.setattr(certificate_generator, "generate_certificate", fail_for_ada)
    response = client.post(
        "/api/jobs",
        json={
            "recipients": [
                {"full_name": "Ada Lovelace", "email": "ada@example.com"},
                {"full_name": "Grace Hopper", "email": "grace@example.com"},
            ]
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "partial"
    results = client.get("/api/jobs/1/recipients").json()
    assert results[0]["generation_status"] == "failed"
    assert results[0]["failure_message"] == "test rendering error"
    assert results[1]["generation_status"] == "succeeded"

    progress = client.get("/api/jobs/1").json()
    assert progress["succeeded"] == 1
    assert progress["failed"] == 1
    assert progress["progress_percent"] == 100
    assert client.get("/api/jobs/1/recipients/1/pdf").status_code == 404
    assert client.get("/api/jobs/1/recipients/2/pdf").status_code == 200


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_job_returns_404(client):
    assert client.get("/api/jobs/999").status_code == 404


def test_database_initialization_adds_result_columns_to_existing_database():
    test_directory = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(
        prefix="pytest-migration-", dir=test_directory
    ) as temp_dir:
        database_path = Path(temp_dir) / "legacy.sqlite3"
        legacy_engine = create_engine(
            f"sqlite:///{database_path.as_posix()}"
        )
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE certificate_jobs "
                    "(id INTEGER PRIMARY KEY, status VARCHAR(30) NOT NULL, "
                    "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE recipients "
                    "(id INTEGER PRIMARY KEY, full_name VARCHAR(200) NOT NULL, "
                    "email VARCHAR(320) NOT NULL, job_id INTEGER NOT NULL)"
                )
            )

        try:
            initialize_database(legacy_engine)
            columns = {
                column["name"]
                for column in inspect(legacy_engine).get_columns("recipients")
            }
            assert {"generation_status", "pdf_path", "failure_message"} <= columns
        finally:
            legacy_engine.dispose()


