
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "services": {"database": "connected", "minio": "connected"}}

def test_upload_unauthorized(client):
    # Attempt upload without token
    files = {'file': ('test.txt', b"content")}
    response = client.post("/upload", files=files)
    # Should be 403 or 401 depending on how RoleChecker is implemented without token
    # RoleChecker usually expects a user dependency. If user dependency fails (no token), it raises 401.
    assert response.status_code == 401
