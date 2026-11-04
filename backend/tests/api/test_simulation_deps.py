"""app/api/simulation_deps.py 테스트. 실제 OpenRouter 는 부르지 않고 연결 모양만 확인한다."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from app.api import simulation_deps
from app.api.simulation_deps import (
    build_image_storage,
    get_model_caller,
    get_openrouter_client,
)
from app.openrouter.client import OpenRouterClient
from app.services.gcs_image_storage import GcsImageStorage
from app.services.image_storage import LocalImageStorage
from tests.services.test_gcs_image_storage import FakeBucket

# 테스트용 가짜 Key. 오류나 출력에 드러나는지 찾을 표식으로 쓴다
FAKE_KEY = "sk-or-test-only-not-a-real-key"


def test_refuses_to_run_without_key() -> None:
    """Key 를 지운 상태에서는 실행을 받지 않는다. 의존성이 저장보다 먼저 풀려 아무것도 저장되지 않는다."""
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_model_caller(None)


def test_refuses_to_run_with_empty_key() -> None:
    """.env 에 값만 지운 줄(OPENROUTER_API_KEY=)이 남아 있어도 Key 가 없는 것으로 본다."""
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_model_caller(SecretStr(""))


def test_returns_call_model_of_real_client_when_key_is_set() -> None:
    caller = get_model_caller(SecretStr(FAKE_KEY))

    assert isinstance(caller.__self__, OpenRouterClient)
    assert caller.__func__ is OpenRouterClient.call_model


def test_key_is_not_exposed_in_caller_repr() -> None:
    caller = get_model_caller(SecretStr(FAKE_KEY))

    assert FAKE_KEY not in repr(caller)
    assert FAKE_KEY not in str(caller)


def test_text_and_image_calls_share_one_real_client() -> None:
    # 연결(httpx 클라이언트)과 Key 를 한 곳에서만 들고 있게 한다
    client = get_openrouter_client(SecretStr(FAKE_KEY))

    assert isinstance(client, OpenRouterClient)
    assert client.generate_image.__func__ is OpenRouterClient.generate_image


def test_image_calls_also_refuse_to_run_without_key() -> None:
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_openrouter_client(None)


def test_images_go_to_the_local_folder_without_a_bucket(tmp_path: Path) -> None:
    storage = build_image_storage(tmp_path, None)

    assert isinstance(storage, LocalImageStorage)


def test_an_emptied_bucket_line_means_no_bucket(tmp_path: Path) -> None:
    # .env 에 값만 지운 줄(IMAGE_STORAGE_BUCKET=)이 남아 있어도 로컬 폴더를 쓴다
    storage = build_image_storage(tmp_path, "")

    assert isinstance(storage, LocalImageStorage)


async def test_images_go_to_the_named_bucket_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 진짜 GCS 클라이언트는 자격증명이 필요해 버킷을 만드는 함수만 바꿔 끼운다
    bucket = FakeBucket()
    requested: list[str] = []

    def fake_bucket(name: str) -> FakeBucket:
        requested.append(name)
        return bucket

    monkeypatch.setattr(simulation_deps, "_gcs_bucket", fake_bucket)

    storage = build_image_storage(tmp_path, "patron-dev-images")
    await storage.write("simulator/a.png", b"abc")

    assert isinstance(storage, GcsImageStorage)
    assert requested == ["patron-dev-images"]
    assert bucket.objects == {"simulator/a.png": b"abc"}
    assert list(tmp_path.iterdir()) == []
