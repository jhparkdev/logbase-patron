"""모델별 응답 속도와 실행 Provider. 지연 시간 = 첫 Token 시간 + 출력 Token / 초당 Token.

값은 모델 등급(고성능·저가·경량)에 맞춘 Mock 추정치다. 실제 측정값이 아니고, Provider 이름도
모델별 실제 엔드포인트 목록으로 확인한 것이 아니다.
"""

from dataclasses import dataclass

ANTHROPIC = ("Anthropic", "Amazon Bedrock", "Google Vertex")
OPENAI = ("OpenAI", "Azure")
GOOGLE = ("Google Vertex", "Google AI Studio")
DEEPSEEK = ("DeepSeek", "DeepInfra")


@dataclass(frozen=True)
class ModelProfile:
    first_token_ms: int
    tokens_per_second: int
    providers: tuple[str, ...]
    reasoning_share: float = 0.0  # 출력 Token 중 추론 Token의 평균 비율


PROFILES = {
    "anthropic/claude-sonnet-5": ModelProfile(1400, 70, ANTHROPIC),
    "openai/gpt-5.6-luna": ModelProfile(500, 140, OPENAI, 0.15),
    "google/gemini-3.6-flash": ModelProfile(450, 180, GOOGLE),
    "deepseek/deepseek-v4-flash-0731": ModelProfile(900, 60, DEEPSEEK),
    "z-ai/glm-5.3-flash": ModelProfile(400, 150, ("Z.AI",)),
    "google/gemini-3.8-flash": ModelProfile(400, 200, GOOGLE, 0.1),
    "deepseek/deepseek-v4.1-flash": ModelProfile(800, 70, DEEPSEEK, 0.1),
    "anthropic/claude-opus-5.5": ModelProfile(2200, 45, ANTHROPIC, 0.25),
    "openai/gpt-6-luna": ModelProfile(450, 160, OPENAI, 0.15),
    "anthropic/claude-sonnet-5.5": ModelProfile(1200, 75, ANTHROPIC, 0.1),
    "openai/gpt-6.1-sol": ModelProfile(1800, 60, OPENAI, 0.35),
    "google/gemini-nano-banana-2.1": ModelProfile(1500, 90, GOOGLE),
    "anthropic/claude-haiku-5.5": ModelProfile(350, 190, ANTHROPIC),
    "google/gemini-4-argon": ModelProfile(1600, 85, GOOGLE, 0.3),
    "moonshotai/kimi-k3.1-pro": ModelProfile(2000, 50, ("Moonshot AI",), 0.4),
}
