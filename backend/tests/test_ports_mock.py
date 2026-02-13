from pathlib import Path

from app.infra.llm.mock import MockLLM
from app.infra.ocr.mock import MockOCR
from app.infra.storage.local import LocalFileStorage


def test_mock_ocr_and_llm_and_local_storage(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    saved_url = storage.save_bytes("set_x/source.png", b"img", "image/png")

    ocr = MockOCR().extract(b"img-bytes")
    llm = MockLLM().generate_structured(prompt="hello", schema={"type": "object"})

    assert saved_url == "/uploads/set_x/source.png"
    assert (tmp_path / "set_x/source.png").exists()

    assert ocr["text"] == "[mock] OCR text"
    assert isinstance(ocr["confidence"], float)

    assert llm["provider"] == "mock"
    assert "schemaKeys" in llm
