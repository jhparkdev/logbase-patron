"""접수 때 DB 에서 읽는 것(SimulationLookup 의 DB 구현). 읽기만 한다."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    APIKey,
    InputAsset,
    InputType,
    KeyStatus,
    ModelRegistry,
    ModelStatus,
    Project,
    Service,
    SimulationRun,
    TestScenario,
)
from app.services.model_parameters import parameter_support
from app.services.simulation_ports import (
    ImageRef,
    ModelInfo,
    ScenarioInfo,
    SimulatorContext,
)

# OpenRouter 모델 정보에서 이미지를 받는다는 표시(input_modalities 의 값)
IMAGE_MODALITY = "image"

# 시뮬레이터 호출을 귀속하는 PoC 프로젝트·서비스·Key. 값은 DB 담당 seed 와 같다.
# api_keys 에는 코드 칸이 없어서 Key 원문이 든 환경변수 이름(secret_ref)으로 찾는다
SIMULATOR_PROJECT_CODE = "PRJ-PATRON-POC"
SIMULATOR_SERVICE_CODE = "PATRON_SIMULATOR"
SIMULATOR_KEY_SECRET_REF = "OPENROUTER_KEY_POC"


class SimulatorContextMissingError(LookupError):
    """시뮬레이터의 비용 귀속 대상(PoC 프로젝트·사용 중인 Key·서비스)이 DB 에 없다.

    귀속을 모른 채 실행하면 미분류 비용이 생기므로 실행을 받지 않는다. 운영 설정 문제다.
    """


class DbSimulationLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_scenario(self, scenario_id: int) -> ScenarioInfo | None:
        scenario = await self._session.get(TestScenario, scenario_id)
        if scenario is None:
            return None
        return ScenarioInfo(
            scenario_id=scenario.scenario_id,
            is_active=scenario.is_active,
            default_json_schema=scenario.default_json_schema,
            default_execution_config=scenario.default_execution_config,
            input_type=InputType(scenario.input_type),
        )

    async def find_models(self, model_ids: Sequence[int]) -> dict[int, ModelInfo]:
        if not model_ids:
            return {}
        rows = await self._session.scalars(
            select(ModelRegistry).where(ModelRegistry.model_id.in_(model_ids))
        )
        return {
            model.model_id: ModelInfo(
                model_id=model.model_id,
                openrouter_model_id=model.openrouter_model_id,
                display_name=model.display_name,
                status=ModelStatus(model.status),
                supports_images=IMAGE_MODALITY in model.input_modalities,
                parameter_support=parameter_support(model.supported_parameters),
            )
            for model in rows
        }

    async def find_images(
        self, asset_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ImageRef]:
        if not asset_ids:
            return {}
        rows = await self._session.scalars(
            select(InputAsset).where(InputAsset.asset_id.in_(asset_ids))
        )
        return {
            asset.asset_id: ImageRef(
                asset_id=asset.asset_id,
                storage_path=asset.storage_path,
                mime_type=asset.mime_type,
                sha256=asset.sha256,
            )
            for asset in rows
        }

    async def simulation_exists(self, simulation_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(SimulationRun.simulation_id).where(
                SimulationRun.simulation_id == simulation_id
            )
        )
        return found is not None

    async def simulator_context(self) -> SimulatorContext:
        row = (
            await self._session.execute(
                select(Project.project_id, APIKey.key_id, Service.service_id)
                .join(APIKey, APIKey.project_id == Project.project_id)
                .join(Service, Service.service_code == SIMULATOR_SERVICE_CODE)
                .where(
                    Project.project_code == SIMULATOR_PROJECT_CODE,
                    APIKey.secret_ref == SIMULATOR_KEY_SECRET_REF,
                    APIKey.status == KeyStatus.ACTIVE,
                )
            )
        ).one_or_none()
        if row is None:
            raise SimulatorContextMissingError
        return SimulatorContext(
            project_id=row.project_id, key_id=row.key_id, service_id=row.service_id
        )
