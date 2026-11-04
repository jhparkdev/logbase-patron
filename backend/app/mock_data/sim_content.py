"""시뮬레이션 입력 재료: 가상의 상품, 모델 등급, 시나리오별 입력 글. 응답 글은 sim_answers가 만든다."""

from dataclasses import dataclass
from enum import StrEnum
from random import Random


class Tier(StrEnum):
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"
    LIGHT = "LIGHT"


class Flaw(StrEnum):
    NONE = "NONE"
    CODE_FENCE = "CODE_FENCE"  # ```json 으로 감싸 JSON 파싱이 실패한다
    WRONG_TYPE = "WRONG_TYPE"  # 숫자 칸에 "189,000원" 같은 글을 넣는다
    MISSING_FIELD = "MISSING_FIELD"  # 필수 칸 하나를 빠뜨린다


MODEL_TIERS = {
    "anthropic/claude-opus-5.5": Tier.PREMIUM,
    "openai/gpt-6.1-sol": Tier.PREMIUM,
    "google/gemini-4-argon": Tier.PREMIUM,
    "moonshotai/kimi-k3.1-pro": Tier.PREMIUM,
    "anthropic/claude-sonnet-5.5": Tier.STANDARD,
    "anthropic/claude-sonnet-5": Tier.STANDARD,
    "google/gemini-3.8-flash": Tier.STANDARD,
    "google/gemini-3.6-flash": Tier.STANDARD,
    "deepseek/deepseek-v4.1-flash": Tier.STANDARD,
    "openai/gpt-6-luna": Tier.LIGHT,
    "openai/gpt-5.6-luna": Tier.LIGHT,
    "anthropic/claude-haiku-5.5": Tier.LIGHT,
    "z-ai/glm-5.3-flash": Tier.LIGHT,
    "deepseek/deepseek-v4-flash-0731": Tier.LIGHT,
    "google/gemini-nano-banana-2.1": Tier.LIGHT,
}


@dataclass(frozen=True)
class Product:
    customer_id: int
    name: str
    price: int
    options: tuple[str, ...]
    material: str
    category: str
    praises: tuple[str, str]  # 리뷰에서 자주 나오는 장점(문장 끝 '-다' 형태)
    complaints: tuple[str, str]


PRODUCTS = (
    Product(1, "울 블렌드 오버핏 싱글 코트", 189_000, ("차콜", "카멜", "오트밀"), "울 70%, 폴리에스터 30%", "아우터",
            ("어깨 라인이 자연스럽다", "보풀이 거의 생기지 않는다"), ("소매가 조금 길다", "카멜 색이 사진보다 어둡다")),
    Product(1, "원턱 와이드 데님 팬츠", 59_000, ("라이트블루", "인디고", "블랙"), "면 98%, 스판덱스 2%", "하의",
            ("허리 밴딩이 편하다", "기장이 넉넉하다"), ("첫 세탁 때 물이 빠진다", "원단이 얇은 편이다")),
    Product(2, "듀얼 인버터 무선 청소기 V12", 429_000, ("스카이 그레이", "미드나잇 블랙"), "본체 ABS, 알루미늄 파이프", "생활가전",
            ("흡입력이 강하다", "배터리를 쉽게 바꿀 수 있다"), ("2.8kg이라 오래 들면 무겁다", "먼지통이 작다")),
    Product(3, "세라마이드 배리어 수분 크림 50ml", 32_000, ("50ml", "50ml 2개 세트"), "세라마이드 NP, 판테놀", "스킨케어",
            ("바르고 나서 끈적이지 않는다", "민감한 피부에도 자극이 없다"), ("은은한 향이 있다", "용량이 금방 줄어든다")),
    Product(5, "오크 원목 4인 식탁 1400", 690_000, ("내추럴 오크", "월넛 스테인"), "북미산 화이트 오크 원목", "가구",
            ("상판이 두껍고 튼튼하다", "혼자서도 조립할 수 있다"), ("배송까지 2주가 걸린다", "모서리 마감이 거칠다")),
    Product(4, "제주 노지 감귤 5kg 선물세트", 34_900, ("5kg 중과", "5kg 대과"), "제주 서귀포산 노지 감귤", "과일",
            ("당도가 높다", "선물 포장이 깔끔하다"), ("크기가 고르지 않다", "몇 개는 물러서 왔다")),
)  # fmt: skip


# 리뷰 데이터의 별점. 요약 답이 말하는 평균 별점도 이 값에서 계산한다.
REVIEW_STARS = (5, 4, 5, 3, 5)


def average_stars() -> str:
    return f"{sum(REVIEW_STARS) / len(REVIEW_STARS):.1f}"


def option_list(product: Product) -> str:
    return ", ".join(product.options)


# --- 입력 ---------------------------------------------------------------


def copy_input(product: Product) -> str:
    return (
        f"상품명: {product.name} / 가격 {product.price:,}원 / "
        f"옵션: {option_list(product)} / 소재: {product.material}"
    )


def unstructured_text(product: Product) -> str:
    return (
        f"{product.name} 새로 입고됐어요! 가격은 {product.price:,}원이고 "
        f"{option_list(product)} 중에 고르실 수 있어요. 소재 정보: {product.material}. "
        f"{product.praises[0]}는 후기가 많습니다."
    )


def review_data(product: Product) -> str:
    lines = [f"[{product.name}] 최근 리뷰 5건"]
    texts = (
        product.praises[0],
        product.complaints[0],
        product.praises[1],
        product.complaints[1],
        f"재구매했다. {product.praises[0]}",
    )
    for number, (stars, text) in enumerate(zip(REVIEW_STARS, texts, strict=True), 1):
        lines.append(f"리뷰 {number} (별점 {stars}): {text}.")
    return "\n".join(lines)


def sales_data(product: Product, rng: Random) -> str:
    base = rng.randint(300, 1500)
    monthly = [
        int(base * growth)
        for growth in (1.0, rng.uniform(0.9, 1.2), rng.uniform(1.0, 1.4))
    ]
    stock = int(monthly[-1] * rng.uniform(0.4, 1.1))
    lines = [f"[{product.name}] 월별 판매"]
    for month, units in zip((8, 9, 10), monthly, strict=True):
        lines.append(
            f"{month}월 판매 {units:,}개 / 반품률 {rng.uniform(1.5, 6.0):.1f}%"
        )
    lines.append(
        f"현재 재고 {stock:,}개 / 옵션별 판매 비중 {product.options[0]} {rng.randint(45, 70)}%"
    )
    return "\n".join(lines)


# --- 직접 입력(CUSTOM) 실행 ----------------------------------------------

INQUIRY_PROMPT = "다음 고객 문의에 정중한 답변 초안을 3문장 이내로 작성하세요."
TITLE_PROMPT = "다음 상품명을 검색에 잘 걸리도록 40자 이내로 다듬어 주세요."


def inquiry_input(product: Product) -> str:
    return (
        f"주문 상품: {product.name} ({product.options[0]})\n"
        "문의: 받아 보니 생각과 달라서 다른 옵션으로 교환하고 싶어요. 택배비는 누가 내나요?"
    )


def title_input(product: Product) -> str:
    return f"{product.name} {product.category} {product.options[0]} 신상 인기 추천 특가"
