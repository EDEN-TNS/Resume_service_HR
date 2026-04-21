import importlib
import os
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def _iter_fixture_files() -> list[Path]:
    d = _fixtures_dir()
    if not d.exists():
        return []
    return sorted([p for p in d.rglob("*") if p.is_file() and p.name != ".gitkeep"])


def _make_sample_pdf_bytes() -> bytes:
    """
    docling이 안정적으로 파싱할 수 있는 PDF를 런타임에 생성한다.
    (바이너리 파일을 repo에 커밋하지 않기 위함)
    """
    pillow = pytest.importorskip("PIL", reason="Pillow not installed")
    Image = pillow.Image
    ImageDraw = pillow.ImageDraw

    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Hello Resume\nEmail: test@example.com", fill=(0, 0, 0))

    buf = BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def _load_fixture_pdf_paths() -> list[Path]:
    return [p for p in _iter_fixture_files() if p.suffix.lower() == ".pdf"]


def _guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".doc":
        return "application/msword"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return "application/octet-stream"


@pytest.mark.parametrize("path", _iter_fixture_files(), ids=lambda p: str(p))
def test_test_resume_upload_all_fixtures_with_mock_processor(path: Path) -> None:
    """
    fixtures 내 모든 파일이 업로드/검증/라우팅에서 깨지지 않는지 확인.
    (처리 로직은 MOCK_HR_PROCESSOR로 우회)
    """
    os.environ["MOCK_HR_PROCESSOR"] = "true"
    os.environ["VLLM_URL"] = "http://example.invalid"
    os.environ["VLLM_MODEL"] = "dummy"

    from src.api import main as api_main

    api_main = importlib.reload(api_main)
    client = TestClient(api_main.app)

    content_type = _guess_content_type(path)
    resp = client.post(
        "/test_resume/",
        files={"file": (path.name, path.read_bytes(), content_type)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("filename") == path.name


def test_test_resume_docling_pipeline_with_mock_llm() -> None:
    pytest.importorskip("docling", reason="docling not installed")
    os.environ["MOCK_HR_PROCESSOR"] = "false"
    os.environ["MOCK_LLM"] = "true"

    from src.api import main as api_main

    api_main = importlib.reload(api_main)
    client = TestClient(api_main.app)

    pdf_paths = _load_fixture_pdf_paths()
    if pdf_paths:
        pdf_path = pdf_paths[0]
        pdf_bytes = pdf_path.read_bytes()
        pdf_name = pdf_path.name
    else:
        pdf_bytes = _make_sample_pdf_bytes()
        pdf_name = "generated.pdf"

    resp = client.post(
        "/test_resume/",
        files={"file": (pdf_name, pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "markdown_length" in data
    assert "token_count" in data
    assert data.get("summary") == "mocked (MOCK_LLM=true)"
