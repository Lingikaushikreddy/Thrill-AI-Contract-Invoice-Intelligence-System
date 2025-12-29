import os
import pytest
from unittest.mock import MagicMock, patch

# Set env vars BEFORE importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "admin"
os.environ["MINIO_SECRET_KEY"] = "admin"
os.environ["MINIO_BUCKET"] = "test-bucket"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "testsecret"
os.environ["ALLOWED_ORIGINS"] = "*"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"

# Mock dependencies before importing api.main
with patch("minio.Minio") as mock_minio, \
     patch("celery.Celery") as mock_celery, \
     patch("shared.ingestion.VectorService") as mock_vector_service:

    mock_minio_instance = MagicMock()
    mock_minio.return_value = mock_minio_instance

    mock_vector_service_instance = MagicMock()
    mock_vector_service.return_value = mock_vector_service_instance

    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)

    def test_health_check():
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "services": {"database": "connected", "minio": "connected"}}

    def test_upload_unauthorized():
        # Attempt upload without token
        files = {'file': ('test.txt', b"content")}
        response = client.post("/upload", files=files)
        # Expect 401 Unauthorized
        assert response.status_code == 401

    def test_upload_authorized():
        # Need to generate a valid token
        from shared.auth import create_access_token
        token = create_access_token(data={"sub": "admin", "role": "admin"})

        files = {'file': ('test.txt', b"content")}
        headers = {"Authorization": f"Bearer {token}"}

        # Mock minio bucket check
        from api.main import minio_client
        minio_client.bucket_exists.return_value = True

        # Mock Celery send_task
        from api.main import celery_app
        celery_app.send_task.return_value = None

        # Need to create a user in the test DB for role checker?
        # RoleChecker checks user from DB using token.
        # "user = db.query(User).filter(User.username == username).first()"
        # So I need to seed the user.
        from shared.database import SessionLocal
        from shared.models import User
        from shared.auth import get_password_hash

        db = SessionLocal()
        # Check if user exists to avoid unique constraint error on re-runs
        if not db.query(User).filter(User.username == "admin").first():
            user = User(username="admin", email="admin@example.com", hashed_password=get_password_hash("pass"), role="admin")
            db.add(user)
            db.commit()
        db.close()

        response = client.post("/upload", files=files, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert "id" in data
