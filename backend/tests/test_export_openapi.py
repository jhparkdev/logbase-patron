"""app/export_openapi.py 테스트. 서버를 띄우지 않고 프론트엔드가 쓸 OpenAPI 문서를 파일로 만든다."""

import json
from pathlib import Path

from app.export_openapi import main
from app.main import create_app


def test_the_written_document_is_the_app_openapi(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"

    main([str(target)])

    assert json.loads(target.read_text(encoding="utf-8")) == create_app().openapi()


def test_the_document_carries_the_simulator_contract(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"

    main([str(target)])

    document = json.loads(target.read_text(encoding="utf-8"))
    assert "/api/simulations/{simulation_id}" in document["paths"]
    # 화면이 쓰는 값(정렬 열 등)이 enum 으로 전달된다
    assert "HistorySortColumn" in document["components"]["schemas"]


def test_korean_text_is_written_as_is(tmp_path: Path) -> None:
    # 설명 문구를 사람이 읽고 리뷰할 수 있게 \uXXXX 로 바꾸지 않는다
    target = tmp_path / "openapi.json"

    main([str(target)])

    assert "\\u" not in target.read_text(encoding="utf-8")
