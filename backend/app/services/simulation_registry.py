import asyncio
import uuid
from collections.abc import Iterable, Mapping


class CancelRegistry:
    """실행 중인 호출마다 취소 신호(asyncio.Event)를 들고 있는 메모리 보관함.

    backend 는 인스턴스 1대로 띄우므로 같은 프로세스에서 실행과 취소 요청을 모두 받는다.
    프로세스가 내려가면 사라지는 값이라 DB 상태의 기준이 아니다. 신호는 호출을 멈추게 하는 용도이고,
    취소 여부는 호출 이력의 상태(CANCELLED)가 기준이다.
    """

    def __init__(self) -> None:
        self._events: dict[uuid.UUID, asyncio.Event] = {}
        self._by_simulation: dict[uuid.UUID, set[uuid.UUID]] = {}

    def register(
        self, simulation_id: uuid.UUID, request_ids: Iterable[uuid.UUID]
    ) -> Mapping[uuid.UUID, asyncio.Event]:
        """실행의 호출마다 취소 신호를 만든다. 돌려주는 값을 run_simulation 에 넘긴다."""
        events = {request_id: asyncio.Event() for request_id in request_ids}
        self._events.update(events)
        self._by_simulation[simulation_id] = set(events)
        return events

    def signal(self, request_id: uuid.UUID) -> None:
        """그 호출에 멈추라고 알린다. 이미 끝났거나 모르는 호출이면 아무것도 하지 않는다."""
        event = self._events.get(request_id)
        if event is not None:
            event.set()

    def is_active(self, simulation_id: uuid.UUID) -> bool:
        """이 프로세스에서 그 실행을 돌리고 있는가."""
        return simulation_id in self._by_simulation

    def release(self, simulation_id: uuid.UUID) -> None:
        """실행이 끝났으니 신호를 버린다. 여러 번 불러도 안전하다."""
        for request_id in self._by_simulation.pop(simulation_id, set()):
            self._events.pop(request_id, None)
