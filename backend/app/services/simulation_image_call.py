"""이미지 생성 실행의 모델 한 칸. 이미지 생성을 부르고, 받은 그림을 저장한 뒤 기록할 값을 돌려준다."""

import asyncio
import logging
from dataclasses import replace
from typing import Any

from app.models import ErrorType, RequestStatus
from app.openrouter import errors as openrouter_errors
from app.services.simulation_image_outcome import to_image_slot_record
from app.services.simulation_input import image_call_inputs
from app.services.simulation_output_config import image_call_options
from app.services.simulation_ports import (
    SimulationDeps,
    SimulationJob,
    SlotPlan,
    SlotRecord,
)

# 로그에는 request_id 와 예외 종류만 남긴다. 프롬프트·그림·예외 메시지는 남기지 않는다
logger = logging.getLogger(__name__)

_STORE_FAILED = openrouter_errors.ErrorType.UNKNOWN_ERROR


async def generate_slot_images(
    slot: SlotPlan,
    job: SimulationJob,
    deps: SimulationDeps,
    cancel: asyncio.Event,
    timeout_seconds: float,
    to_send: list[dict[str, Any]],
) -> SlotRecord:
    """칸 하나의 이미지를 만들고 기록할 값을 돌려준다. to_send 는 이미지 내용을 넣은 메시지다.

    그림은 결과를 기록하기 전에 저장한다. 저장하지 못하면 그림 없는 성공이 되지 않게 실패로 기록하고,
    이미 나간 비용은 그대로 남긴다.
    """
    prompt, reference_urls = image_call_inputs(to_send)
    result = await deps.image_generator(
        request_id=slot.request_id,
        model_id=slot.openrouter_model_id,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        input_image_urls=reference_urls or None,
        provider_order=[slot.execution_provider],
        allow_fallbacks=job.allow_fallbacks,
        cancel=cancel,
        **image_call_options(slot.execution_config),
    )
    record = to_image_slot_record(result)
    if record.status != RequestStatus.SUCCESS:
        return record
    try:
        await deps.outputs.save(slot.request_id, result.images)
    except Exception as error:  # noqa: BLE001 - 저장 실패는 이 칸의 실패로 바꿔 기록한다
        logger.error(
            "output images not stored: request_id=%s error=%s",
            slot.request_id,
            type(error).__name__,
        )
        return replace(
            record,
            status=RequestStatus.FAILED,
            error_type=ErrorType(_STORE_FAILED.value),
            error_message=openrouter_errors.USER_MESSAGES[_STORE_FAILED],
        )
    return record
