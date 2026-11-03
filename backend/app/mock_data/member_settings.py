"""구성원 설정: 시뮬레이터 모델 즐겨찾기.

구성원별 Command Code Key는 실제 Key로 외부 사용량을 조회하므로 seed에 넣지 않는다.
실제 구성원은 `app.cli command-code-key-register`로 등록한다.
"""

from dataclasses import dataclass
from datetime import datetime

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
