"""시뮬레이터 API 테스트들이 함께 쓰는 fixture."""

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.simulation_deps import get_image_storage, get_simulation_manager
from app.services.image_storage import LocalImageStorage
from tests.api.simulation_helpers import FakeManager
from tests.api.test_auth import log_in, make_user
from tests.db_helpers import Factory


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def manager(app: FastAPI, events: list[str]) -> FakeManager:
    fake = FakeManager(events)
    app.dependency_overrides[get_simulation_manager] = lambda: fake
    return fake


@pytest.fixture
def image_storage(app: FastAPI, tmp_path: Path) -> LocalImageStorage:
    """업로드 이미지를 테스트 폴더에 쓴다. 저장소(리포지토리)나 실제 설정 폴더를 건드리지 않는다."""
    storage = LocalImageStorage(tmp_path / "images")
    app.dependency_overrides[get_image_storage] = lambda: storage
    return storage


@pytest.fixture
async def poc_setup(factory: Factory) -> None:
    """시뮬레이터 호출을 귀속하는 PoC 프로젝트·서비스·Key."""
    project = await factory.project(project_code="PRJ-PATRON-POC", project_type="POC")
    await factory.service(service_code="PATRON_SIMULATOR", service_type="PATRON")
    await factory.api_key(
        project_id=project["project_id"], secret_ref="OPENROUTER_KEY_POC"
    )


@pytest.fixture
async def models(factory: Factory) -> list[int]:
    rows = [
        await factory.model(
            status="ACTIVE", supported_parameters=["temperature", "reasoning"]
        )
        for _ in range(2)
    ]
    return [row["model_id"] for row in rows]


@pytest.fixture
async def signed_in(client: AsyncClient, factory: Factory) -> dict[str, Any]:
    user = await make_user(factory)
    assert (await log_in(client, user["email"])).status_code == 200
    return user
