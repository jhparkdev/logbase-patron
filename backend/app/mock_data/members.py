"""Patron 구성원(관리자 계정). 실행자·등록자 기록용이며 비용 귀속 대상이 아니다.

기존 seed의 관리자 2명은 그대로 두어 팀원이 쓰던 로그인 정보로 계속 들어올 수 있게 한다.
"""

from dataclasses import dataclass
from datetime import datetime

from app.mock_data.period import kst
from app.mock_data.rows import Row

# 개발용 공통 비밀번호의 Argon2id 해시(v0.6 seed와 같은 값). 원문은 저장소에 두지 않는다.
DEV_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$gaRyHd/7tmr/juCD6muBAg$HsHckDxel4IYHkYqpMinwJOmBAhInt2fQM+WEI7bexg"


@dataclass(frozen=True)
class MockUser:
    user_id: int
    user_code: str
    name: str
    email: str
    last_login_at: datetime | None = None
    deactivated_at: datetime | None = None  # 퇴사 등으로 비활성화한 시각

    @property
    def is_active(self) -> bool:
        return self.deactivated_at is None

    def can_act_at(self, at: datetime) -> bool:
        return self.deactivated_at is None or at < self.deactivated_at


USERS = (
    MockUser(1, "USR-001", "김관리", "admin1@patron.dev"),
    MockUser(2, "USR-002", "이관리", "admin2@patron.dev"),
    MockUser(3, "USR-003", "박서연", "seoyeon.park@patron.dev", kst(11, 5, 18, 40)),
    MockUser(4, "USR-004", "최민준", "minjun.choi@patron.dev", kst(11, 5, 17, 12)),
    MockUser(5, "USR-005", "정하은", "haeun.jung@patron.dev", kst(11, 4, 11, 3)),
    MockUser(
        6,
        "USR-006",
        "한도윤",
        "doyun.han@patron.dev",
        kst(10, 17, 16, 25),
        kst(10, 17, 18),
    ),
)


def user_rows() -> list[Row]:
    return [
        {
            "user_id": u.user_id,
            "user_code": u.user_code,
            "name": u.name,
            "email": u.email,
            "password_hash": DEV_PASSWORD_HASH,
            "last_login_at": u.last_login_at,
            "is_active": u.is_active,
            "is_mock": True,
        }
        for u in USERS
    ]
