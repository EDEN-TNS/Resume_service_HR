import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    """
    CI에서는 LLM/vLLM 및 무거운 문서 전처리를 돌리지 않고,
    API 레이어(검증/라우팅/응답)를 샘플 업로드로 검증한다.
    """
    import os
    os.environ["MOCK_HR_PROCESSOR"] = "true"

    from src.api import main as api_main
    return TestClient(api_main.app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_test_resume_upload_txt(client: TestClient) -> None:
    resp = client.post(
        "/test_resume/",
        files={"file": ("sample.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
