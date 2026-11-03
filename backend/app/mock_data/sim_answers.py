"""모델 응답 원문. 모델 등급(고성능·표준·경량)에 따라 답의 길이와 구성이 달라진다.

일부 답은 실제로 자주 나오는 실수(코드 블록으로 감싼 JSON, 가격을 문자열로 쓴 JSON, 빠진 필드)를 담는다.
"""

import json
from random import Random

from app.mock_data.sim_content import (
    REVIEW_STARS,
    Flaw,
    Product,
    Tier,
    average_stars,
    option_list,
)


def product_copy(product: Product, tier: Tier, rng: Random) -> str:
    first = rng.choice(
        (
            f"{product.name}. {product.material} 소재로 완성한 {product.category}입니다.",
            f"{product.material} 소재로 만든 {product.category}, {product.name}입니다.",
        )
    )
    second = rng.choice(
        (
            f"준비한 옵션: {option_list(product)}.",
            f"옵션은 {option_list(product)} 중에서 고를 수 있습니다.",
        )
    )
    third = rng.choice(
        (f"가격은 {product.price:,}원입니다.", f"판매가 {product.price:,}원.")
    )
    if tier != Tier.LIGHT:
        first += f" {product.praises[0]}는 평을 가장 많이 받습니다."
        second += f" {product.praises[1]}는 점도 구매 이유로 자주 꼽힙니다."
        third += " 구매 전 상세 정보와 실측 사진을 함께 확인해 주세요."
    if tier == Tier.PREMIUM:
        first += " 매일 손이 가는 기본 아이템을 찾는 분께 잘 맞습니다."
        second += " 같은 옵션이라도 조명에 따라 색감이 조금 달라 보일 수 있습니다."
        third += f" '{product.complaints[0]}'는 의견이 있어 상세 안내를 보강했습니다."
    slogans = (
        f"{product.praises[0]}는 그 차이를 직접 느껴 보세요.",
        f"오늘의 {product.category}, {product.name}",
        f"{product.category} 고민은 여기서 끝.",
    )
    return f"{first}\n\n{second}\n\n{third}\n\n마케팅 문구: {rng.choice(slogans)}"


def _render_json(data: dict[str, object], tier: Tier, flaw: Flaw) -> str:
    text = json.dumps(
        data, ensure_ascii=False, indent=2 if tier != Tier.LIGHT else None
    )
    return f"```json\n{text}\n```" if flaw == Flaw.CODE_FENCE else text


def text_to_json(product: Product, tier: Tier, flaw: Flaw, rng: Random) -> str:
    data: dict[str, object] = {
        "name": product.name,
        "price": f"{product.price:,}원" if flaw == Flaw.WRONG_TYPE else product.price,
        "options": list(product.options),
    }
    if flaw == Flaw.MISSING_FIELD:
        del data["options"]
    if tier == Tier.PREMIUM and rng.random() < 0.5:
        data["material"] = product.material
    return _render_json(data, tier, flaw)


def summary_lines(product: Product, tier: Tier, rng: Random) -> str:
    lines = [
        rng.choice(
            (
                f"- 리뷰 {len(REVIEW_STARS)}건 평균 별점 {average_stars()}점",
                f"- 평균 별점 {average_stars()}점 (리뷰 {len(REVIEW_STARS)}건)",
            )
        ),
        f"- {rng.choice(('장점', '좋은 점'))}: {product.praises[0]}, {product.praises[1]}",
        f"- {rng.choice(('단점', '아쉬운 점'))}: {product.complaints[0]}",
    ]
    if tier != Tier.LIGHT:
        lines.append(f"- 개선 제안: '{product.complaints[1]}' 관련 안내 보강")
    if tier == Tier.PREMIUM:
        lines.append("- 재구매 언급이 있어 만족도가 높은 편")
    return "\n".join(lines)


def structured_summary(product: Product, tier: Tier, flaw: Flaw) -> str:
    points = [product.praises[0], product.praises[1], product.complaints[0]]
    if tier == Tier.PREMIUM:
        points.append(product.complaints[1])
    data: dict[str, object] = {
        "summary": (
            f"{product.name} 리뷰 {len(REVIEW_STARS)}건의 평균 별점은 {average_stars()}점이다. "
            f"{product.praises[0]}는 의견이 많고, "
            f"{product.complaints[0]}는 지적이 있다."
        ),
        "key_points": points,
    }
    if flaw == Flaw.MISSING_FIELD:
        del data["key_points"]
    if flaw == Flaw.WRONG_TYPE:
        data["key_points"] = " / ".join(points)
    return _render_json(data, tier, flaw)


def stock_strategy(product: Product, tier: Tier, rng: Random) -> str:
    cover = rng.choice(("3~4주 판매분", "한 달이 안 되는 양"))
    lines = [
        (
            f"1. {product.name}의 10월 판매가 늘어 다음 달에도 비슷한 수요가 "
            f"예상됩니다. 현재 재고는 {cover}이라 추가 발주를 권합니다."
        ),
        f"2. 판매 비중이 큰 {product.options[0]} 옵션을 우선 확보하세요.",
    ]
    if tier != Tier.LIGHT:
        lines.append(
            f"3. 반품 사유로 '{product.complaints[0]}'가 보여 상세 안내를 보강하면 반품률을 낮출 수 있습니다."
        )
    if tier == Tier.PREMIUM:
        lines.append(
            "4. 위험 요인: 발주가 늦으면 행사 기간에 품절될 수 있으니 2주 안에 결정하는 것이 좋습니다."
        )
    return "\n".join(lines)


def inquiry_reply(product: Product, tier: Tier, rng: Random) -> str:
    opener = rng.choice(
        ("안녕하세요, 고객님.", "문의 주셔서 감사합니다.", "불편을 드려 죄송합니다.")
    )
    reply = (
        f"{opener} 주문하신 {product.name} 교환을 도와드리겠습니다. "
        "단순 변심 교환은 왕복 택배비가 고객님 부담이며, 마이페이지에서 교환을 신청해 주세요."
    )
    if tier != Tier.LIGHT:
        reply += f" 원하시는 옵션({product.options[-1]}) 재고를 확인한 뒤 바로 안내드리겠습니다."
    return reply


def search_title(product: Product, tier: Tier, rng: Random) -> str:
    if tier == Tier.LIGHT:
        return rng.choice(
            (
                f"{product.name} {product.options[0]}",
                f"{product.name} {product.category}",
                f"{product.options[0]} {product.name}",
            )
        )
    separator = rng.choice((" | ", " - ", " / "))
    return f"{product.name}{separator}{product.category} {product.options[0]}·{product.options[-1]}"
