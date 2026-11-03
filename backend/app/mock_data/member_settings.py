"""구성원 설정: 시뮬레이터 모델 즐겨찾기와 구성원별 Command Code Key 참조 이름."""

from dataclasses import dataclass
from datetime import datetime

from app.mock_data.members import USERS
from app.mock_data.period import kst
from app.mock_data.routes import model_id
from app.mock_data.rows import Row


@dataclass(frozen=True)
class _Favorite:
    user_id: int
    openrouter_model_id: str
    execution_provider: str
    created_at: datetime


FAVORITES = (
    _Favorite(1, "anthropic/claude-opus-5.5", "Anthropic", kst(9, 26, 9, 40)),
    _Favorite(1, "anthropic/claude-sonnet-5.5", "Anthropic", kst(10, 3, 10, 12)),
    _Favorite(2, "openai/gpt-6-luna", "Azure", kst(9, 29, 11, 20)),
    _Favorite(2, "openai/gpt-6.1-sol", "OpenAI", kst(10, 7, 14, 5)),
    _Favorite(3, "z-ai/glm-5.3-flash", "Z.AI", kst(9, 1, 10)),
    _Favorite(3, "deepseek/deepseek-v4.1-flash", "DeepInfra", kst(9, 16, 15, 30)),
    _Favorite(4, "google/gemini-4-argon", "Google Vertex", kst(10, 21, 13, 50)),
    _Favorite(4, "moonshotai/kimi-k3.1-pro", "Moonshot AI", kst(10, 28, 10, 15)),
    _Favorite(5, "google/gemini-3.8-flash", "Google AI Studio", kst(9, 8, 16)),
    _Favorite(5, "anthropic/claude-haiku-5.5", "Anthropic", kst(10, 14, 9, 30)),
)
# 키를 새로 발급받아 이전 참조를 비활성화한 구성원과 그 시각
ROTATED_KEYS = {3: kst(10, 10, 11)}
KEYS_ISSUED_AT = kst(8, 3, 10)


def favorite_rows() -> list[Row]:
    return [
        {
            "user_id": f.user_id,
            "model_id": model_id(f.openrouter_model_id),
            "execution_provider": f.execution_provider,
            "created_at": f.created_at,
        }
        for f in FAVORITES
    ]


def _secret_ref(user_code: str, version: int = 1) -> str:
    base = f"COMMAND_CODE_KEY_{user_code.replace('-', '_')}"
    return base if version == 1 else f"{base}_V{version}"


def command_code_key_rows() -> list[Row]:
    rows: list[Row] = []
    for user in USERS:
        rotated_at = ROTATED_KEYS.get(user.user_id)
        closed_at = rotated_at or user.deactivated_at
        rows.append(
            {
                "member_name": user.name,
                "secret_ref": _secret_ref(user.user_code),
                "is_active": closed_at is None,
                "created_at": KEYS_ISSUED_AT,
                "updated_at": closed_at or KEYS_ISSUED_AT,
            }
        )
        if rotated_at is not None:
            rows.append(
                {
                    "member_name": user.name,
                    "secret_ref": _secret_ref(user.user_code, version=2),
                    "is_active": True,
                    "created_at": rotated_at,
                    "updated_at": rotated_at,
                }
            )
    return [{"command_code_key_id": n, **row} for n, row in enumerate(rows, start=1)]
