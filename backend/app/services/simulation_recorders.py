"""RequestRecorder 포트의 DB 구현. 쓰기는 모두 services/requests.py 에 맡긴다.

두 가지 쓰임이 있다.
- SessionRequestRecorder: 요청 세션을 그대로 쓰고 commit 하지 않는다. 접수가 실행·호출 이력·칸 결과를
  한 트랜잭션에 묶을 때 쓴다.
- ScopedRequestRecorder: 쓸 때마다 새 세션을 열고 commit 한다. 모델 호출은 요청이 끝난 뒤에도 돌고
  여러 칸이 동시에 저장하는데, 세션 하나는 여러 작업이 함께 쓰면 안 되기 때문이다. 취소도 이쪽으로
  부르면 CANCELLED 가 commit 된 뒤에 멈춤 신호를 켤 수 있다.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import simulation_requests
from app.services.simulation_ports import NewRequest, SlotRecord


class SessionRequestRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(self, request: NewRequest) -> None:
        await simulation_requests.create_simulation_request(self._session, request)

    async def mark_running(self, request_id: uuid.UUID, now: datetime) -> bool:
        return await simulation_requests.start_simulation_request(
            self._session, request_id
        )

    async def record_finished(
        self, request_id: uuid.UUID, record: SlotRecord, now: datetime
    ) -> bool:
        return await simulation_requests.finish_simulation_request(
            self._session, request_id, record, now
        )

    async def cancel_if_open(self, request_id: uuid.UUID, now: datetime) -> bool:
        return await simulation_requests.cancel_simulation_request(
            self._session, request_id, now
        )

    async def save_payload(
        self,
        request_id: uuid.UUID,
        messages: Sequence[dict[str, str]],
        response_text: str | None,
    ) -> None:
        await simulation_requests.save_simulation_payload(
            self._session, request_id, messages, response_text
        )


class ScopedRequestRecorder:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create_pending(self, request: NewRequest) -> None:
        async with self._sessions.begin() as session:
            await SessionRequestRecorder(session).create_pending(request)

    async def mark_running(self, request_id: uuid.UUID, now: datetime) -> bool:
        async with self._sessions.begin() as session:
            return await SessionRequestRecorder(session).mark_running(request_id, now)

    async def record_finished(
        self, request_id: uuid.UUID, record: SlotRecord, now: datetime
    ) -> bool:
        async with self._sessions.begin() as session:
            return await SessionRequestRecorder(session).record_finished(
                request_id, record, now
            )

    async def cancel_if_open(self, request_id: uuid.UUID, now: datetime) -> bool:
        async with self._sessions.begin() as session:
            return await SessionRequestRecorder(session).cancel_if_open(request_id, now)

    async def save_payload(
        self,
        request_id: uuid.UUID,
        messages: Sequence[dict[str, str]],
        response_text: str | None,
    ) -> None:
        async with self._sessions.begin() as session:
            await SessionRequestRecorder(session).save_payload(
                request_id, messages, response_text
            )
