"""AI 도우미 요청의 동시 처리 제한. backend는 인스턴스 1대라 프로세스 안에서만 센다."""


class AssistantGate:
    """사용자마다 한 요청만, 전체로는 capacity개까지 받는다.

    asyncio는 한 스레드에서 돌고 확인과 등록 사이에 await가 없어 두 요청이 동시에 통과하지 않는다.
    """

    def __init__(self) -> None:
        self._active_users: set[int] = set()

    def try_enter(self, *, user_id: int, capacity: int) -> bool:
        if user_id in self._active_users or len(self._active_users) >= capacity:
            return False
        self._active_users.add(user_id)
        return True

    def leave(self, *, user_id: int) -> None:
        self._active_users.discard(user_id)
