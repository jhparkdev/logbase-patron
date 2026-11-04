"""고객·프로젝트·서비스 기준정보.

고객 이름은 실존하지 않는 업체명으로 지었다(2026-11-03 웹 검색으로 같은 이름이 없음을 확인).
앱이 코드로 찾는 서비스·프로젝트는 앱의 상수를 그대로 써서, 이름이 바뀌면 테스트가 먼저 깨지게 한다.
"""

from dataclasses import dataclass
from datetime import datetime

from app.mock_data.period import PERIOD_START, kst
from app.mock_data.rows import Row
from app.models import ProjectType, ServiceType
from app.services.assistant_records import ASSISTANT_SERVICE_CODE
from app.services.model_test import TEST_SERVICE_CODE
from app.services.simulation_lookup import (
    SIMULATOR_PROJECT_CODE,
    SIMULATOR_SERVICE_CODE,
)

AI_PDP = "AI_PDP"
FLIPPAGE = "FLIPPAGE"
INTERNAL_TOOL = "INTERNAL_TOOL"


@dataclass(frozen=True)
class MockCustomer:
    customer_id: int
    customer_code: str
    name: str
    industry: str
    service_codes: tuple[str, ...]
    usage_from: datetime
    usage_until: datetime | None = None  # 계약 종료 시각. 이후에는 호출이 없다

    @property
    def is_active(self) -> bool:
        return self.usage_until is None


@dataclass(frozen=True)
class MockService:
    service_id: int
    service_code: str
    name: str
    service_type: ServiceType


@dataclass(frozen=True)
class MockProject:
    project_id: int
    project_code: str
    name: str
    project_type: ProjectType


CUSTOMERS = (
    MockCustomer(
        1,
        "CUST-001",
        "로웰린 스튜디오",
        "패션 쇼핑몰",
        (AI_PDP, FLIPPAGE),
        PERIOD_START,
    ),
    MockCustomer(2, "CUST-002", "에이븐전자몰", "가전 유통", (AI_PDP,), PERIOD_START),
    MockCustomer(
        3, "CUST-003", "뮤렌 코스메틱", "뷰티 브랜드", (AI_PDP,), kst(9, 8, 10)
    ),
    MockCustomer(4, "CUST-004", "솔레담 푸드", "식품·신선", (FLIPPAGE,), PERIOD_START),
    MockCustomer(5, "CUST-005", "모뉴하우스", "리빙·가구", (AI_PDP,), kst(10, 13, 10)),
    MockCustomer(
        6,
        "CUST-006",
        "카르펜 아웃도어",
        "스포츠·아웃도어",
        (AI_PDP,),
        PERIOD_START,
        kst(9, 30, 18),
    ),
)

SERVICES = (
    MockService(
        1, AI_PDP, "AI PDP (상품 상세페이지 생성)", ServiceType.CUSTOMER_FACING
    ),
    MockService(2, FLIPPAGE, "FlipPage", ServiceType.CUSTOMER_FACING),
    MockService(3, INTERNAL_TOOL, "내부 개발 도구", ServiceType.INTERNAL),
    MockService(4, SIMULATOR_SERVICE_CODE, "모델 비교 시뮬레이터", ServiceType.PATRON),
    MockService(5, TEST_SERVICE_CODE, "모델 연결 테스트", ServiceType.PATRON),
    MockService(6, ASSISTANT_SERVICE_CODE, "AI 도우미", ServiceType.PATRON),
)

PROJECTS = (
    MockProject(1, "PRJ-PDP-DEV", "AI PDP 고도화 개발", ProjectType.INTERNAL_DEV),
    MockProject(
        2, "PRJ-CUST-RENEWAL", "고객사 상세페이지 리뉴얼", ProjectType.CUSTOMER_PROJECT
    ),
    MockProject(3, SIMULATOR_PROJECT_CODE, "Patron PoC", ProjectType.POC),
)


def service_id(service_code: str) -> int:
    return next(s.service_id for s in SERVICES if s.service_code == service_code)


def project_id(project_code: str) -> int:
    return next(p.project_id for p in PROJECTS if p.project_code == project_code)


def customer_rows() -> list[Row]:
    return [
        {
            "customer_id": c.customer_id,
            "customer_code": c.customer_code,
            "name": c.name,
            "is_active": c.is_active,
            "is_mock": True,
        }
        for c in CUSTOMERS
    ]


def service_rows() -> list[Row]:
    return [
        {
            "service_id": s.service_id,
            "service_code": s.service_code,
            "name": s.name,
            "service_type": s.service_type,
            "is_active": True,
            "is_mock": True,
        }
        for s in SERVICES
    ]


def project_rows() -> list[Row]:
    return [
        {
            "project_id": p.project_id,
            "project_code": p.project_code,
            "name": p.name,
            "project_type": p.project_type,
            "is_active": True,
            "is_mock": True,
        }
        for p in PROJECTS
    ]
